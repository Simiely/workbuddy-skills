# -*- coding: utf-8 -*-
"""镜像源实测：pip / npm 各家国内镜像 vs 官方源，用同一份数据测连通 + TTFB + 传输。"""
import socket, ssl, time, io, os, statistics

def fetch(host, path, sni=None, limit=6 * 1024 * 1024, timeout=25):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    t0 = time.time()
    raw = socket.create_connection((host, 443), timeout=timeout)
    t1 = time.time()
    s = ctx.wrap_socket(raw, server_hostname=sni or host)
    t2 = time.time()
    s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: Mozilla/5.0\r\nAccept: */*\r\nConnection: close\r\n\r\n"
               % (path, sni or host)).encode())
    total = 0; first = True; hdr = b""; ttfb = None
    while total < limit:
        try: c = s.recv(131072)
        except Exception: break
        if not c: break
        if first:
            hdr += c
            if b"\r\n\r\n" in hdr:
                head, _, body = hdr.partition(b"\r\n\r\n")
                status = head.split(b"\r\n")[0].decode(errors="replace")
                ttfb = time.time() - t0
                total += len(body); first = False
        else:
            total += len(c)
        if time.time() - t0 > timeout: break
    dt = time.time() - t0
    try: s.close()
    except Exception: pass
    code = status.split(" ")[1] if len(status.split(" ")) > 1 else "?"
    return dict(conn=(t1 - t0) * 1000, tls=(t2 - t1) * 1000, ttfb=(ttfb or 0) * 1000,
                bytes=total, ms=dt, code=code, mbs=(total / 1048576) / dt if dt else 0)

out = io.StringIO()
def w(s): out.write(s + "\n"); print(s, flush=True)

w("=" * 100)
w("  一、pip 镜像实测（同一个 numpy 索引页，真实传输）")
w("=" * 100)
w("  %-34s %6s %8s %9s %9s %9s %s" % ("镜像", "状态", "建连+TLS", "TTFB", "下载量", "总耗时", "速率"))
w("  " + "-" * 96)
PIP = [
    ("pypi.tuna.tsinghua.edu.cn", "/simple/numpy/", "清华 TUNA"),
    ("mirrors.aliyun.com", "/pypi/simple/numpy/", "阿里云"),
    ("mirrors.cloud.tencent.com", "/pypi/simple/numpy/", "腾讯云"),
    ("mirrors.huaweicloud.com", "/repository/pypi/simple/numpy/", "华为云"),
    ("pypi.org", "/simple/numpy/", "官方 PyPI（跨境对照）"),
]
for host, path, tag in PIP:
    try:
        r = fetch(host, path, limit=4 * 1024 * 1024)
        w("  %-34s %6s %6.0fms %8.0fms %7.1fKB %8.0fms %6.2f MB/s"
          % (tag, r["code"], r["conn"] + r["tls"], r["ttfb"], r["bytes"] / 1024, r["ms"], r["mbs"]))
    except Exception as e:
        w("  %-34s FAIL %s: %s" % (tag, type(e).__name__, e))

w("")
w("=" * 100)
w("  二、npm 镜像实测（同一个包 lodash 的元数据）")
w("=" * 100)
w("  %-34s %6s %8s %9s %9s %9s %s" % ("镜像", "状态", "建连+TLS", "TTFB", "下载量", "总耗时", "速率"))
w("  " + "-" * 96)
NPM = [
    ("registry.npmmirror.com", "/lodash", "npmmirror（阿里）"),
    ("registry.npmjs.org", "/lodash", "官方 npm（跨境对照）"),
]
for host, path, tag in NPM:
    try:
        r = fetch(host, path, limit=2 * 1024 * 1024)
        w("  %-34s %6s %6.0fms %8.0fms %7.1fKB %8.0fms %6.2f MB/s"
          % (tag, r["code"], r["conn"] + r["tls"], r["ttfb"], r["bytes"] / 1024, r["ms"], r["mbs"]))
    except Exception as e:
        w("  %-34s FAIL %s: %s" % (tag, type(e).__name__, e))

w("")
w("=" * 100)
w("  三、结论读法：TTFB 反映就近程度，速率反映带宽/限速；两者的最优可能不是同一台。")
w("     注意：阿里云对单连接有限速（本次早前实测 ubuntu 镜像单连接 0.87MB/s），")
w("     所以如果看到阿里云 TTFB 低但速率不高，是限速而非距离问题。")
w("=" * 100)

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirror_bench_out.txt")
open(p, "w", encoding="utf-8").write(out.getvalue())
print("\n[written] " + p)
