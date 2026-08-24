---
name: github-contents-api-push
description: 在 WorkBuddy 沙箱内把本地 git 仓库推送到 GitHub 的可靠方案——git push 到 github.com:443 长期不通（/dev/tty 凭证错误 / Connection reset），改用 GitHub Contents API 逐文件 PUT 绕过。当用户要求"推送到 GitHub / push / 上传仓库 / 提交到远程"且 git push 失败时使用。覆盖:连通性探测→逐文件更新/新建/删除→远端验证→本地 ref 修正（packed-refs 坑）→knowledge-base 盘点表回填。已验证于 vray-material-replacer、knowledge-base（2026-08-15）、edge-multi-account-cookie（2026-08-24）。
agent_created: true
version: 1.1.0
---

# GitHub Contents API 推送（沙箱内 git push 不通时的可靠通道）

## 适用场景
用户要推送到 GitHub（`Simiely/*` 等个人仓库），但 `git push` 在沙箱内失败：
- `fatal: unable to auto-detect email address` —— 先 `git config user.name/email`（仓库级）
- `/dev/tty: No such device or address` —— git 凭证交互在沙箱无 tty，push 必失败
- github.com:443 Connection reset / 超时 —— 网络受限容器

**核心结论（实测 2026-08-15）**：`git push` 不可靠，但 `api.github.com` 间歇可达，**Contents API 逐文件 PUT 是稳定通道**。

**失败现象到决策（2026-08-24 实测，只记现象不臆断成因）**：
- 直连 `github.com:443`：`Could not connect to server`（**超时**）
- 设 `http.proxy` 后：`Recv failure: Connection was reset`（**被 reset**）
- 两者都只说明"`github.com` 域名当前不可达"；若 `api.github.com` 可达 → **直接切 Contents API，不要反复重试 git push**

## 前置准备
- Token：用户提供（格式 `ghp_xxx`，**本文件不写真实 token——GitHub Secret scanning 会拦截含 token 的推送**）。**只走环境变量，不落盘**：`GH_TOKEN="ghp_xxx" node script.js`
- 认证头：`Authorization: Bearer <token>`（经典 PAT 用 Bearer，不要 `x-access-token:` 前缀——那是 GitHub App 令牌用的）
- User-Agent 头必带：`'User-Agent': 'workbuddy'`（GitHub API 强制要求，缺了 403）

## 标准流程

### 1. 先试 git push（万一通了最省事）
```bash
cd <repo> && timeout 30 git push origin main 2>&1 | tail -5
```
若报 `/dev/tty` 或 Connection reset → 走 Contents API。**不要反复重试 git push**。

### 2. 连通性探测 + 取远端文件列表
```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/<owner>/<repo>/contents/" | head -c 2000
```
- 拿到每个文件的 `sha`（更新时需要）和 `path`
- 返回 401/403 → token 无效/限流，等窗口重试
- 返回列表 → 通，继续

### 3. 逐文件推送（Node 脚本，一次搞定更新+新建+删除）

**省请求优化（2026-08-24 实测）**：默认的逐个 `GET /contents/<path>` 取 sha（一个文件一次请求），可换成**一次** `GET /git/trees/{commit.tree}?recursive=1` 拿全部 blob sha——该 sha 与 `/contents/<path>` 返回的**完全一致**（实测 `manifest.json` 两法均为 `2d5b5d...`），PUT 更新直接复用这张表。收益是"少 N-1 次请求与往返"；**不是**为躲限流（认证核心任务 5000 次/时，普通规模远够不到）。
```js
async function getShasAll() {
  const head = await (await api('/git/ref/heads/' + branch)).json.object.sha;
  const tree = (await api('/git/commits/' + head)).json.tree.sha;
  const tr = await api('/git/trees/' + tree + '?recursive=1');
  const map = {};
  for (const it of (tr.json.tree || [])) if (it.type === 'blob') map[it.path] = it.sha;
  return map; // path -> blob sha，PUT 时 body.sha = map[path]
}
```

模板 `push_repo.js`（放工作目录临时用，token 走 env）：

```js
const fs = require('fs');
const token = process.env.GH_TOKEN;
const repo = '<owner>/<repo>';
const branch = 'main';
const base = 'https://api.github.com/repos/' + repo;

async function api(path, method, body) {
  const r = await fetch(base + path, {
    method: method || 'GET',
    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'workbuddy' },
    body: body ? JSON.stringify(body) : undefined
  });
  return { status: r.status, json: await r.json().catch(() => ({})) };
}

async function getSha(path) {
  const { status, json } = await api('/contents/' + path);
  return (status === 200 && json.sha) ? json.sha : null;
}

async function putFile(path, content, sha) {
  const body = { message: '<commit message>', content: Buffer.from(content, 'utf8').toString('base64'), branch };
  if (sha) body.sha = sha;  // 更新已有文件必须带 sha，否则 422
  const { status } = await api('/contents/' + path, 'PUT', body);
  return status;
}

async function deleteFile(path, sha) {
  const { status } = await api('/contents/' + path, 'DELETE', { message: '<msg>', sha, branch });
  return status;
}

(async () => {
  // 更新：取 sha 再 PUT
  for (const p of ['file1.ms', 'file2.md']) {
    const sha = await getSha(p);
    const content = fs.readFileSync('D:/workbuddy/<...>/<repo>/' + p, 'utf8');
    console.log(p, (await putFile(p, content, sha)) === 200 || 201 ? 'OK' : 'FAIL');
  }
  // 新建：sha 传 null
  // 删除：先 getSha
})().catch(e => console.log('NET ERR', e.message));
```

**要点**：
- 更新已有文件：**必须先 GET 取 sha**，PUT 带 `sha`，否则 422
- 新建文件：sha 省略（或 null）
- 删除文件：`DELETE /contents/<path>` body 带 sha + message + branch
- 中文文件名（如 `用户库/仓库盘点表.md`）：路径要 `encodeURIComponent`，但**斜杠不要编码**（只编码每段）
- 每次 PUT 生成一个独立 commit——远端会有多个 commit，属正常
- 逐文件串行执行（Contents API 无批量接口）

### 4. 远端验证
```bash
# 最新 commit
curl -s -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/<owner>/<repo>/commits/main" | node -e "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{const j=JSON.parse(d);console.log(j.sha, j.commit.message.split('\n')[0])})"
# 内容一致性（raw 域稳定可达，可作校验；注意 CDN 缓存延迟，以 API 为准）
for f in file1 file2; do
  local=$(md5sum "$f" | cut -d' ' -f1)
  remote=$(curl -s "https://raw.githubusercontent.com/<owner>/<repo>/main/$f" | md5sum | cut -d' ' -f1)
  [ "$local" = "$remote" ] && echo "一致: $f" || echo "★不一致: $f"
done
```

> **PowerShell 注意（2026-08-24 实测）**：`gh api --jq` 传**含 `|` / `\n` / 嵌套引号**的复杂 jq 会被转义打断（报 `unexpected token "\"`）；简单 jq（如 `--jq '.commit.message'`）可用。**复杂解析交给 Node/Python**，别把带管道/转义的 jq 塞进 `gh api --jq`。

### 5. 本地 ref 修正（packed-refs 坑，必做）
push 成功后本地 `git fetch origin` 可能**更新了 FETCH_HEAD 但 origin/main ref 没动**——`.git/packed-refs` 里写死了旧值，fetch/update-ref 被忽略。修正：

```bash
# 1) 从 packed-refs 移除 origin/main 行
grep -v "refs/remotes/origin/main" .git/packed-refs > .git/packed-refs.tmp && mv .git/packed-refs.tmp .git/packed-refs
# 2) 写 loose ref 指向远端真实 sha（上一步 API 查到的）
mkdir -p .git/refs/remotes/origin && echo "<远端sha>" > .git/refs/remotes/origin/main
# 3) 本地 HEAD 对齐
git reset --hard origin/main
```

**注意**：Contents API 生成的 commit 与本地 commit 哈希不同（内容一致），`git reset --hard` 到远端 sha 后 `git log` 会显示远端的分段 commit——这是正常现象，工作区内容一致即可。

## 实战要点（2026-08-15 两次验证）

- **vray-material-replacer**：3 更新（.ms + 2 md）+ 3 新建（AGENTS/CHANGELOG/DEVELOPMENT）+ 1 删除（DEV.md），一次跑通，6 文件 md5 全一致
- **knowledge-base**：中文路径 `用户库/仓库盘点表.md` 更新，`encodeURIComponent` 处理段路径成功
- git 身份：`git config user.name "Simiely" && git config user.email "Simiely@users.noreply.github.com"`（仓库级，勿 --global）
- **v1.1.0 迭代（2026-08-24, edge-multi-account-cookie 实测回填）**：
  1. 一次 `git/trees?recursive=1` 取全 blob sha，与逐个 `/contents/` 的 sha 一致（实测同 sha），PUT 复用免逐文件 GET
  2. PowerShell 下 `gh api --jq` 复杂表达式有转义坑，简单 jq 可用、复杂解析交 node/python
  3. 直连=超时、走代理=reset、api.github.com 可达即切 Contents，勿重试 git push（现象→决策，不臆断成因）

## 配套：knowledge-base 单项目文档规范（推送前按此建文档）
按 `模板库/单项目规范/README.md` 四件套：README（用户向）/ AGENTS（AI 向，含文档基线行）/ DEVELOPMENT（开发者向，一坑一篇）/ CHANGELOG（版本分节）。推送后回填 `用户库/仓库盘点表.md`（已重写表加行 + 从"未完成"移除），再推 knowledge-base。

## 验证清单
- [ ] api.github.com 可达（GET contents 返回列表）
- [ ] 更新文件带 sha，新建省略 sha，删除走 DELETE
- [ ] raw.githubusercontent.com 逐文件 md5 校验一致
- [ ] packed-refs 修正后 `git status` 干净
- [ ] knowledge-base 盘点表回填（如适用）
- [ ] （可选优化）一次 `git/trees?recursive=1` 取全 sha，可先校验两法 sha 一致再用于 PUT
