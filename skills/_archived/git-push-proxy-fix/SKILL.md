---
name: git-push-proxy-fix
description: 诊断并修复 "git push 到 GitHub 反复失败，但代理/Clash 测速正常" 的问题——根因通常是 git 全局配置残留针对 github.com 的「空代理覆盖」（http.https://github.com.proxy=），强制 git 直连被墙域名。当用户要求"推送到 GitHub / push 失败 / 连不上 / 认证失败 / 一直不通"且代理本身看起来正常时使用。覆盖:可靠连通验证（避开 PowerShell curl -w 假失败）→ 定位空代理覆盖 → 删除修复 → 成功判定。已验证于 Simiely/content-archive（2026-09-02）。与 github-contents-api-push 互补:本技能解决"git 通道可修复"的情形,若验证后发现 git push 无论怎么配都连不上且 api.github.com 可达,再切 Contents API。
agent_created: true
version: 1.0.0
status: archived
---

> ## ⚠️ 已归档（2026-09-03）
> 本技能已被 **`github-connect-diag`**（skills/ 下）吸收替代。git-push-proxy-fix 聚焦的「空代理覆盖」根因已作为 github-connect-diag 的兜底诊断分支收录，且补充了 7890 代理挂起 / GCM 弹窗 / curl 劫持等更全的症状对照。
> 本目录保留完整历史正文供查阅（含 PowerShell `curl -w` 假失败细节）。**新用请用 `skills/github-connect-diag`。**

# Git 推送代理修复（git push 失败但代理正常时的诊断与修复）

## 适用场景

用户说"推送到 GitHub / push 失败 / 连不上 / 认证失败 / 一直不通"，且具备以下矛盾特征时命中本技能：

- **Clash/代理测速正常**（用户视角代理没问题）
- 用 curl 走代理访问 GitHub **可以通**（`curl.exe -s -x http://127.0.0.1:7890 https://api.github.com/user` 返回 200）
- 但 **`git push` 失败**，报以下任一：`Failed to connect to github.com:443 after 21122 ms`（超时）、`Recv failure: Connection was reset`（被重置）、`Authentication failed`

**核心结论（实测 2026-09-02，content-archive）**：这种"curl 通 / git 不通"的组合，根因几乎都是 **git 全局配置里残留了针对 github.com 的空代理覆盖**——`http.https://github.com.proxy=`（空值）会让 git 对 github.com **强制直连、不走代理**，直连被墙所以必失败。**不是代理/Clash 的问题**，改 git 配置即可。

**失败现象到决策（不要反复重试 git push）**：
- `curl`（无 `-w` 写法）走代理能 200 → 代理与域名都通，**问题在 git 侧** → 走本技能 A 主线
- `curl` 走代理也 000/超时 → 代理或网络问题，先处理代理（切 Clash 节点）再回来
- git 怎么配都连不上、但 `api.github.com` 可达 → 切 [github-contents-api-push](../../github-contents-api-push/SKILL.md)（Contents API 逐文件 PUT）

## 前置准备

- Token：用户提供（格式 `ghp_xxx`），仅以环境变量或 remote URL 形式使用，**绝不写进任何被提交的文件**
- 代理：git 全局 `http.proxy`/`https.proxy` 指向本地代理（如 `http://127.0.0.1:7890`），直连 GitHub 被网络环境拦截时必须走代理

## A 主线（诊断 → 修复 → 验证）

### A1. 可靠地验证"走代理能通"（先排除网络/代理问题）

> ⚠️ **PowerShell 大坑（实测 2026-09-02）**：`curl.exe -w "%{http_code}"` 里的 `%{...}` 会被 PowerShell 当作脚本块解析，导致 curl 收到坏参数报 `A libcurl function was given a bad argument`（exit 43）并输出 `000`——**这是假失败，不是网络问题**。之前所有用 `-w` 测的 `000` 都不可信。

**不要用** `-w "%{http_code}"` 写法。用以下任一可靠方式：

```powershell
# 方式一：不带 -w，输出 body，EXIT=0 即通（推荐）
curl.exe -s -m 15 -x http://127.0.0.1:7890 -H "Authorization: Bearer $env:GITHUB_TOKEN" https://api.github.com/user
# 返回 JSON 且 EXIT=0 → 通；返回空/EXIT 非 0 → 不通

# 方式二：下载到文件看大小
curl.exe -s -m 20 -x http://127.0.0.1:7890 -o gh_test.html https://github.com/
# EXIT=0 且文件大小 >0 → 通（如 github 首页约 573KB）

# 方式三：PowerShell 原生（走系统代理）
(Invoke-WebRequest -Uri "https://api.github.com/user" -Headers @{Authorization="Bearer $env:GITHUB_TOKEN"} -TimeoutSec 10 -UseBasicParsing).StatusCode  # 200 即通
```

产出：确认「curl 走代理通、git push 不通」→ 问题定位到 git 侧，继续 A2。

### A2. 检查 git 全局配置的「代理覆盖」

```powershell
git config --global -l | Select-String -Pattern "proxy|github.com"
```

**命中特征**（根因所在）：
```
http.proxy=http://127.0.0.1:7890
https.proxy=http://127.0.0.1:7890
http.https://github.com.proxy=        ← 空值！对 github.com 强制直连
https.https://github.com.proxy=       ← 空值！
```

带 `https://github.com.proxy` 且**值为空**的行，就是"git 对 github.com 不走代理"的元凶。这些行通常是历史遗留或某次误配置写入的。

### A3. 删除空代理覆盖（修复）

```powershell
git config --global --unset-all "http.https://github.com.proxy"
git config --global --unset-all "https.https://github.com.proxy"
```

验证已删：
```powershell
git config --global -l | Select-String -Pattern "github.com.proxy"   # 无输出 = 已删干净
git config --global --get http.proxy                                  # 应仍返回 http://127.0.0.1:7890
```

### A4. 重试推送 + 成功判定

```powershell
cd <repo>
git push origin main
```

**成功判定（PowerShell 坑）**：git 的输出走 stderr，PowerShell 会把 `To https://...` 误报为 `RemoteException`（红色报错），**不代表失败**。真正的成功标志是最后一行出现：
```
<old>..<new>  main -> main
```
例如 `9fb8ecf..eb85fdf  main -> main`。看到这个就是推送成功。

远端复核（可选）：
```powershell
git status -sb   # 显示 ## main...origin/main（同步）即完成
curl.exe -s -m 15 -x http://127.0.0.1:7890 -H "Authorization: Bearer $env:GITHUB_TOKEN" "https://api.github.com/repos/<owner>/<repo>/commits?per_page=3" | Select-String -Pattern '"message"' | Select-Object -First 3
```

## B 工具库（按需）

### B1. 若 A4 仍失败——检查 remote URL 与认证
```powershell
git remote -v   # 确认 remote URL 内嵌了 token 或用 credential manager
git config --global --get credential.helper
```
- remote URL 内嵌 token：`https://x-access-token:ghp_xxx@github.com/<owner>/<repo>.git`
- 若用 credential manager 但认证失败，优先改用内嵌 token 的 URL（`git remote set-url origin ...`）

### B2. 若 git 走代理本身有疑问——手动验证 git 的实际连接
```powershell
GIT_TRACE=1 git -c http.verbose=true push origin main 2>&1 | Select-String -Pattern "proxy|CONNECT|error"
```
确认 git 确实把请求发给了 `127.0.0.1:7890`（而非直连 github.com）。

### B3. 与 Contents API 的分流判断
- 本技能走通（删空覆盖后 push 成功）→ 完事，无需 Contents API
- 删完仍 `Connection reset`/`Could not connect` 且 `api.github.com` 可达 → 网络环境彻底不通 git 通道，切 [github-contents-api-push](../../github-contents-api-push/SKILL.md)

## C 检查与沉淀

**代码/配置审查点**：
- [ ] 确认 `curl`（无 `-w`）走代理访问 github 确实 200，再下"git 侧问题"结论
- [ ] `git config --global -l` 里没有残留 `http.https://github.com.proxy=` / `https.https://github.com.proxy=` 空值
- [ ] 删除空覆盖后全局 `http.proxy`/`https.proxy` 仍指向本地代理
- [ ] push 输出看到 `old..new main -> main`（不是被 RemoteException 误导判失败）

**流程合规点**：
- [ ] token 未写入任何被提交的文件
- [ ] 未反复盲目重试 git push（同一动作失败两次就换诊断通道）
- [ ] 根因/修复过程沉淀：本仓库 CHANGELOG + AGENTS 关键坑；content-archive 侧同步记入 AGENTS.md 关键坑

**落盘规范**：本次修复是全局 git 配置变更（`--global`），影响用户所有仓库——执行前告知用户；修复后把该坑记入 AGENTS 关键坑，防止复发。

## 实战要点（2026-09-02，Simiely/content-archive 验证）

- 现象：连续 3 次 push 失败（超时 21s → Connection reset → Authentication failed），Clash 测速正常、curl 走代理访问 github 通
- 根因：`git config --global -l` 里有 `http.https://github.com.proxy=` 与 `https.https://github.com.proxy=` 两行**空值覆盖**，git 对 github.com 强制直连被墙
- 修复：两条 `--unset-all` 删除后，push 一次成功（`9fb8ecf..eb85fdf main -> main`）
- 附带发现：PowerShell 下 `curl -w "%{http_code}"` 因 `%{}` 被 PS 解析而报 bad argument（exit 43）假失败 000，排查全程被误导——验证连通务必避开该写法
