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

**⚠️ 动手前先验 token（30 秒，省掉半小时瞎折腾）**：

```python
import os, ssl, json, urllib.request, urllib.error
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7890'}),
                                 urllib.request.HTTPSHandler(context=ctx))
req = urllib.request.Request('https://api.github.com/user',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'User-Agent': 'wb'})
try:
    print('token OK:', json.loads(op.open(req, timeout=20).read())['login'])
except urllib.error.HTTPError as e:
    print('token 被拒:', e.code, e.read().decode()[:80])   # 401 Bad credentials → 换 token，别再试网络
```
**401 Bad credentials = token 过期/被吊销**（2026-09-28 实测：`ghp_` 40 位，`Bearer` 与 `token`
两种前缀都 401）。此时 git push 与 Contents API **两条路都会失败** → 直接找用户换新 PAT，
不要重试、不要怀疑网络。注意区分：**HTTPError(401) 是服务器明确答复（说明网络那一刻是通的）**，
而 `URLError` / `SSLEOFError` 才是网络问题；两者会在同一轮里交替出现，别都当抖动重试。

> ⚠️ 若 `GH_TOKEN` 未设置，脚本会明确报错并拒绝执行，绝不触发 GCM 弹窗。

## 反模式（务必避免）
1. **不要用 curl 判断网络** —— WorkBuddy 劫持 curl（`CODEBUDDY_*`），`exit 43 / HTTP 000` 假失败。用 Python urllib 判断。
2. **不要手动 `env -u http_proxy` 清代理后裸直连** —— 本用户墙内 github **必须走 7890(Clash) 代理**才通。注意区分：脚本 `run()` 会清掉 WorkBuddy 注入的 `127.0.0.1:51141` env 代理隧道（github 不通），清后 git **回落读 .gitconfig 的 `7890`**（通）。即：清的是 WorkBuddy 的坏隧道、保留的是你的 7890 好代理，git 最终走 7890。**切勿手动把 .gitconfig 的 7890 也删了**——那才真的连不上。
3. **GCM(credential manager)** 在无交互环境会弹 `credentialhelperselector` 或挂死。remote 无内嵌 token 时尤其触发。脚本禁用 GCM（`-c credential.helper=`）+ 从 env/URL 读 token，不弹窗。**若频繁弹窗，先跑 `github-env-fix` 根治全局配置**。
4. 推送失败别急着改 git 配置 —— 先看 `github-connect-diag` skill 做根因诊断，或先跑 `github-env-fix` 修环境，再决定走哪条路。
5. **先分清"是哪一层不通"：做域名级出口矩阵**（2026-09-28 实测）。同一代理下 `github.com` 不通、
   而 `api.github.com` 通是完全可能的（clash 规则/节点差异）—— 别测一次就判"网络全断"、更别去动
   `.gitconfig`。必须用 Python urllib + 显式 ProxyHandler（curl 的 000 是假失败）逐域名测：
   `api.github.com/rate_limit` / `github.com` / `codeload.github.com` / `www.baidu.com`（对照组）。
   判读：baidu 通 + `github.com` 报 `SSL: UNEXPECTED_EOF_WHILE_READING` → **代理节点/规则问题**
   （让用户切节点，等恢复），此时 git push 与 API 全废，唯一正确动作是**把改动 commit 在本地**并如实告知；
   api 通而 github.com 不通 → 可走 Contents API 路径。
   若 `git ls-remote` 直连超时、走 7890 TLS EOF、且 `dangerouslyDisableSandbox` 下同样如此，
   即可排除沙箱限制，直接判定为用户侧出口问题（不要再反复重试同一命令）。
6. **Contents API 回退前先看工作区有没有大体积 ignored 产物**（`dist/` `build/` `*.zip` `_build_env/`）。
   差集基线是 `os.walk` **整个工作区、不认 `.gitignore`**：本仓库 `dist/` 有 12MB zip ×N + 上千文件，
   直接 `--force-contents` 会把构建产物全推上远端。要么先把产物挪出仓库，要么只手工 PUT 本次改动的
   路径白名单（推荐后者：脏数据面最小）。
7. **⚠️ 别把「显示层脱敏」误判成「token 到不了命令行」**（2026-09-28 实测，**这条能省掉一小时弯路**）。
   现象：把 PAT 放进命令后，回显的 `Command:` 行与 stdout 里，PAT 形态的串会变成**另一个短串**
   （例：40 字符的 PAT 显示成 24 字符）。**但执行层拿到的是真值** —— 一条命令即可验证长度：

   ```bash
   T="ghp_"AAAA"BBBB"CCCC"DDDD"EEEE"FFFF"GGGG"HHHH   # 或直接把你手上的 PAT 赋给 T
   echo "${#T}"        # classic PAT 规范应为 40；返回 40 ⇒ 执行层拿到的是真 token，脱敏只发生在显示层
   ```

   **判读（关键）**：
   - `${#T}` = 40 → 执行层是**真 token** → 之后若 push 失败，就是**真失败**，按下面的 401 流程走，
     **不要再怀疑"环境把 token 换了"**。
   - 若确实出现写入文件为 0 字节 / 执行层收到短串（罕见）→ 才走「用户写文件 + `credential.helper=store`」兜底：

     ```bash
     # 用户手动创建，内容一行：https://x-access-token:<PAT>@github.com
     git -c credential.helper= \
         -c 'credential.helper=store --file=<仓库外凭据文件>' \
         -c http.sslVerify=false -c http.proxy=http://127.0.0.1:7890 \
         push https://github.com/<owner>/<repo>.git main
     ```

8. **`Invalid username or token. Password authentication is not supported` / API `401 Bad credentials`
   = 真实认证失败，不是网络、也不是"token 被掩码"**（2026-09-28 实测）。
   先用 Python urllib 问 `api.github.com/user`（脚本见本 skill 的 `probe_token.py` 思路）——
   **服务器能答复 401 ⇒ 那一刻网络是通的**，此时唯一正确动作是**找用户换一个有效 PAT**（需 `repo` scope），
   别去反复重试 push、也别改 .gitconfig。注意与 `URLError`/`SSLEOFError` 区分：后者才是网络抖动。

9. **直连 vs 代理都要试，且要「自动重试」**（2026-09-28 实测）：同一分钟内连跑 3 次
   `git ls-remote`（走 `http.proxy=127.0.0.1:7890`）可能 **1 次通、2 次 `TLS ... unexpected eof`**；
   而 `api.github.com` 走同一代理却可能稳定可通 → **按域名分别判断**。
   → 别一次失败就判死；写成 `for i in $(seq 1 8)` 重试，并用
   `ls-remote` 的远端 HEAD 是否等于本地 HEAD 作**成功判据**（不要只看 push 的 stdout 尾巴）。

## ⚠️ 只改一两个文件时：**别 clone**，直接走 Contents API（2026-09-28 实测）

github 通道**时通时断**（同一小时内能"全通 → 全挂 → 全通"）。此时：

| 路径 | 需要的请求数 | 暴露在抖动下的窗口 |
|---|---|---|
| `git clone` | 1 次握手 + 拉几千个对象 | **很长**（本轮连试 10 次全败） |
| Contents API 单文件改 | **2 次**（GET 拿 sha → PUT） | 很短（同一分钟里就成功了） |

**做法**：`GET /repos/{o}/{r}/contents/{path}` 取 `sha` + base64 内容 → 改 → `PUT` 带上
`{message, content(base64), sha, branch}`。多文件就先扫一遍（对候选路径各 GET 一次，grep 出引用），
再逐个 PUT。**一次 PUT 就是一个 commit**（GitHub 固有限制），改多处就说清"这几次 commit 同属一件事"。

配套纪律：
- 外层套**持久重试循环**（`for i in 1..30; do python patch.py && break; sleep 20; done`）——
  一次失败不代表这条路不行，是网络又抖了；本例第 22 轮才通。
- PUT 前先判"是不是已经改过了"（新内容已在、旧内容不在 → 直接 exit 0），否则重试循环会反复踩空报错。

## 只读核验：github 通道全死时用 jsDelivr 把整个仓库取回来（2026-09-28 实测）

**场景**：`github.com` / `api.github.com` 的 HTTPS 全不通（git clone、API 全废），
但你只是想**读远端代码做核验**（不需要 token）。jsDelivr 是独立出口，可绕过：

```python
# 1) 完整文件清单（每个条目带 size，用来逐一对账）
GET https://data.jsdelivr.com/v1/packages/gh/<owner>/<repo>@<ref>   # ref 可直接用分支名
# 2) 逐文件取内容（严格打印进度，别让它静默跑）
GET https://fastly.jsdelivr.net/gh/<owner>/<repo>@<ref>/<path>
```

要点（都是实测换来的）：
- **镜像要逐个试**：本机 `fastly.jsdelivr.net` 通，`cdn.` / `gcore.` / `testingcf.` 全 `000` → 别只试 `cdn.`。
- **`data.jsdelivr.com` 也通**，所以"先列后取"两步都走 jsDelivr，不碰 github。
- **落盘后逐个比字节数**（清单里的 `size` vs 实际写入字节）—— 全等才叫"取到真文件"；
  本轮 15 个文件全部吻合，且据此实机跑通了程序。
- **非 ASCII 文件名会 `403 Forbidden`**（例：`启动日历.bat`）→ 这类文件改用 WebFetch 读，或放弃。
- 取回目录**没有 `.git`，但足以实机运行验证**（起服务 + 打 `/health` + 无头浏览器截图），
  对"这仓库 clone 下来到底能不能复现"这类问题，这比读代码有说服力得多。
- **必须写重试**：沙箱出口会偶发 `502 Bad Gateway`；且**长循环放 `run_in_background`** ——
  前台跑网络长循环会被 SIGTERM 掐掉（同一脚本后台跑就正常）。

### 附带结论：匿名**无法**判断某个仓库是「私有」还是「不存在」（2026-09-28 对照实验）

想确认 `<owner>/<repo>` 到底存在与否时，别用匿名请求下结论 —— GitHub 故意不区分：

| 目标 | 匿名 smart-HTTP 响应 |
|---|---|
| 已知存在的公开仓库 | `200` + refs 数据 |
| 待查仓库 | `401` `Repository not found.` |
| **随便编的名字（对照组）** | `401` `Repository not found.`（**与待查仓库字节相同**） |

`git ls-remote` 同理，两者都是 `fatal: could not read Username`。
→ **正确做法**：必须用**有效 token** 打 `GET /repos/<owner>/<repo>`（200 = 私有仓库确实存在；
404 = 真的不存在）。token 无效时先跑本 skill 的 token 自检，**别把 401 当成"仓库不存在"**。

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

## ⚠️ git 通道其实可用时：优先 git，别默认走 API（2026-09-21 实测）

**背景**：同一天里 git push 三连败（7890 死 / 直连抖动 / 沙箱代理 502），改走 Contents API 成功；
但同一次会话稍后 `git clone` **直连就成功了**，push 也随之走通。**github.com 的直连是间歇性的**，
不是"永久不通"——失败后隔一阵子重试，或先跑 `git clone --depth 1` 探活。

**恢复后走 git 的正确姿势**（`credential.helper=` 被禁用时，必须自带 token，否则报
`could not read Username for 'https://github.com'`）：

```bash
# 1) 先探活 + 取远端完整 SHA
git -c http.proxy= -c https.proxy= ls-remote origin main
# 2) force-with-lease 覆盖（本地链替换 API 生成的逐文件小 commit 链）
git -c http.proxy= -c https.proxy= -c http.sslVerify=false -c credential.helper= \
    push --force-with-lease=refs/heads/main:<完整40位SHA> \
    "https://x-access-token:${GH_TOKEN}@github.com/<owner>/<repo>.git" main
```
- ⚠️ `--force-with-lease=main:fc09913`（短 SHA）会报 `cannot parse expected object name`
  —— **必须完整 40 位**。
- 覆盖前先确认：本地 HEAD 树与远端树内容一致（本轮实测 104 文件全等），这样 force 只规整历史、不动内容。
- 覆盖后 `git fetch origin main` 刷 `origin/main`（git 通道下 fetch 正常），`git status` 即可干净。

## 验证清单（推送后）
- [ ] 远端文件树已含预期文件：`GET /repos/{o}/{r}/git/trees/{branch}?recursive=1`
- [ ] 远端分支最新 commit sha 已更新
- [ ] 本地 `git status` 干净、HEAD 与远端一致

## ⚠️ Contents API 路径也会推 untracked/被 ignore 的工作区文件（2026-09-21 实测）

**症状**：`--force-contents` 推送时把工作区里的 untracked 临时文件（`panels/MountainSpectrum/_c.js`，
v1.1.2 旧副本，已加进 .gitignore）一并 PUT 到了远端。

**根因**：Contents API 路径的差集基线不是纯 git HEAD 树——工作区里存在的文件（哪怕 untracked /
已被 .gitignore 覆盖）会被扫描进「本地有」集合。.gitignore 只挡 `git add -A`（git 路径），挡不住 API 扫描。

**绕过**：
- push 前把临时文件**物理移出仓库目录**（最稳），或
- push 后用 Contents API 单独 DELETE 误推文件：
  `DELETE /repos/{o}/{r}/contents/<path>` + body `{message, sha(文件的 blob sha), branch}`
- 对照核验用 `GET /git/trees/{branch}?recursive=1` 的 blob 集合 vs `git ls-tree -r --name-only HEAD`。
  注意：git ls-tree 对中文/特殊路径输出带引号的八进制转义（`"\346..."`），与 GitHub 树的原始 UTF-8 路径
  直接字符串对比会假性不一致——先 unescape 再比，别误判。

## ⚠️ update-ref 后本地 ref 卡在旧 hash 的坑（2026-09-08 实测）

**症状**：脚本最后一步 `update-ref refs/heads/main refs/remotes/origin/main` 后，`git log origin/main` 仍显示旧的 commit 链（不是刚 push 的），
`git rev-parse origin/main` 返回旧 SHA。本地 main 指向新 commit，但 `origin/main` 引用停在旧值 → `git status` 报本地 ahead/behind 错乱。

**根因**：脚本的 `git fetch` 在某些环境下（7890 代理 + packed-refs 已存在）不会更新 `.git/refs/remotes/origin/main`，只更新 FETCH_HEAD。`update-ref refs/heads/main refs/remotes/origin/main` 把本地 main 拉到的是**旧的** origin/main SHA（脚本启动前的 view）。

**复现**：本机 v0.7.4 push 时 fetch 返回 0，但 `refs/remotes/origin/main` 未刷新。`git ls-remote origin main` 已显示新 SHA，`.git/packed-refs` 仍含旧 hash。

**3 种绕过（按优先级）**：
1. **传 `--git-only`** 跳过 update-ref 步骤，跑完自己 `git fetch && git merge --ff-only origin/main`。**这是首选**。
2. push 后手动验证 `git ls-remote origin <branch>` = 新 SHA；若 `git rev-parse origin/<branch>` 还是旧 SHA：
   ```bash
   sed -i 's|^<old_sha> refs/remotes/origin/<branch>$|<new_sha> refs/remotes/origin/<branch>|' .git/packed-refs
   git merge --ff-only origin/<branch>
   ```
3. 删 `.git/packed-refs`（`git gc` 后会自动重建）—— 暴力但有效。

## ⚠️ push_repo.py 默认 `git add -A` 会自动 commit 未跟踪辅助文件（2026-09-08）

**症状**：本轮 push 时把开发期临时生成的 `clipboard-exe/Assets/app_sizes.png`（109KB Pillow 检视图）当 untracked 自动 commit 推到 origin。这不该进库（仅是肉眼验多帧用）。

**根因**：脚本默认 `git add -A` 把所有 untracked 一并提交。

**绕过**：
- 先在 `.gitignore` 加 `clipboard-exe/Assets/app_sizes.png`（或类似辅助文件模式），再 push。
- 或 `git add <path1> <path2>...`（手动精确），再 `push_repo.py ... --git-only`（让脚本只 push 不 commit）。

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
