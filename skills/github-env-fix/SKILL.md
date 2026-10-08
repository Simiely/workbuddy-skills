---
name: github-env-fix
description: 在 WorkBuddy 沙箱 / Windows 无交互环境里，推送或发布 GitHub 之前，先做"环境就绪检测 + 修复"。核心是根治 git 凭据弹窗 credentialhelperselector/GCM（设全局 credential.helper=），并确认网络通道就绪（7890(Clash) 是可靠通道之一；github 通道时通时断，直连与代理都要试、自动重试）。用户说"先修环境 / 推送前准备 / 又弹窗了 / git 环境有问题 / 环境就绪"时先跑本 skill，跑完再走 github-push-universal 或 github-release。
agent_created: true
version: 1.0.0
---

# GitHub 推送前环境修复（env-fix）

> ⚠️ **必须先读本节。** 历史结论有两版，都是实测：① 2026-09：走 7890(Clash) 代理可达、直连不通，且真正让 git 卡死/弹窗的是 **credential helper（helper-selector/GCM）**，不是代理；② 2026-10-08：**出口会漂**——同一天里 7890 死过（10061 拒绝）、直连成功过又失败过、代理 502 间歇。⇒ **7890 是可靠通道之一（建议保留配置），但不是"必通"常量；任何一次失败都别判死，直连与代理都要试并自动重试**（与 github-push-universal 注 9 的出口矩阵一致）。

## 本 skill 定位

- 它是 `github-push-universal`（推代码）与 `github-release`（发版本）的**前置步骤**。
- 职责：**先把 git 环境修到"能稳定走代理 push、不弹窗"**，再交棒给兄弟 skill。
- 触发时机：推送/发布**之前**，或用户报"又弹 credentialhelperselector / git 环境有问题 / 推送前先修一下"。

---

## 正确基线（本机事实，勿改）

> 📝 路径中的 `<USER>` = 本机 Windows 用户名（源仓库记录于 260803 机器，移植到其它机器时按实际用户名替换，如 `C:/Users/2504/...`）。

1. **git 来源**：唯一 git 是 WorkBuddy 自带 `PortableGit`（当前 `C:/Users/<USER>/.workbuddy/binaries/PortableGit/versions/1.2.0/`）。无系统 Git。
2. **网络**：墙内。`127.0.0.1:7890`(Clash) 是**可靠通道之一**（多数时间可达），但 **github 通道时通时断**——直连（`-c http.proxy=`）也曾成功（2026-10-08 实测：`ls-remote` 直连成功过，同日 `git clone` 直连 4 连败、代理 502 间歇）。出口会漂，**每次先跑出口矩阵（env 隧道 / 7890 / 直连 三角色）**，**一次失败 ≠ 此路不通，直连与代理都要试并自动重试**。
3. **唯一真正的故障源**：git 需要凭据时，被 PortableGit 系统级 `etc/gitconfig` 的 `credential.helper = helper-selector` 拦截 → 弹 `credentialhelperselector` / GCM 凭据窗；无 tty 的沙箱会话里弹窗即**挂死**。
   - 触发条件：remote **无内嵌 token**，且目标需凭据（如私有仓库写操作）。
   - 系统级 `helper-selector` 由 PortableGit 出厂预设（`git-credential-helper-selector.exe`），**不要改系统级 gitconfig**（WorkBuddy 更新会覆盖）；在**全局** `~/.gitconfig` 覆盖即可。
4. **token**：推荐使用环境变量 `GH_TOKEN`（唯一推荐做法），备选内嵌在 remote URL（`https://x-access-token:<PAT>@github.com/...`）。带 token 时 helper 完全不介入，无需任何弹窗。

---

## 就绪检测清单（按序执行，全绿才算就绪）

```bash
# 1) git 存在且版本可用
git --version

# 2) 是否有弹窗 helper 残留（命中任一即需修复）
git config --global --get-regexp 'credential'          # 若 credential.helper 非空 / 有 helperselector.selected → 需修
git config --show-origin --get credential.helper        # 系统级 helper-selector 是 PortableGit 预设，不碰系统级

# 3) 代理配置（7890 是可靠通道之一；若全局代理已被删，改走直连+重试也可）
git config --global --get http.proxy                    # 常见为 http://127.0.0.1:7890；为空不代表环境坏，可直连重试
git config --global --get https.proxy                   # 期望 http://127.0.0.1:7890

# 4) 实测连通（走代理 + 禁 helper，测网络本身；应返回 ref 而非挂起/弹窗）
GIT_TERMINAL_PROMPT=0 timeout 25 git -c credential.helper= \
  ls-remote https://github.com/git/git.git HEAD

# 5) token 是否有效（如有 remote 内嵌 token 或 GH_TOKEN）
git -c credential.helper= ls-remote "https://x-access-token:<PAT>@github.com/<owner>/<repo>.git" HEAD
```

判定：
- 第 4 步公开仓库通 → **代理/网络 OK**，问题只在凭据弹窗 → 执行下方「修复 A」。
- 第 4 步不通（当前通道仍挂/报错）→ 才去看 `github-connect-diag` 的网络诊断（注意：出口会漂，换通道重试优先于深诊断）。

---

## 修复 A：根治凭据弹窗（全局，改前先备份）

唯一必做项。**代理一律不动**。

```bash
# 0) 备份（持久改动前强制）
cp ~/.gitconfig ~/.gitconfig.bak.$(date +%Y%m%d-%H%M%S)

# 1) 全局置空 credential.helper，覆盖系统级 helper-selector / 现有 wincred
git config --global credential.helper ""

# 2) 清除残留的 helperselector.selected（它会让 selector 机制仍介入）
git config --global --unset credential.helperselector.selected 2>/dev/null || true
```

**效果**：此后 git 任何需要凭据的请求都不会再弹窗。副作用：若 remote 无内嵌 token 且目标是私有仓库，将无法交互输密码 → **所有私有仓库 remote 必须内嵌 token**（兄弟 skill 均如此处理）。

**验证**：
```bash
git config --global --get credential.helper   # 应无输出（空）
git config --global --get credential.helperselector.selected  # 应报错/空（已删）
```

**回滚**：若需恢复，`git config --global credential.helper "!C:/Users/<USER>/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin/git-credential-wincred.exe"`（或从备份 .gitconfig.bak 还原）。

---

## 配置 GH_TOKEN（推荐认证方式）

修复弹窗后，私有仓库必须带 token 才能推送。**推荐使用 `GH_TOKEN` 环境变量**：

```bash
# 设置用户环境变量（持久生效，一次设置所有仓库共用）
[Environment]::SetEnvironmentVariable("GH_TOKEN", "ghp_xxx", "User")

# 设置完成后，兄弟 skill 自动读取使用
```

推荐理由：
- **不落盘**：token 只在内存/环境变量传递，不写入 `.git/config` 或磁盘文件
- **全局生效**：所有仓库自动共用，无需逐个修改 remote URL
- **零弹窗**：脚本自动将 `GH_TOKEN` 内嵌到推送 URL，credential helper 完全不介入

> 兄弟 skill `github-push-universal` 和 `github-release` 已内置对 `GH_TOKEN` 的支持，优先级：`--token` 参数 > URL 内嵌 > `GH_TOKEN` > `GITHUB_TOKEN`。

---

## 修复后交棒

- 就绪清单全绿 → 交给 **`github-push-universal`**（推代码）或 **`github-release`**（发版本）。
- 这两个兄弟 skill 的通道纪律：脚本清掉 WorkBuddy 注入的 env 代理（让 git 回落读 .gitconfig 的 **7890**）；`.gitconfig` 的 7890 **建议保留**（它是可靠通道之一），但若已删除，**直连+自动重试同样可能走通**——按出口矩阵动态选通道，别把任何一条通道当"唯一"。弹窗防护始终用 `-c credential.helper=`。
- 若推送中仍异常 → 去看 `github-connect-diag`（网络/凭据深度诊断）。

---

## 反模式（勿做）

- ⚠️ **删掉 / 设空 .gitconfig 的 `http.proxy=7890`** → 不算"环境坏了"，但要清楚后果：git 将只走直连，而**直连时通时断**；7890 是可靠通道之一，**建议保留**。（注意：脚本清 WorkBuddy 注入的 env 代理隧道是**另一回事**，属正常且必要。）真正致命的历史误区是**通道单点化 + 一次失败就判死**——任何通道失败都要换通道重试。
- ❌ **改 PortableGit 系统级 `etc/gitconfig`**（删 helper-selector）→ WorkBuddy 更新会覆盖，且影响其自身机制。在全局覆盖即可。
- ❌ **无 token 裸 push 私有仓库后干等** → 必然弹窗挂死。先确保 remote 内嵌 token。
