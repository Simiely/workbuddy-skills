# -*- coding: utf-8 -*-
"""生成安全的网络配置备份（可读快照 + 可编程恢复的 JSON）。
   注意：不用 netsh dump —— 它不含生产网卡的 DNS 配置，且正文带 reset 命令，误用会重置网络。"""
import winreg, subprocess, json, os, datetime, io

HKLM = winreg.HKEY_LOCAL_MACHINE
IFB = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
NETBT = r"SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces"
OUT = os.path.dirname(os.path.abspath(__file__))

def rd(path, name, root=HKLM):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except FileNotFoundError:
        return None
    except OSError:
        return None

def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    try: return p.stdout.decode("gbk")
    except Exception: return p.stdout.decode("utf-8", errors="replace")

# 静态 DNS 也读一份
static_dns = {}
o = run(["netsh", "interface", "ipv4", "show", "dnsservers"])
cur = None
for line in o.splitlines():
    s = line.strip()
    if s.startswith("接口 ") or s.startswith("接口\"") or ('"' in s and "配置" in s):
        try:
            cur = s.split('"')[1]
        except IndexError:
            cur = None
    elif "DNS" in s or "dns" in s.lower():
        static_dns.setdefault(cur, []).append(s)

snapshot = {
    "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "hostname": run(["hostname"]).strip(),
    "interfaces": {},
    "notes": "本文件由 make_net_backup.py 生成。可用于人工核对或脚本恢复，安全（不含 reset 命令）。",
}

with winreg.OpenKey(HKLM, IFB) as k:
    i = 0
    while True:
        try: guid = winreg.EnumKey(k, i); i += 1
        except OSError: break
        d = {
            "guid": guid,
            "DhcpIPAddress": rd(IFB + "\\" + guid, "DhcpIPAddress"),
            "IPAddress": rd(IFB + "\\" + guid, "IPAddress"),
            "DhcpSubnetMask": rd(IFB + "\\" + guid, "DhcpSubnetMask"),
            "SubnetMask": rd(IFB + "\\" + guid, "SubnetMask"),
            "DhcpDefaultGateway": rd(IFB + "\\" + guid, "DhcpDefaultGateway"),
            "DefaultGateway": rd(IFB + "\\" + guid, "DefaultGateway"),
            "EnableDHCP": rd(IFB + "\\" + guid, "EnableDHCP"),
            "NameServer": rd(IFB + "\\" + guid, "NameServer"),
            "DhcpNameServer": rd(IFB + "\\" + guid, "DhcpNameServer"),
            "DhcpServer": rd(IFB + "\\" + guid, "DhcpServer"),
            "NetbiosOptions": rd(NETBT + "\\Tcpip_" + guid, "NetbiosOptions"),
        }
        if any(v is not None for v in d.values()):
            snapshot["interfaces"][guid] = d

snapshot["global"] = {
    "tcp_settings": run(["netsh", "int", "tcp", "show", "global"]),
    "dns_servers_text": o,
    "routes_default": [l.strip() for l in run(["route", "print", "-4"]).splitlines()
                       if l.strip().startswith("0.0.0.0")],
    "proxy_wininet": {
        "ProxyEnable": rd(r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", "ProxyEnable", winreg.HKEY_CURRENT_USER),
        "ProxyServer": rd(r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", "ProxyServer", winreg.HKEY_CURRENT_USER),
    },
    "nic_eee": {
        "EEELinkAdvertisement": rd(r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\0001", "EEELinkAdvertisement"),
        "ULPMode": rd(r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\0001", "ULPMode"),
    },
    "winhttp": run(["netsh", "winhttp", "show", "proxy"]),
}

with open(os.path.join(OUT, "net_backup.json"), "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)

# 人类可读版
buf = io.StringIO()
def w(s): buf.write(s + "\n")
w("网络配置备份  %s" % snapshot["generated"])
w("主机: %s" % snapshot["hostname"])
w("=" * 88)
w("")
w("【当前生效的 DNS】")
for line in o.splitlines():
    if line.strip(): w("  " + line.strip())
w("")
w("【默认路由】")
for line in snapshot["global"]["routes_default"]:
    w("  " + line)
w("")
w("【代理 / 网卡节能 / 其它】")
g = snapshot["global"]
w("  ProxyEnable              = %r" % g["proxy_wininet"]["ProxyEnable"])
w("  ProxyServer              = %r" % g["proxy_wininet"]["ProxyServer"])
w("  EEELinkAdvertisement     = %r" % g["nic_eee"]["EEELinkAdvertisement"])
w("  ULPMode                  = %r" % g["nic_eee"]["ULPMode"])
w("  winhttp                  = %s" % " ".join(g["winhttp"].split())[-30:])
w("")
w("【各接口关键值】")
for guid, d in snapshot["interfaces"].items():
    ip = d["DhcpIPAddress"] or d["IPAddress"]
    if not ip and not d["NameServer"] and not d["DhcpNameServer"]:
        continue
    w("  %s" % guid)
    w("     IP            = %s" % (ip or "-"))
    w("     网关          = %s" % (d["DhcpDefaultGateway"] or d["DefaultGateway"] or "-"))
    w("     NameServer    = %r   ← 手工静态（生效的那个）" % d["NameServer"])
    w("     DhcpNameServer= %r   ← DHCP 下发的" % d["DhcpNameServer"])
    w("     NetbiosOptions= %r" % d["NetbiosOptions"])
w("")
w("【TCP 全局参数】")
for line in snapshot["global"]["tcp_settings"].splitlines():
    if line.strip(): w("  " + line.strip())

with open(os.path.join(OUT, "net_backup.txt"), "w", encoding="utf-8") as f:
    f.write(buf.getvalue())

print(buf.getvalue())
print("[written] net_backup.json / net_backup.txt")

# 删掉误导性的 netsh dump 文件
for bad in ["netcfg_backup.txt"]:
    p = os.path.join(OUT, bad)
    if os.path.exists(p):
        os.remove(p)
        print("[removed] %s  （netsh dump 不含生产网卡 DNS，且正文带 reset 命令，不能用作还原）" % bad)
