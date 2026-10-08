# -*- coding: utf-8 -*-
"""同尺性能基准：30 域冷启动解析 + 国内 CDN 建连 + 境外建连。

用法:
    python bench.py --save <标签>     # 结果存 bench_<标签>.txt
    python bench.py                   # 只打印

对比纪律: 必须与「同一脚本、同一域名集」的历史结果比，不同口径的数字不可比。
"""
import argparse
import socket
import ssl
import struct
import subprocess
import time
import random
import statistics
import os
import sys


def dns_query(server, name, rdtype=1, timeout=2.5):
    tid = random.randint(0, 65535)
    q = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    for part in name.split("."):
        q += bytes([len(part)]) + part.encode()
    q += b"\x00" + struct.pack(">HH", rdtype, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.sendto(q, (server, 53))
        data, _ = s.recvfrom(4096)
        rcode = data[3] & 0x0F
        ancount = struct.unpack(">H", data[6:8])[0]
        off = 12
        off = skip_name(data, off)
        off += 4
        addrs = []
        for _ in range(ancount):
            off = skip_name(data, off)
            if off + 10 > len(data):
                break
            rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[off:off + 10])
            off += 10
            if rtype == 1 and rdlen == 4:
                addrs.append(socket.inet_ntoa(data[off:off + 4]))
            off += rdlen
        return (time.time() - t0) * 1000, rcode, addrs, None
    except Exception as e:
        return (time.time() - t0) * 1000, None, [], type(e).__name__
    finally:
        s.close()


def skip_name(data, off):
    while True:
        if off >= len(data):
            return off
        l = data[off]
        if l == 0:
            return off + 1
        if l & 0xC0 == 0xC0:
            return off + 2
        off += 1 + l


def tcp_ms(ip, port=443, timeout=4.0, tries=2):
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


SITES = [
    "www.zhihu.com", "www.bilibili.com", "www.iqiyi.com", "www.youku.com", "www.douban.com",
    "www.36kr.com", "www.hupu.com", "www.51job.com", "www.12306.cn", "www.gov.cn",
    "www.tsinghua.edu.cn", "www.pku.edu.cn", "docs.qq.com", "cloud.tencent.com",
    "developer.aliyun.com", "www.cnblogs.com", "gitee.com", "www.oschina.net",
    "www.runoob.com", "www.w3school.com.cn", "segmentfault.com", "juejin.cn",
    "www.jianshu.com", "www.csdn.net", "mirrors.tuna.tsinghua.edu.cn",
    "pypi.tuna.tsinghua.edu.cn", "npm.taobao.org", "mirrors.aliyun.com",
    "www.deepseek.com", "www.qq.com",
]
CDN = ["www.bilibili.com", "www.douyin.com", "www.taobao.com", "dldir1.qq.com", "cdn.jsdelivr.net"]
OVERSEAS = ["github.com", "registry.npmjs.org", "raw.githubusercontent.com"]


def current_dns(iface_hint=None):
    """探测当前生效的 DNS（优先取有静态配置的接口，否则取第一个有 DNS 的）"""
    p = subprocess.run(["netsh", "interface", "ipv4", "show", "dnsservers"], capture_output=True)
    try:
        txt = p.stdout.decode("gbk")
    except Exception:
        txt = p.stdout.decode("utf-8", errors="replace")
    ips = []
    cur = None
    blocks = {}
    for line in txt.splitlines():
        if '"' in line and ("接口" in line or "interface" in line.lower()):
            try:
                cur = line.split('"')[1]
            except IndexError:
                cur = None
        for tok in line.replace(":", " ").replace(",", " ").split():
            if tok.count(".") == 3 and tok[0].isdigit():
                blocks.setdefault(cur, []).append(tok)
    for name, lst in blocks.items():
        for ip in lst:
            if ip not in ips:
                ips.append(ip)
    return ips[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label", nargs="?", default="run")
    ap.add_argument("--save", dest="save", action="store_true")
    args = ap.parse_args()
    label = args.label

    lines = []
    def w(s):
        lines.append(s)
        print(s, flush=True)

    w("=" * 82)
    w("  DNS 基准测试  [%s]   %s" % (label, time.strftime("%Y-%m-%d %H:%M:%S")))
    w("=" * 82)
    cur = current_dns()
    w("  当前生效的 DNS 服务器: %s" % (", ".join(cur) if cur else "(未识别)"))
    w("")

    if cur:
        lat = []
        for d in SITES[:10]:
            ms, rc, a, err = dns_query(cur[0], d)
            if err is None and rc == 0 and a:
                lat.append(ms)
        if lat:
            w("  首台 DNS 直接查询: 平均 %.1fms（10 域）" % statistics.mean(lat))
    w("")

    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
    t0 = time.time()
    ok = 0
    for d in SITES:
        try:
            socket.getaddrinfo(d, 443)
            ok += 1
        except Exception:
            pass
    total = (time.time() - t0) * 1000
    w("  A. 冷启动会话：%d 个域名首次解析" % len(SITES))
    w("     总计 %7.0f ms   平均 %5.1f ms/域   成功 %d/%d" % (total, total / len(SITES), ok, len(SITES)))
    w("")

    dns_now = cur[0] if cur else "223.5.5.5"
    w("  B. 国内 CDN 节点选择（解析后测建连；越小越近）")
    dom_sum = []
    for d in CDN:
        ms, rc, a, err = dns_query(dns_now, d)
        if err or rc != 0 or not a:
            w("     %-20s 解析失败 (%s)" % (d, err or rc))
            continue
        t = tcp_ms(a[0])
        dom_sum.append(t if t else 9999)
        w("     %-20s -> %-16s 建连 %s" % (d, a[0], ("%.0fms" % t) if t else "超时"))
    domestic = [x for x, c in zip(dom_sum, CDN) if "jsdelivr" not in c]
    if domestic:
        w("     国内 CDN 平均建连 %.1f ms（不含境外 jsdelivr 时 %.1f ms）"
          % (statistics.mean(dom_sum), statistics.mean(domestic)))
    w("")

    w("  C. 境外 / 开发域名")
    os_sum = []
    for d in OVERSEAS:
        ms, rc, a, err = dns_query(dns_now, d)
        if err or rc != 0 or not a:
            w("     %-28s 解析失败 (%s)" % (d, err or rc))
            continue
        t = tcp_ms(a[0])
        if t:
            os_sum.append(t)
        w("     %-28s -> %-16s 建连 %s" % (d, a[0], ("%.0fms" % t) if t else "超时"))
    if os_sum:
        w("     境外平均建连 %.1f ms" % statistics.mean(os_sum))
    w("")
    w("=" * 82)
    w("  与历史基线对比：把本输出与 bench_<旧标签>.txt 逐项比（A 总耗时 / B 国内建连 / C 境外）")
    w("=" * 82)

    if args.save:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_%s.txt" % label)
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("\n[written] " + out)


if __name__ == "__main__":
    main()
