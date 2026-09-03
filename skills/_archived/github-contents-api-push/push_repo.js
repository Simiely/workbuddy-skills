// GitHub Contents API 推送模板 —— 用法：
// 1. 改 REPO / BRANCH / 文件清单 / commit message
// 2. 运行: GH_TOKEN="ghp_xxx" node push_repo.js
// 3. 只处理 git push 不通的沙箱环境；token 走环境变量不落盘
const fs = require('fs');
const token = process.env.GH_TOKEN;
if (!token) { console.log('缺 GH_TOKEN 环境变量'); process.exit(1); }

const REPO = '<owner>/<repo>';        // 改这里
const BRANCH = 'main';
const LOCAL_ROOT = 'D:/workbuddy/2026-08-14-22-01-24/<repo>';  // 本地仓库绝对路径
const MSG = 'chore: update via Contents API';
const UPDATES = [];   // 更新已有文件: 'path/in/repo'
const NEWS = [];      // 新建文件: 'path/in/repo'
const DELETES = [];   // 删除文件: 'path/in/repo'

const base = 'https://api.github.com/repos/' + REPO;
async function api(path, method, body) {
  const r = await fetch(base + path, {
    method: method || 'GET',
    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'workbuddy' },
    body: body ? JSON.stringify(body) : undefined
  });
  return { status: r.status, json: await r.json().catch(() => ({})) };
}
const enc = p => p.split('/').map(encodeURIComponent).join('/');
const getSha = async p => { const { status, json } = await api('/contents/' + enc(p)); return (status === 200 && json.sha) ? json.sha : null; };
const putFile = async (p, content, sha) => {
  const body = { message: MSG, content: Buffer.from(content, 'utf8').toString('base64'), branch: BRANCH };
  if (sha) body.sha = sha;
  const { status } = await api('/contents/' + enc(p), 'PUT', body);
  return status;
};
const deleteFile = async (p, sha) => {
  const { status } = await api('/contents/' + enc(p), 'DELETE', { message: MSG, sha, branch: BRANCH });
  return status;
};

(async () => {
  for (const p of UPDATES) {
    const sha = await getSha(p);
    const content = fs.readFileSync(LOCAL_ROOT + '/' + p, 'utf8');
    const s = await putFile(p, content, sha);
    console.log((s === 200 || s === 201) ? 'UPDATED ' + p : 'FAIL ' + p + ' status=' + s);
  }
  for (const p of NEWS) {
    const sha = await getSha(p);
    const content = fs.readFileSync(LOCAL_ROOT + '/' + p, 'utf8');
    const s = await putFile(p, content, sha || undefined);
    console.log((s === 200 || s === 201) ? 'CREATED ' + p : 'FAIL ' + p + ' status=' + s);
  }
  for (const p of DELETES) {
    const sha = await getSha(p);
    if (sha) {
      const s = await deleteFile(p, sha);
      console.log(s === 200 ? 'DELETED ' + p : 'FAIL delete ' + p + ' status=' + s);
    } else console.log(p + ' 不存在，跳过');
  }
})().catch(e => console.log('NET ERR', e.message));
