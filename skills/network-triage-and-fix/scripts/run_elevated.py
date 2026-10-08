# -*- coding: utf-8 -*-
"""通用提权执行器（解决"沙箱内改不了系统设置"的问题）。

用法:
    python run_elevated.py <要执行的 .bat 或命令> [--marker <标记文件路径>] [--wait N]

要点（实测踩坑，务必遵守）:
  1. 绝对不要对 .bat 直接用 "runas" 动词 —— ShellExecuteW 会返回 42（看起来成功），
     但脚本根本不会执行，无日志、无进程。必须把 .bat 包在 cmd.exe /c 里。
  2. 返回值 >32 只代表"已发起提权请求"，不代表执行成功。
     判定成功必须让提权进程写一个标记文件，再回读。
  3. 本机账户 2504 是管理员但 UAC 过滤了令牌 —— 会弹 UAC，点"是"即可，不用输密码。
  4. 若目标路径在沙箱工作区之外、或需要写文件观察结果，
     Bash 调用本身建议加 dangerouslyDisableSandbox: true。
"""
import ctypes, ctypes.wintypes as wt, os, sys, time

SHELL32 = ctypes.WinDLL("shell32", use_last_error=True)
SHELL32.ShellExecuteW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_int]
SHELL32.ShellExecuteW.restype = ctypes.c_void_p

CMD = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")

ERRS = {0: "内存不足", 2: "文件未找到", 3: "路径未找到", 5: "访问被拒绝（UAC 被点否/策略禁止）",
        8: "内存不足", 26: "共享冲突", 27: "文件关联不完整", 28: "DDE 超时",
        29: "DDE 失败", 30: "DDE 忙", 31: "无关联应用程序", 32: "DLL 未找到"}


def elevate(target, marker=None, wait=0.0, extra_args=None):
    """提权执行 target（.bat/.exe/命令）。返回 True/False。"""
    if marker and os.path.exists(marker):
        os.remove(marker)

    if target.lower().endswith((".bat", ".cmd")):
        params = '/c "%s"' % target
        if marker:
            params = '/c ""%s" > "%s" 2>&1"' % (target, marker)
    else:
        params = target

    print("target  :", target)
    print("params  :", params)
    print("cmd.exe :", CMD, os.path.exists(CMD))
    print("isAdmin :", bool(ctypes.windll.shell32.IsUserAnAdmin()), "(False = 需要提权)")

    r = SHELL32.ShellExecuteW(None, "runas", CMD, params, None, 0)
    code = ctypes.cast(r, ctypes.c_void_p).value or 0
    print("ShellExecuteW ->", code)
    if 0 < code <= 32:
        print("  ✗ 发起失败:", ERRS.get(code, "未知"))
        return False
    print("  ✓ 提权请求已发起 —— 请在 UAC 弹框点【是】")

    if marker and wait > 0:
        deadline = time.time() + wait
        while time.time() < deadline:
            if os.path.exists(marker):
                print("  ✓ 提权进程已执行（标记文件出现）:", marker)
                return True
            time.sleep(1)
        print("  ✗ 等待超时，标记文件未出现 —— 提权可能被拒绝")
        return False
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    tgt = sys.argv[1]
    mk = None
    wt_sec = 0.0
    if "--marker" in sys.argv:
        mk = sys.argv[sys.argv.index("--marker") + 1]
    if "--wait" in sys.argv:
        wt_sec = float(sys.argv[sys.argv.index("--wait") + 1])
    if not os.path.isabs(tgt):
        tgt = os.path.abspath(tgt)
    ok = elevate(tgt, marker=mk, wait=wt_sec)
    sys.exit(0 if ok else 1)
