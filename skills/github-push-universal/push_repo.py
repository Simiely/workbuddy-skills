#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 GitHub 推送工具 (WorkBuddy 沙箱内优先，可脱离 git 使用)
=============================================================
目标：在 WorkBuddy 沙箱/无交互环境里稳定推送 GitHub。

统一语义：把「本地已 commit 的内容」推送到远端分支之上。

流程：
  1. 探测 remote 解析 owner/repo/branch；解析 token。
  2. `git add -A` + `git commit`（把工作区改动先固化成本地 commit）。
  3. 若本地 HEAD 与远端 HEAD 一致 → 无需推送，结束。
  4. 优先尝试 `git push`（直连 + 超时 + 禁用 GCM/弹窗/交互）。
     成功 → 结束。
  5. 若 git push 失败（/dev/tty、Connection reset、超时、credentialhelperselector
     等征兆）→ 自动回退 GitHub Contents API，基于「本地 HEAD 树 vs 远端树」
     逐文件对齐（PUT / DELETE），幂等——内容已一致的跳过。
  6. 推送成功后用 `git fetch` + 重置本地 ref，使 `git status` 与远端一致。

token 来源（优先级从高到低）：
  A. CLI 参数 --token
  B. 仓库 remote URL 中内嵌的 token（如 https://x-access-token:TOKEN@github.com/...）
  C. 环境变量 GH_TOKEN / GITHUB_TOKEN
  三者都没有 → 明确报错，绝不触发 GCM 弹窗。

用法：
  python push_repo.py <repo_dir> [--branch main] [--message "..."] [--token TOKEN]
                        [--git-only] [--force-contents] [--test]
  python push_repo.py --test <repo_dir>   # 只探测远端可达性，不推送

安全约定：
  - 不把 token 写进任何文件 / 不进仓库 / 不打日志，只在内存中使用。
  - Contents API 采用幂等对齐：本地与远端一致的路径不产生多余 commit。
"""
import os, sys, subprocess, base64, json, time, re

API = "https://api.github.com"


# ---------------------------------------------------------------- helpers
def log(*a):
    print("[push] " + " ".join(str(x) for x in a), flush=True)


def die(msg):
    print("[push] ERROR: " + msg, flush=True)
    sys.exit(2)


def run(cmd, timeout=60, cwd=None):
    """Run a command; return (returncode, stdout, stderr). Never interact."""
    env = dict(os.environ)
    for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "all_proxy", "ALL_PROXY", "CODEBUDDY_SERVICE_PROXY_URL"]:
        env.pop(k, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "true"
    env["SSH_ASKPASS"] = "true"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd or ".", env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT"
    except FileNotFoundError:
        return 127, "", "not-found"


# ---------------------------------------------------------------- git primitives
def git(repo, *args, timeout=60):
    code, out, err = run(["git", "-C", repo] + list(args), timeout=timeout)
    return code, out, err


def head_sha(repo):
    code, out, _ = git(repo, "rev-parse", "HEAD", timeout=15)
    return out.strip() if code == 0 and out.strip() else None


def default_branch(repo):
    code, out, _ = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", timeout=15)
    if code == 0 and out.strip():
        return out.strip().replace("origin/", "")
    code, out, _ = git(repo, "rev-parse", "--abbrev-ref", "HEAD", timeout=15)
    return out.strip() if code == 0 and out.strip() else "main"


def local_has_uncommitted(repo):
    code, out, _ = git(repo, "status", "--porcelain", timeout=20)
    return bool(out.strip()) if code == 0 else False


def blob_sha_in_repo(repo, path):
    """Git blob sha of a working file (used to detect no-op against remote)."""
    code, out, _ = run(["git", "-C", repo, "hash-object", path], timeout=20)
    return out.strip() if code == 0 and out.strip() else None


# ---------------------------------------------------------------- remote probing
def probe_remote(repo):
    code, out, _ = git(repo, "remote", "get-url", "origin", timeout=15)
    if code != 0:
        return None
    url = out.strip()
    owner = reponame = None
    tok = None
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
    return {"owner": owner.strip(), "repo": reponame.strip(),
            "branch": default_branch(repo), "token_url": tok}


# ---------------------------------------------------------------- GitHub API
class GitHubAPI:
    def __init__(self, token, owner, repo):
        self.token = token
        self.owner = owner
        self.repo = repo
        import urllib.request, urllib.error
        self._ur = urllib.request
        self._ue = urllib.error

    def _req(self, method, path, data=None):
        url = API + path
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/vnd.github+json",
                   "User-Agent": "push-universal",
                   "Content-Type": "application/json"}
        body = json.dumps(data).encode() if data is not None else None
        req = self._ur.Request(url, data=body, headers=headers, method=method)
        try:
            with self._ur.urlopen(req, timeout=60) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except self._ue.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"message": raw[:200]}

    def branch_sha(self, branch):
        s, d = self._req("GET", "/repos/%s/%s/branches/%s" % (self.owner, self.repo, branch))
        return d.get("commit", {}).get("sha") if s == 200 else None

    def tree_list(self, branch):
        """Return {path: {'sha': blob_sha, 'type': ...}} for the whole branch tree."""
        bs = self.branch_sha(branch)
        if not bs:
            return None
        s, d = self._req("GET", "/repos/%s/%s/git/trees/%s?recursive=1" % (self.owner, self.repo, bs))
        out = {}
        if s == 200:
            for t in d.get("tree", []):
                if t.get("type") in ("blob", "submodule"):
                    out[t["path"]] = t
        return out

    def delete_path(self, path, blob_sha, branch, message):
        return self._req("DELETE", "/repos/%s/%s/contents/%s" % (self.owner, self.repo, path),
                         {"message": message, "sha": blob_sha, "branch": branch})

    def put_path(self, path, content_b64, old_sha, branch, message):
        data = {"message": message, "content": content_b64, "branch": branch}
        if old_sha:
            data["sha"] = old_sha
        return self._req("PUT", "/repos/%s/%s/contents/%s" % (self.owner, self.repo, path), data)


def walk_local_tree(repo, root):
    """Yield (relpath) for every file under root in the working tree."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip .git
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, root).replace("\\", "/")
            out.append(rel)
    return out


def contents_api_push(repo, cfg):
    """Align remote branch tree to the local working tree via Contents API.
    Idempotent: paths already identical on remote are skipped.
    Returns True on success. Produces commits per changed file (API limitation)."""
    branch = cfg["branch"]
    api = GitHubAPI(cfg["token"], cfg["owner"], cfg["repo"])
    base_sha = api.branch_sha(branch)
    if not base_sha:
        die("Contents API: 无法读取远端分支 %s（token 无权限或仓库不存在）" % branch)
    remote_tree = api.tree_list(branch) or {}
    local_root = repo
    local_files = walk_local_tree(repo, local_root)

    plan = []          # actions: ("put", path, b64) or ("del", path, sha)
    for rel in local_files:
        # git blob sha of local file
        fp = os.path.join(local_root, rel)
        if not os.path.isfile(fp):
            continue
        try:
            with open(fp, "rb") as f:
                raw = f.read()
        except Exception:
            continue
        local_blob = blob_sha_in_repo(repo, rel)
        remote = remote_tree.get(rel)
        # if remote blob sha (github content sha == git blob sha) equals local -> skip
        if remote and remote.get("sha") == local_blob:
            continue
        b64 = base64.b64encode(raw).decode()
        plan.append(("put", rel, b64, (remote or {}).get("sha")))
    # deletions: remote files not present locally (exclude submodule? still delete handled)
    remote_paths = set(remote_tree.keys())
    local_set = set(local_files)
    for rp in remote_paths - local_set:
        plan.append(("del", rp, None, remote_tree[rp].get("sha")))

    if not plan:
        log("Contents API: 本地与远端已一致，无需推送")
        return True
    log("Contents API: 待同步 %d 项（%d 写入 / %d 删除）" %
        (len(plan), sum(1 for p in plan if p[0] == "put"), sum(1 for p in plan if p[0] == "del")))
    put_n = del_n = 0
    for act in plan:
        kind, path = act[0], act[1]
        if kind == "put":
            b64, old_sha = act[2], act[3]
            s, d = api.put_path(path, b64, old_sha, branch, cfg["message"])
            if s in (200, 201):
                log("  [PUT]    %s" % path); put_n += 1
            else:
                die("PUT %s 失败: %s" % (path, json.dumps(d)[:160]))
        else:
            sha = act[3]
            if not sha:
                continue
            s, d = api.delete_path(path, sha, branch, cfg["message"])
            if s == 200:
                log("  [DELETE] %s" % path); del_n += 1
            else:
                die("DELETE %s 失败: %s" % (path, json.dumps(d)[:160]))
    log("Contents API: 完成 %d PUT / %d DELETE" % (put_n, del_n))
    return True


# ---------------------------------------------------------------- git push try
def try_git_push(repo, cfg):
    branch = cfg["branch"]
    remote_url = "https://x-access-token:%s@github.com/%s/%s.git" % (cfg["token"], cfg["owner"], cfg["repo"])
    cmd = ["git", "-C", repo,
           "-c", "credential.helper=",
           "-c", "http.sslBackend=openssl",
           "-c", "http.version=HTTP/1.1",
           "push", remote_url, "HEAD:" + branch]
    code, out, err = run(cmd, timeout=90)
    combined = out + "\n" + err
    if code == 0:
        return True, "git-push-ok"
    low = combined.lower()
    if ("credentialhelperselector" in low or "credential" in low or "askpass" in low
            or "no such device" in low or "/dev/tty" in low):
        return False, "credential-triggered: " + combined[-200:]
    if code == 124:
        return False, "git-timeout"
    return False, "git-fail(code=%s): %s" % (code, combined[-300:])


def sync_local_ref_to_remote(repo, cfg):
    """After push, align local refs so `git status` matches remote."""
    remote_url = "https://x-access-token:%s@github.com/%s/%s.git" % (cfg["token"], cfg["owner"], cfg["repo"])
    code, _, _ = run(["git", "-C", repo,
                      "-c", "credential.helper=",
                      "-c", "http.sslBackend=openssl",
                      "-c", "http.version=HTTP/1.1",
                      "fetch", remote_url, cfg["branch"] + ":refs/remotes/origin/" + cfg["branch"]],
                     timeout=90)
    if code == 0:
        code2, _, _ = git(repo, "update-ref", "refs/heads/" + cfg["branch"],
                          "refs/remotes/origin/" + cfg["branch"], timeout=15)
        # also fix upstream head symbolic
        git(repo, "symbolic-ref", "refs/remotes/origin/HEAD",
            "refs/remotes/origin/" + cfg["branch"], timeout=15)
        return code2 == 0
    return False


# ---------------------------------------------------------------- entry
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(0)
    repo = branch = message = token = None
    git_only = force_contents = do_test = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--branch" and i + 1 < len(args):
            branch = args[i + 1]; i += 2
        elif a == "--message" and i + 1 < len(args):
            message = args[i + 1]; i += 2
        elif a == "--token" and i + 1 < len(args):
            token = args[i + 1]; i += 2
        elif a == "--git-only":
            git_only = True; i += 1
        elif a == "--force-contents":
            force_contents = True; i += 1
        elif a == "--test":
            do_test = True; i += 1
        elif a.startswith("-"):
            print("unknown option", a); sys.exit(2)
        else:
            repo = a; i += 1
    if not repo:
        die("需要仓库路径")
    repo = os.path.abspath(repo)
    if not os.path.isdir(os.path.join(repo, ".git")):
        die("%s 不是 git 仓库" % repo)

    pr = probe_remote(repo)
    if not pr:
        die("无法从 origin 解析 owner/repo，请确认 remote 是 github 仓库")
    owner, reponame = pr["owner"], pr["repo"]
    branch = branch or pr["branch"]
    message = message or ("auto: push via push_repo.py " + time.strftime("%Y-%m-%d %H:%M"))
    token = token or pr["token_url"] or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        die("未找到 token：请用 --token 提供，或设 GH_TOKEN，或在 remote URL 内嵌")
    cfg = {"owner": owner, "repo": reponame, "branch": branch,
           "token": token, "message": message}
    log("仓库 %s/%s  分支=%s" % (owner, reponame, branch))

    api = GitHubAPI(token, owner, reponame)
    if do_test:
        bs = api.branch_sha(branch)
        log("自检: 远端分支 %s 可达，sha=%s" % (branch, (bs[:8] if bs else "N/A")))
        return

    # ---- step: commit local working changes (unless git-only already committed by caller)
    if not git_only:
        code, _, err = git(repo, "add", "-A", timeout=30)
        if code != 0:
            die("git add 失败: %s" % err[-200:])
        if local_has_uncommitted(repo):
            code, _, err = git(repo, "commit", "-m", message, timeout=40)
            if code != 0:
                log("警告: 本地 commit 未成功（%s），继续尝试推送已 commit 内容" % err[-150:])
        else:
            log("工作区干净，无新增 commit")

    # ---- decide if push needed
    local = head_sha(repo)
    remote = api.branch_sha(branch)
    if local and remote == local:
        log("本地 HEAD 与远端一致，无需推送")
        return

    # ---- git path
    if not force_contents:
        ok, why = try_git_push(repo, cfg)
        if ok:
            log("git push 成功")
            sync_local_ref_to_remote(repo, cfg)
            return
        if git_only:
            log("git push 结果: 失败 (%s)" % why)
            sys.exit(1)
        log("git push 失败(%s)，回退 Contents API..." % why)
    else:
        log("--force-contents，跳过 git 直接走 Contents API")

    # ---- contents API fallback
    log("--- 走 GitHub Contents API 推送 ---")
    if contents_api_push(repo, cfg):
        # reset local working refs to remote so status is clean
        remote2 = api.branch_sha(branch)
        if remote2:
            git(repo, "update-ref", "refs/heads/" + branch, remote2, timeout=15)
            git(repo, "update-ref", "refs/remotes/origin/" + branch, remote2, timeout=15)
            log("本地 ref 已与远端对齐 (%s)" % remote2[:8])
        log("Contents API 推送完成")
    else:
        die("Contents API 推送失败")


if __name__ == "__main__":
    main()
