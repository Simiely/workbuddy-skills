#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Release 工具 (WorkBuddy 沙箱内，纯 API，脱离 git/curl)
==============================================================
职责：针对「已推送到远端分支」的代码，打 tag + 创建/更新 GitHub Release + 上传资产。
不负责代码推送 —— 代码推送用同级的 github-push-universal skill。

统一语义：把本地仓库 HEAD 视为"待发布的 commit"，在其上确保 tag 存在，
再创建/更新 Release（幂等：tag 已有 Release 则 PATCH 更新），最后上传 zip 资产。

用法：
  python release_repo.py <repo_dir> --tag vX.Y.Z [--body <file.md>] [--name "显示名"]
                                   [--asset <file.zip>] [--prerelease] [--token TOKEN]
  python release_repo.py <repo_dir> --tag vX.Y.Z --test   # 只自检连通与 tag 状态，不写

token 来源（优先级从高到低）：
  A. CLI 参数 --token
  B. 仓库 remote URL 中内嵌的 token（https://x-access-token:TOKEN@github.com/...）
  C. 环境变量 GH_TOKEN / GITHUB_TOKEN
  三者都没有 → 明确报错，绝不触发 GCM / 弹窗。

安全约定：
  - token 只经内存传递，不写进任何文件 / 不进仓库 / 不打日志。
  - Release body 若含反引号/换行，务必走 --body 文件，绝不在命令行内联（防 bash 吞反引号）。
"""
import os, sys, json, time, base64
import urllib.request, urllib.error, urllib.parse

API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"


def log(*a):
    print("[release] " + " ".join(str(x) for x in a), flush=True)


def die(msg):
    print("[release] ERROR: " + msg, flush=True)
    sys.exit(2)


# ---------------------------------------------------------------- GitHub API
class GitHubAPI:
    def __init__(self, token, owner, repo):
        self.token = token
        self.owner = owner
        self.repo = repo
        self._ur = urllib.request
        self._ue = urllib.error

    def _req(self, method, url, data=None, raw_body=None, content_type=None):
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/vnd.github+json",
                   "User-Agent": "release-universal"}
        body = None
        if raw_body is not None:
            body = raw_body
            headers["Content-Type"] = content_type or "application/octet-stream"
        elif data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        req = self._ur.Request(url, data=body, headers=headers, method=method)
        try:
            with self._ur.urlopen(req, timeout=120) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except self._ue.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"message": raw[:200]}

    # --- refs / tags ---
    def branch_sha(self, branch):
        s, d = self._req("GET", "%s/repos/%s/%s/branches/%s" % (API, self.owner, self.repo, branch))
        return d.get("commit", {}).get("sha") if s == 200 else None

    def ref_sha(self, ref):
        s, d = self._req("GET", "%s/repos/%s/%s/git/ref/%s" % (API, self.owner, self.repo, ref))
        return d.get("object", {}).get("sha") if s == 200 else None

    def create_lightweight_tag(self, tag, commit_sha):
        body = {"ref": "refs/tags/%s" % tag, "sha": commit_sha}
        s, d = self._req("POST", "%s/repos/%s/%s/git/refs" % (API, self.owner, self.repo), body)
        if s == 201:
            return True, "created"
        # 422 often means ref already exists (race) — caller re-reads
        return (s == 422), d.get("message", "")

    def delete_tag(self, tag):
        s, d = self._req("DELETE", "%s/repos/%s/%s/git/refs/tags/%s" % (API, self.owner, self.repo, tag))
        return s in (200, 204)

    # --- releases ---
    def get_release_by_tag(self, tag):
        s, d = self._req("GET", "%s/repos/%s/%s/releases/tags/%s" % (API, self.owner, self.repo, tag))
        return d if s == 200 else None

    def create_release(self, tag, name, body, prerelease=False, draft=False):
        existing = self.get_release_by_tag(tag)
        if existing:
            data = {"tag_name": tag, "name": name, "body": body,
                    "prerelease": prerelease, "draft": draft}
            return self._req("PATCH", "%s/repos/%s/%s/releases/%s" % (API, self.owner, self.repo, existing["id"]), data)
        data = {"tag_name": tag, "target_commitish": "main", "name": name,
                "body": body, "prerelease": prerelease, "draft": draft}
        return self._req("POST", "%s/repos/%s/%s/releases" % (API, self.owner, self.repo), data)

    def upload_asset(self, release_id, asset_path, content_type="application/octet-stream"):
        fname = os.path.basename(asset_path)
        url = ("%s/repos/%s/%s/releases/%s/assets?name=%s"
               % (UPLOAD, self.owner, self.repo, release_id, urllib.parse.quote(fname)))
        try:
            with open(asset_path, "rb") as f:
                payload = f.read()
        except Exception as e:
            return 0, {"message": "read-asset-fail: %s" % e}
        return self._req("POST", url, raw_body=payload, content_type=content_type)

    # --- misc query (verification) ---
    def list_release_assets(self, tag):
        rel = self.get_release_by_tag(tag)
        if not rel:
            return None
        s, d = self._req("GET", "%s/repos/%s/%s/releases/%s/assets" % (API, self.owner, self.repo, rel["id"]))
        return d if s == 200 else []


# ---------------------------------------------------------------- local git reads (read-only)
def git_read(repo, *args, timeout=30):
    """Run a read-only git command in repo; returns (code, out). No network, no interaction."""
    import subprocess
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        p = subprocess.run(["git", "-C", repo] + list(args),
                           capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout.strip()
    except Exception:
        return 127, ""


def resolve_target(repo):
    """Determine owner/repo/branch + local HEAD sha; reads only, never writes/network."""
    code, url = git_read(repo, "remote", "get-url", "origin")
    tok = None
    owner = reponame = None
    if code == 0 and url:
        import re
        m = re.match(r"https?://(?:[^@/]+@)?github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
        m2 = re.match(r"git@github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
        if m:
            owner, reponame = m.group(1), m.group(2)
            em = re.match(r"https?://(?:x-access-token:)?([^@/]+)@github\.com", url)
            tok = em.group(1) if em else None
        elif m2:
            owner, reponame = m2.group(1), m2.group(2)
    if not owner or not reponame:
        return None
    # default branch
    cb, branch = git_read(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch or "main"
    # local HEAD sha
    ls, head = git_read(repo, "rev-parse", "HEAD")
    head = head if ls == 0 and head else None
    return {"owner": owner, "repo": reponame, "branch": branch,
            "token_url": tok, "head": head}


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    repo = branch = token = tag = body_file = name = asset = None
    prerelease = do_test = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--branch" and i + 1 < len(args):
            branch = args[i + 1]; i += 2
        elif a == "--token" and i + 1 < len(args):
            token = args[i + 1]; i += 2
        elif a == "--tag" and i + 1 < len(args):
            tag = args[i + 1]; i += 2
        elif a == "--body" and i + 1 < len(args):
            body_file = args[i + 1]; i += 2
        elif a == "--name" and i + 1 < len(args):
            name = args[i + 1]; i += 2
        elif a == "--asset" and i + 1 < len(args):
            asset = args[i + 1]; i += 2
        elif a == "--prerelease":
            prerelease = True; i += 1
        elif a == "--test":
            do_test = True; i += 1
        elif a in ("-h", "--help"):
            print(__doc__); sys.exit(0)
        elif a.startswith("-"):
            print("unknown option", a); sys.exit(2)
        else:
            repo = a; i += 1
    if not repo:
        die("需要仓库路径")
    repo = os.path.abspath(repo)
    if not os.path.isdir(os.path.join(repo, ".git")):
        die("%s 不是 git 仓库" % repo)
    if not tag:
        die("需要 --tag vX.Y.Z")

    r = resolve_target(repo)
    if not r:
        die("无法从 origin 解析 owner/repo，请确认 remote 是 github 仓库")
    owner, reponame = r["owner"], r["repo"]
    branch = branch or r["branch"]
    head = r["head"]
    token = token or r["token_url"] or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        die("未找到 token：请用 --token 提供，或设 GH_TOKEN，或在 remote URL 内嵌")

    api = GitHubAPI(token, owner, reponame)
    log("仓库 %s/%s  分支=%s  tag=%s" % (owner, reponame, branch, tag))
    if not head:
        die("读不到本地 HEAD —— 请先确认本地有已 commit 的内容")

    if do_test:
        remote_head = api.branch_sha(branch)
        cur_tag = api.ref_sha("tags/" + tag)
        rel = api.get_release_by_tag(tag)
        log("自检: 远端分支=%s(%s)  tag存在=%s  Release存在=%s" %
            (branch, (remote_head[:8] if remote_head else "N/A"),
             "是@" + cur_tag[:8] if cur_tag else "否", "是" if rel else "否"))
        return

    # ---- 1) ensure tag ref exists pointing at local HEAD (idempotent)
    cur = api.ref_sha("tags/" + tag)
    if not cur:
        ok, msg = api.create_lightweight_tag(tag, head)
        if ok:
            log("tag %s 已创建 @ %s" % (tag, head[:8]))
        else:
            cur = api.ref_sha("tags/" + tag)  # maybe raced/created
            if not cur:
                die("建 tag %s 失败: %s" % (tag, msg))
    else:
        log("tag %s 已存在 @ %s" % (tag, cur[:8]))

    # ---- 2) body from file (avoid shell-quoting/backtick pitfalls)
    body = ""
    if body_file:
        try:
            with open(body_file, encoding="utf-8") as f:
                body = f.read()
        except Exception as e:
            die("读取 body 文件失败: %s" % e)
    rname = name or tag
    s, d = api.create_release(tag, rname, body, prerelease=prerelease)
    if s not in (200, 201):
        die("创建/更新 Release 失败: %s" % json.dumps(d)[:200])
    rid = d.get("id")
    log("Release %s 就绪 (id=%s, url=%s)" % (tag, rid, d.get("html_url", "")))

    # ---- 3) upload asset
    if asset:
        if not os.path.isfile(asset):
            die("资产文件不存在: %s" % asset)
        ct = "application/zip" if asset.lower().endswith(".zip") else "application/octet-stream"
        sa, ad = api.upload_asset(rid, asset, ct)
        if sa in (200, 201):
            log("资产已上传: %s (%s bytes)" % (os.path.basename(asset), os.path.getsize(asset)))
        else:
            die("上传资产失败: %s" % json.dumps(ad)[:200])

    log("完成：https://github.com/%s/%s/releases/tag/%s" % (owner, reponame, tag))


if __name__ == "__main__":
    main()
