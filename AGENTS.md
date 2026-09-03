# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-09-03 `5b8a3e5`（v1.6.0：新增 github-env-fix 推送前环境修复 + 修正三个 git skill 的"清代理直连"错误认知→保留 7890 代理只禁 credential helper）
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

## 技术栈

- WorkBuddy Skills：`SKILL.md` 格式（frontmatter 含 `name` + `description`，description 写触发词 + 适用对象 + 能力摘要）
- 本机用户技能目录：`C:\Users\260803\.workbuddy\skills\<技能名>\SKILL.md`
- git 三件套附 Python 脚本（`push_repo.py` / `release_repo.py`，Python3 零依赖），非 Node

## 关键坑

- 沙箱内 `git push` 到 github.com 慢/卡/弹窗 → 用 **github-env-fix** 先根治凭据弹窗（设全局 `credential.helper=`），再走 **GitHub Contents API** 或 git 推送（见 github-push-universal / github-release）
- ⚠️ **墙内必须走 `127.0.0.1:7890`(Clash) 代理才能访问 github**，走代理实测**必通**。**切勿删/设空 .gitconfig 的 http.proxy=7890**——那是历史"清代理直连"的错误认知（误以为 7890 挂起），照做才真连不上。真正让 git 卡死/弹窗的是 **credential helper（helper-selector/GCM）**，不是代理。
- 沙箱内 git 需要凭据时会弹 `credentialhelperselector`（无交互挂死）→ remote URL 内嵌 token / `-c credential.helper=` / 先跑 github-env-fix 根治，token 走 env/URL 内嵌
- 判断网络**用 Python urllib，不用 curl**（WorkBuddy 劫持 curl 致 exit 43 假失败）
- 认证：`Authorization: Bearer <PAT>`；未认证访问 GitHub API 会限流，一律带 token
- token 只用于 API 调用，**绝不写进任何被提交的文件**
- SkillManage 工具可能不可用 → 直接编辑 SKILL.md 文件即可，无需经过工具

## 约定

- 每个技能一个子目录，`SKILL.md` 为唯一入口
- description 必须含触发词（如"推送""发布""诊断"），并写明核心价值
- 中文文档；skill 正文三层结构：A 主线（必做）/ B 工具库（按需查）/ C 检查与沉淀
- 职责单一：诊断 ≠ 推送 ≠ 发布，分开建 skill，不捆绑
- **git skill 协作链路**：推送/发布前先跑 **github-env-fix**（根治凭据弹窗 + 确认 7890 代理保留）→ 再走 github-push-universal（推码）/ github-release（发布）；异常走 github-connect-diag 诊断
- **归档惯例**：不再维护的技能移入 `skills/_archived/` 并在 SKILL.md 顶部加「⚠️ 已归档」标注（注明被谁替代 + 新用哪个），不进 README 主列表，旧正文保留供查阅
- 新增技能五件事：`skills/` 加目录 + README 技能列表加行 + CHANGELOG 加版本节 + AGENTS 基线行更新 + DEVELOPMENT 补坑记录

## 常用命令

- 推送：GitHub Contents API（PUT `/repos/Simiely/workbuddy-skills/contents/{path}`，body 含 base64 content + message + branch）
- 验证：对话中直接说触发词测试技能

## 详细规则（按需 @引用）

- @DEVELOPMENT.md  仓库结构、新增技能流程、GitHub 推送方案
