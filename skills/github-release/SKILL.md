---
name: github-release
description: 在 WorkBuddy 沙箱/Windows 无交互环境里，为已推送到 GitHub 的代码打 tag + 创建/更新 GitHub Release + 上传 zip 资产。纯 GitHub API（urllib），完全脱离 git push 与 curl。用户说"发版本 / 建 Release / 打 tag / release / 传安装包 zip"时使用。
agent_created: true
---

# github-release —— 版本发布（tag + Release + 资产）

职责单一：**发布一个版本**。本地仓库代码必须**已经推送到远端分支**（推送用 `github-push-universal` skill）。本 skill 不负责推代码。

## 什么时候用
- 用户要求"发布 / 发版本 / 打 tag / 建 Release / release / 上传 zip 安装包"。
- 已有一个本地 git 仓库，HEAD 内容已在远端 main/dev 分支上，要给这段代码打版本号 + 建 GitHub Release + 附资产。

## 反模式（务必避免）
1. **不要用 curl** —— WorkBuddy 劫持 curl（`CODEBUDDY_*`），`exit 43 / HTTP 000` 假失败。脚本内部全走 urllib。
2. **不要靠 git push 打 tag** —— 无 tty 时 git 需要凭据会弹 `credentialhelperselector` 挂死（凭据层问题，**不是代理**；本机 7890 代理访问 github 是通的）。本脚本用 API POST `/git/refs` 建 tag，纯走 api.github.com，无 git 子进程、无弹窗、不受凭据层影响。
3. **Release body 含反引号/换行必须走文件** —— bash 双引号包 `python -c "..."` 时反引号会被当作命令吞掉。body 先 `Write` 到文件，用 `--body <file>`。
4. **token 不落盘、不进命令历史** —— 只经 `--token` / env `GH_TOKEN` / remote 内嵌传递。

## 工具
脚本：`release_repo.py`（同目录，Python3，零第三方依赖，纯 API）。

### token 来源（优先级）
`--token` 参数 > remote URL 内嵌 token > 环境变量 `GH_TOKEN` / `GITHUB_TOKEN`。
都没有 → 明确报错，绝不弹窗。

### 用法
```bash
# 标准发布：建 tag（指向本地 HEAD）+ 创建/更新 Release + 传 zip
export GH_TOKEN='ghp_...'
python "C:/Users/260803/.workbuddy/skills/github-release/release_repo.py" /path/to/repo \
  --tag v0.4.26 --body /path/to/release_notes.md --asset /path/to/App-v0.4.26.zip

# 只自检（连通 + tag/Release 是否已存在），不写任何东西
python ".../release_repo.py" /path/to/repo --tag v0.4.26 --test

# 预发布 / 自定义显示名 / 指定 token
python ".../release_repo.py" /path/to/repo --tag v1.0.0-rc1 --prerelease \
  --name "v1.0.0-rc1" --token 'ghp_...'
```

### 建议运行方式
```bash
cd /path/to/repo
export GH_TOKEN='ghp_...'          # 用完即弃，勿落盘
python "C:/Users/260803/.workbuddy/skills/github-release/release_repo.py" . \
  --tag v0.4.26 --body ./release_notes.md --asset ./dist/App-v0.4.26.zip
```
脚本内部自动：读 remote 解析 owner/repo、读本地 HEAD 作为发布 commit、幂等建 tag、
Release 已存在则 PATCH 更新而非报错、按扩展名选 Content-Type 传资产。

## 发布语义（幂等）
1. 本地 HEAD 作为发布 commit。
2. tag 不存在 → POST `/git/refs` 建轻量 tag；已存在 → 复用（指向不变，脚本只读不强制移动）。
3. 该 tag 已有 Release → PATCH 更新；没有 → POST 创建（`target_commitish=main`）。
4. `--asset` 存在 → 上传到 `uploads.github.com`（zip 用 `application/zip`）。

> 提示：若同一 tag 需**重新指向新 commit**（例如补丁后又推了新代码），Release 能更新 body，
> 但 GitHub 的 tag 不可直接改指向 —— 需先 `DELETE refs/tags/<tag>`（脚本已提供 `delete_tag`，可手动调用）
> 或换新版本号。通常发布新版本用新 tag 即可。

## 验证清单（发布后）
- [ ] `GET /repos/{o}/{r}/releases/tags/{tag}` → 200，body 长度 > 若干、`html_url` 可访问
- [ ] `assets` 含目标 zip（名称 + 大小）
- [ ] `https://github.com/{o}/{r}/releases/tag/{tag}` 浏览器可打开

## 与兄弟 skill 的关系
- **先** `github-push-universal` 把代码推到远端 → **再**本 skill 发布。
- 推送/发布失败先看 `github-connect-diag` 诊断（GCM 弹窗 / 代理挂起 / curl 劫持）。
