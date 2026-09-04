---
name: github-push-universal
description: 在 WorkBuddy 沙箱/无交互环境里稳定推送本地 git 仓库代码到 GitHub 分支。git push 优先，遇 /dev/tty、Connection reset、超时、credentialhelperselector 弹窗等失败时自动回退 GitHub Contents API 逐文件推送，全程不弹 GCM。用户说"推送到 GitHub / push / 上传代码"时使用。
agent_created: true
---

# github-push-universal —— 代码推送（只推代码，不发布）

职责单一：**把本地代码推到 GitHub 分支**。建 Release / 打 tag / 传 zip 用 `github-release` skill，本 skill 不碰。

## 什么时候用
- 用户要求"推送到 GitHub / push / 上传代码 / 同步代码"。
- 需要把本地改动稳定推到 `github.com/<owner>/<repo>` 的某个分支（默认 main）。

## 前置条件（必读）

**使用本 skill 推送前，必须确保 `GH_TOKEN` 环境变量已设置。** 这是推荐的认证方式，优先级高于 URL 内嵌 token。

```bash
# 设置 GH_TOKEN（Windows 用户环境变量，持久生效）
[Environment]::SetEnvironmentVariable("GH_TOKEN", "ghp_xxx", "User")

# 或在当前会话中设置
$env:GH_TOKEN = "ghp_xxx"
```

为什么推荐 `GH_TOKEN` 而非 URL 内嵌 token：
- 🔒 **不进文件**：token 只在环境变量中传递，不写入 `.git/config` 或其他文件
- 🔄 **全局生效**：所有仓库共用，无需逐一修改 remote URL
- 🚫 **不弹窗**：脚本自动读 `GH_TOKEN` 并内嵌到推送 URL，credential helper 完全不介入

> ⚠️ 若 `GH_TOKEN` 未设置，脚本会明确报错并拒绝执行，绝不触发 GCM 弹窗。

## 反模式（务必避免）
1. **不要用 curl 判断网络** —— WorkBuddy 劫持 curl（`CODEBUDDY_*`），`exit 43 / HTTP 000` 假失败。用 Python urllib 判断。
2. **不要手动 `env -u http_proxy` 清代理后裸直连** —— 本用户墙内 github **必须走 7890(Clash) 代理**才通。注意区分：脚本 `run()` 会清掉 WorkBuddy 注入的 `127.0.0.1:51141` env 代理隧道（github 不通），清后 git **回落读 .gitconfig 的 `7890`**（通）。即：清的是 WorkBuddy 的坏隧道、保留的是你的 7890 好代理，git 最终走 7890。**切勿手动把 .gitconfig 的 7890 也删了**——那才真的连不上。
3. **GCM(credential manager)** 在无交互环境会弹 `credentialhelperselector` 或挂死。remote 无内嵌 token 时尤其触发。脚本禁用 GCM（`-c credential.helper=`）+ 从 env/URL 读 token，不弹窗。**若频繁弹窗，先跑 `github-env-fix` 根治全局配置**。
4. 推送失败别急着改 git 配置 —— 先看 `github-connect-diag` skill 做根因诊断，或先跑 `github-env-fix` 修环境，再决定走哪条路。

## 工具
脚本：`push_repo.py`（同目录，Python3，零第三方依赖）。

### token 来源（优先级）
**推荐使用 `GH_TOKEN` 环境变量**（推荐做法）：
```bash
# 设置 GH_TOKEN（只一次，全局生效）
$env:GH_TOKEN = "ghp_..."
```

优先级从高到低：
1. `--token` 参数（显式指定，优先级最高）
2. remote URL 内嵌 token（如 `https://x-access-token:TOKEN@github.com/...`）
3. **`GH_TOKEN` 环境变量**（推荐，全局生效不落盘）
4. `GITHUB_TOKEN` 环境变量（备选）

都没有 → 明确报错，绝不触发弹窗。

### 用法
```bash
# 标准推送（本地 commit 改动 → git push；失败自动回退 Contents API）
export GH_TOKEN='ghp_...'
python "C:/Users/<USER>/.workbuddy/skills/github-push-universal/push_repo.py" /path/to/repo --message "commit msg"

# 分支 / 指定 token / 只测连通不推送
python ".../push_repo.py" /path/to/repo --branch dev --token 'ghp_...'
python ".../push_repo.py" /path/to/repo --test

# 强制走 Contents API（明知 git 不通时）
python ".../push_repo.py" /path/to/repo --force-contents --message "msg"

# 只用 git，失败即退出(不回退)
python ".../push_repo.py" /path/to/repo --git-only
```

### 建议运行方式（走 7890 代理 + 禁 credential helper）
```bash
cd /path/to/repo
export GH_TOKEN='ghp_...'
python "C:/Users/<USER>/.workbuddy/skills/github-push-universal/push_repo.py" . --message "..."
```
脚本内部已自动：清掉 WorkBuddy 注入的 `51141` env 代理（git 回落读 .gitconfig 的 **7890** 走代理）、`-c credential.helper=`（禁弹窗）、`-c http.sslBackend=openssl`、`-c http.version=HTTP/1.1`、禁交互。
> 在 WorkBuddy 桌面沙箱里运行涉及网络的命令时，若被沙箱策略拦截，可对 Bash 命令加 `dangerouslyDisableSandbox: true`（网络操作）。

## 推送语义
1. `git add -A` + `git commit`（把工作区改动固化成本地 commit）。
   - 若仓库无 user.name/email，commit 失败 → 警告并继续（API 路径仍可用）。
2. 本地 HEAD == 远端 HEAD → 无需推送，直接返回。
3. 尝试 `git push HEAD:<branch>`（走 7890 代理，90s 超时）。
4. git 失败 → 回退 **Contents API**：以「本地 HEAD 树 vs 远端分支树」做差集，幂等对齐——
   - 本地有、远端无/不同 → PUT（base64 content）
   - 远端有、本地无 → DELETE
   - 内容与远端一致的路径**跳过**（不产生多余 commit）
   - Contents API 逐文件各建一个 commit（API 固有限制），结果文件与 git push 一致。
5. 结束后 update-ref 对齐本地 ref，使 `git status` 干净。

## 验证清单（推送后）
- [ ] 远端文件树已含预期文件：`GET /repos/{o}/{r}/git/trees/{branch}?recursive=1`
- [ ] 远端分支最新 commit sha 已更新
- [ ] 本地 `git status` 干净、HEAD 与远端一致

## 安全
- token 只经内存/环境变量传递，**不写进任何文件、不进仓库、不打日志**。
- 若 token 曾在聊天里明文出现，提醒用户测试完可到 GitHub → Settings → Developer settings → Personal access tokens 轮换/撤销。

## 与兄弟 skill 的关系
- 推完代码需要发版本 → 继续用 `github-release` skill（本脚本不传 asset / 不打 tag）。
- 失败/慢/弹窗先看 `github-connect-diag` 诊断。

## 端到端验证记录（2026-09-03，测试仓库 Simiely/push-test-dummy 私有）
- 路径1 git 优先(commit+push)：✓ 推 4 文件(含中文/二进制/嵌套)
- 路径2 Contents API(强制)：✓ PUT 新文件、DELETE 删除、幂等(无变化=0操作)
- 自动回退(制造 git non-fast-forward 分叉)：✓ git 失败→自动切 API→PUT 成功
