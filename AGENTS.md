# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-08-18（v1.2.0：+ docs-ssot-convergence 文档 SSOT 收敛技能）
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

## 技术栈

- WorkBuddy Skills：`SKILL.md` 格式（frontmatter 含 `name` + `description`，description 写触发词 + 适用对象 + 能力摘要）
- 本机用户技能目录：`C:\Users\wandou\.workbuddy\skills\<技能名>\SKILL.md`

## 关键坑

- 沙箱内 `git push` 到 github.com 不通（Connection reset）→ 用 **GitHub Contents API** 逐文件推送
- 认证：`Authorization: token <PAT>`；未认证访问 GitHub API 会限流（"API rate limit exceeded"），一律带 token
- token 只用于 API 调用，**绝不写进任何被提交的文件**
- SkillManage 工具可能不可用 → 直接编辑 SKILL.md 文件即可，无需经过工具

## 约定

- 每个技能一个子目录，`SKILL.md` 为唯一入口，单文件交付
- description 必须含触发词（如"走查""排查""模拟"），并写明核心价值
- 中文文档；skill 正文三层结构：A 主线（必做）/ B 工具库（按需查）/ C 检查与沉淀
- 新增技能五件事：`skills/` 加目录 + README 技能列表加行 + CHANGELOG 加版本节 + AGENTS 基线行更新 + DEVELOPMENT 补坑记录

## 常用命令

- 推送：GitHub Contents API（PUT `/repos/Simiely/workbuddy-skills/contents/{path}`，body 含 base64 content + message + branch）
- 验证：对话中直接说触发词测试技能

## 详细规则（按需 @引用）

- @DEVELOPMENT.md  仓库结构、新增技能流程、GitHub 推送方案
