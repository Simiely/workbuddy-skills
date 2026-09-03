---
name: github-env-fix
description: 在 WorkBuddy 沙箱 / Windows 无交互环境里，推送或发布 GitHub 之前，先做"环境就绪检测 + 修复"。核心是根治 git 凭据弹窗 credentialhelperselector/GCM（设全局 credential.helper=），并确认保留 7890(Clash) 代理（墙内必须走代理才能连 github，绝不"清代理直连"）。用户说"先修环境 / 推送前准备 / 又弹窗了 / git 环境有问题 / 环境就绪"时先跑本 skill，跑完再走 github-push-universal 或 github-release。
agent_created: true
version: 1.0.0
---

# GitHub 推送前环境修复（env-fix）

> ⚠️ **必须先读本节，它修正了历史错误认知。** 曾误以为"git 走 7890 代理会挂起、清代理直连才通"，并在旧 skill 里写入 `env -u http_proxy` 清代理。**这是错的**。实测证明：用户是**墙内环境，必须走 7890(Clash) 代理才能访问 github**，走代理**必通**；真正让 git 卡死/弹窗的是 **credential helper（helper-selector/GCM）**，不是代理。

## 本 skill 定位

- 它是 `github-push-universal`（推代码）与 `github-release`（发版本）的**前置步骤**。
- 职责：**先把 git 环境修到"能稳定走代理 push、不弹窗"**，再交棒给兄弟 skill。
- 触发时机：推送/发布**之前**，或用户报"又弹 credentialhelperselector / git 环境有问题 / 推送前先修一下"。

---

## 正确基线（本机事实，勿改）

1. **git 来源**：唯一 git 是 WorkBuddy 自带 `PortableGit`（当前 `C:/Users/260803/.workbuddy/binaries/PortableGit/versions/1.2.0/`）。无系统 Git。
2. **网络**：墙内，**必须走 `127.0.0.1:7890`(Clash) 代理**访问 github。走代理访问 github 实测**必通**（公开仓库、remote 内嵌 token 均正常返回）。
3. **唯一真正的故障源**：git 需要凭据时，被 PortableGit 系统级 `etc/gitconfig` 的 `credential.helper = helper-selector` 拦截 → 弹 `credentialhelperselector` / GCM 凭据窗；无 tty 的沙箱会话里弹窗即**挂死**。
   - 触发条件：remote **无内嵌 token**，且目标需凭据（如私有仓库写操作）。
   - 系统级 `helper-selector` 由 PortableGit 出厂预设（`git-credential-helper-selector.exe`），**不要改系统级 gitconfig**（WorkBuddy 更新会覆盖）；在**全局** `~/.gitconfig` 覆盖即可。
4. **token**：内嵌在 remote URL（`https://x-access-token:<PAT>@github.com/...`）或环境变量 `GH_TOKEN`。带 token 时 helper 完全不介入，无需任何弹窗。

---

## 就绪检测清单（按序执行，全绿才算就绪）

```bash
# 1) git 存在且版本可用
git --version

# 2) 是否有弹窗 helper 残留（命中任一即需修复）
git config --global --get-regexp 'credential'          # 若 credential.helper 非空 / 有 helperselector.selected → 需修
git config --show-origin --get credential.helper        # 系统级 helper-selector 是 PortableGit 预设，不碰系统级

# 3) 代理配置仍在（必须保留 7890，别删）
git config --global --get http.proxy                    # 期望 http://127.0.0.1:7890
git config --global --get https.proxy                   # 期望 http://127.0.0.1:7890

# 4) 实测连通（走代理 + 禁 helper，测网络本身；应返回 ref 而非挂起/弹窗）
GIT_TERMINAL_PROMPT=0 timeout 25 git -c credential.helper= \
  ls-remote https://github.com/git/git.git HEAD

# 5) token 是否有效（如有 remote 内嵌 token 或 GH_TOKEN）
git -c credential.helper= ls-remote "https://x-access-token:<PAT>@github.com/<owner>/<repo>.git" HEAD
```

判定：
- 第 4 步公开仓库通 → **代理/网络 OK**，问题只在凭据弹窗 → 执行下方「修复 A」。
- 第 4 步不通（走代理仍挂/报错）→ 才去看 `github-connect-diag` 的网络诊断（罕见；本机事实是走代理必通）。

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

**回滚**：若需恢复，`git config --global credential.helper "!C:/Users/260803/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin/git-credential-wincred.exe"`（或从备份 .gitconfig.bak 还原）。

---

## 修复后交棒

- 就绪清单全绿 → 交给 **`github-push-universal`**（推代码）或 **`github-release`**（发版本）。
- 这两个兄弟 skill 已按本基线修正：脚本会清掉 WorkBuddy 注入的 env 代理（让 git 回落读 .gitconfig 的 **7890** 走代理），**绝不删 .gitconfig 的 7890**、只用 `-c credential.helper=` 禁弹窗。
- 若推送中仍异常 → 去看 `github-connect-diag`（网络/凭据深度诊断）。

---

## 反模式（勿做）

- ❌ **删掉 / 设空 .gitconfig 的 `http.proxy=7890`** → 你墙内必须走 7890 才连得上 github，删了才真连不上。这是历史最大误区。（注意：脚本清 WorkBuddy 注入的 env 代理隧道是**另一回事**，清后 git 仍回落用 .gitconfig 的 7890，属正常且必要。）
- ❌ **改 PortableGit 系统级 `etc/gitconfig`**（删 helper-selector）→ WorkBuddy 更新会覆盖，且影响其自身机制。在全局覆盖即可。
- ❌ **无 token 裸 push 私有仓库后干等** → 必然弹窗挂死。先确保 remote 内嵌 token。
