# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-10-30 v1.12.0（v1.12.0 新增 illustrator-artboard-clip：用 Illustrator 脚本按画板矩形剪切蒙版收素材，含溢出扫描 / 画板收边 / 零弹窗无头启动三脚本 + AI 2026 实测 API 坑位清单）　← 前序：2026-10-08 v1.11.1
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

## 技术栈

- WorkBuddy Skills：`SKILL.md` 格式（frontmatter 含 `name` + `description`，description 写触发词 + 适用对象 + 能力摘要）
- 本机用户技能目录：`C:\Users\<USER>\.workbuddy\skills\<技能名>\SKILL.md`
- git 三件套附 Python 脚本（`push_repo.py` / `release_repo.py`，Python3 零依赖），非 Node

## 关键坑

- 沙箱内 `git push` 到 github.com 慢/卡/弹窗 → 用 **github-env-fix** 先根治凭据弹窗（设全局 `credential.helper=`），再走 **GitHub Contents API** 或 git 推送（见 github-push-universal / github-release）
- ⚠️ **墙内访问 github：`127.0.0.1:7890`(Clash) 是可靠通道之一（建议保留 .gitconfig 的 http.proxy=7890），但通道时通时断**——2026-10-08 实测同一天里 7890 死过、直连成功过又失败过、代理 502 间歇。⇒ **每次先跑出口矩阵（env 隧道 / 7890 / 直连），一次失败 ≠ 此路不通，直连与代理都要试并自动重试**。真正让 git 卡死/弹窗的是 **credential helper（helper-selector/GCM）**，不是代理。
- 沙箱内 git 需要凭据时会弹 `credentialhelperselector`（无交互挂死）→ remote URL 内嵌 token / `-c credential.helper=` / 先跑 github-env-fix 根治，token 走 env/URL 内嵌
- 判断网络**用 Python urllib，不用 curl**（WorkBuddy 劫持 curl 致 exit 43 假失败）
- 认证：`Authorization: Bearer <PAT>`；未认证访问 GitHub API 会限流，一律带 token
- token 只用于 API 调用，**绝不写进任何被提交的文件**
- SkillManage 工具可能不可用 → 直接编辑 SKILL.md 文件即可，无需经过工具
- **Illustrator 无头脚本**：脚本必须与 Illustrator **同盘**（跨盘会弹模态 "File not found" 并阻塞执行，不点掉弹窗脚本永不开始）→ 用 illustrator-artboard-clip 的 `run_headless.ps1`（自动暂存到 `%SystemDrive%`）；**剪切组需 ≥2 个对象且裁切框在组内最上层**；`.jsx`/`.ps1` 一律纯 ASCII（ExtendScript/PS 5.1 按 ANSI 读，中文字面量会被破坏）→ 详见该技能 `references/api-pitfalls-ai2026.md`

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
