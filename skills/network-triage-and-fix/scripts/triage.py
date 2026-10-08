# -*- coding: utf-8 -*-
"""网络快速分诊（抓现场）：接口/路由/DNS/延迟/实时带宽/出站/SYN_SENT/错误计数。
   只读诊断（flushdns 除外），可反复运行；结果存 triage_now.txt 供与历史对比。"""
import subprocess
import socket
import time
import re
import statistics
import collections
import datetime
import os

_buf = []


def w(s):
    _buf.append(s + "\n")
    print(s, flush=True)


def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        try:
            return p.stdout.decode("gbk")
        except Exception:
            return p.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        return "[%s]%s" % (type(e).__name__, e)


w("网络快速分诊  %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
w("=" * 90)

# 1) 接口状态 / 跃点
w("【1】接口状态 / 跃点 / MTU")
ifaces = run(["netsh", "interface", "ipv4", "show", "interfaces"])
w(ifaces)
connected = []
for line in ifaces.splitlines():
    m = re.match(r"\s*(\d+)\s+(\d+)\s+\d+\s+connected\s+(.+?)\s*$", line)
    if m:
        connected.append((int(m.group(1)), int(m.group(2)), m.group(3).strip()))
w("")

# 2) 默认路由
w("【2】默认路由（有无同跃点/新增）")
rt = run(["route", "print", "-4"])
defr = [l.strip() for l in rt.splitlines() if l.strip().startswith("0.0.0.0")]
for l in defr:
    w("  " + l)
if len(defr) > 1:
    metas = [l.split() for l in defr]
    w("  ★ 存在 %d 条默认路由 —— 若其中来自两个不同接口且跃点接近，选路不确定" % len(defr))
w("")

# 3) DNS 现状
w("【3】DNS 服务器现状（全部接口）")
dnstxt = run(["netsh", "interface", "ipv4", "show", "dnsservers"])
w(dnstxt)
w("")

# 4) 链路质量
w("【4】链路质量（各 30 包）")
def ping_stat(target, n=30):
    p = subprocess.run(["ping", "-n", str(n), "-w", "2000", target], capture_output=True)
    t = p.stdout.decode("gbk", errors="replace")
    ts = [int(m.group(1)) for m in re.finditer(r"(?:时间|time)\s*[=<]\s*(\d+)\s*ms", t)]
    lm = re.search(r"(\d+)%", t)
    if not ts:
        return None
    return (statistics.mean(ts), max(ts), statistics.pstdev(ts),
            int(lm.group(1)) if lm else None, len(ts))


# 自动探测网关
gw = None
for line in rt.splitlines():
    if line.strip().startswith("0.0.0.0") and "10034" not in line:
        f = line.split()
        if len(f) >= 5 and f[2].count(".") == 3:
            gw = f[2]
            break
dns_primary = None
for line in dnstxt.splitlines():
    for tok in line.replace(":", " ").split():
        if tok.count(".") == 3 and tok[0].isdigit():
            dns_primary = dns_primary or tok

targets = []
if gw:
    targets.append((gw, "网关"))
if dns_primary:
    targets.append((dns_primary, "首选DNS"))
targets += [("www.baidu.com", "百度"), ("mirrors.aliyun.com", "阿里云镜像")]
for t, l in targets:
    r = ping_stat(t)
    if r:
        w("  %-14s %-18s 平均 %6.1fms  最大 %4dms  抖动 %5.2fms  丢包 %s%%  收 %d/30"
          % (l, t, r[0], r[1], r[2], r[3], r[4]))
    else:
        w("  %-14s %-18s 无 ICMP 响应（不一定是故障：很多公网 IP 禁 ping）" % (l, t))
w("")

# 5) DNS 解析实测
w("【5】DNS 解析实测（系统解析器，清缓存后）")
socket.setdefaulttimeout(4)
run(["ipconfig", "/flushdns"])
doms = ["www.qq.com", "www.baidu.com", "www.taobao.com", "github.com", "www.bilibili.com",
        "www.douyin.com", "mirrors.aliyun.com", "pypi.org", "registry.npmmirror.com", "www.zhihu.com"]
t0 = time.time()
ok = 0
times = []
for d in doms:
    a = time.time()
    try:
        socket.getaddrinfo(d, 443)
        times.append((time.time() - a) * 1000)
        ok += 1
    except Exception:
        pass
if times:
    w("  成功 %d/%d  总耗时 %.0fms  平均 %.1fms  最慢 %.0fms"
      % (ok, len(doms), (time.time() - t0) * 1000, statistics.mean(times), max(times)))
w("")

# 6) 实时带宽
w("【6】实时带宽占用（每 4 秒采样）")
def netstat_e():
    t = run(["netstat", "-e"])
    for l in t.splitlines():
        f = l.split()
        if len(f) == 3 and f[0] == "字节":
            try:
                return (int(f[1].replace(",", "")), int(f[2].replace(",", "")))
            except ValueError:
                pass
    return None


prev = netstat_e()
for i in range(3):
    time.sleep(4)
    cur = netstat_e()
    if cur and prev:
        drx = (cur[0] - prev[0]) / 4
        dtx = (cur[1] - prev[1]) / 4
        w("  采样%d: 下行 %8.0f B/s (%5.2f Mbps)   上行 %8.0f B/s (%5.2f Mbps)"
          % (i + 1, drx, drx * 8 / 1e6, dtx, dtx * 8 / 1e6))
    prev = cur
w("")

# 7) 出站建连
w("【7】出站实测（TCP 443 建连，各 2 次）")
def tcp(ip, port=443, timeout=5, tries=2):
    best = None
    for _ in range(tries):
        t0 = time.time()
        try:
            s = socket.create_connection((ip, port), timeout=timeout)
            s.close()
            d = (time.time() - t0) * 1000
            best = d if best is None else min(best, d)
        except Exception:
            pass
    return best


import socket as _s
import urllib.parse
extra = []
for d in ["www.baidu.com", "mirrors.aliyun.com", "registry.npmmirror.com"]:
    try:
        ip = socket.gethostbyname(d)
        extra.append((ip, d))
    except Exception:
        pass
seen = set()
for ip, l in extra + [(t, lbl) for t, lbl in targets]:
    if ip in seen:
        continue
    seen.add(ip)
    t = tcp(ip)
    w("  %-14s %-18s %s" % (l, ip, ("✅ %.0fms" % t) if t else "❌ 超时"))
w("")

# 8) TCP 状态 + SYN_SENT
w("【8】TCP 状态 / SYN_SENT（谁在等连不上的目标）")
ns = run(["netstat", "-ano"])
st = collections.Counter()
syn = []
for l in ns.splitlines():
    m = re.search(r"\s+(LISTENING|ESTABLISHED|TIME_WAIT|SYN_SENT|CLOSE_WAIT|FIN_WAIT\w*|LAST_ACK)\s+", l)
    if m:
        st[m.group(1)] += 1
    if "SYN_SENT" in l:
        f = l.split()
        if len(f) >= 5:
            syn.append((f[2], f[4]))
w("  " + str(dict(st)))
if syn:
    targets_seen = sorted({d for d, _ in syn})
    w("  ★ %d 条 SYN_SENT，目标: %s" % (len(syn), ", ".join(targets_seen)))
    w("     → 逐个用 IP 直连复核：能连=本机/应用问题；连不上=被墙或对端问题")
    w("     → 找出对应进程（netstat 最后一列 PID + 任务管理器）并决定 关页/镜像/fail-fast")
else:
    w("  ✅ 无 SYN_SENT")
w("")

# 9) 接口错误
w("【9】接口错误 / 丢弃（应为 0）")
ne = run(["netstat", "-e"])
for l in ne.splitlines():
    if re.match(r"^(丢弃|错误|Discards|Errors)", l.strip()):
        w("  " + l.strip())
w("")

outp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triage_now.txt")
with open(outp, "w", encoding="utf-8") as f:
    f.write("".join(_buf))
print("\n[written] " + outp)
