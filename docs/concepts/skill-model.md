---
id: docs.concepts.skill-model
title: 技能单元模型
summary: 一个技能一个目录，SKILL.md 是唯一入口；frontmatter 用 name/description，正文三层。
type: explanation
kind: standard
status: active
owner: "@simiely"
tier: critical
topics: [skills]
defines: skill-model
source_type: doc
source: README.md
last_reviewed: 2026-11-11
related: []
---
# 技能单元模型

本仓库把验证有效的 AI 工作流沉淀成可安装技能。每个技能是一个**自包含目录**：

```
skills/<name>/
  SKILL.md        # 唯一入口：frontmatter + 正文
  *.py            # 可选：零依赖工具脚本
  references/     # 可选：长资料，按需查阅
```

## SKILL.md 的契约

- frontmatter：`name`（英文短名）+ `description`（触发词 + 适用对象 + 能力摘要）。
- 正文三层：
  - **A 主线**：必做流程，每步写动作/产出/铁律/工具引用。
  - **B 工具库**：按需查，每个工具标触发条件。
  - **C 检查与沉淀**：checklist + 落盘规范。
- 版本历史不留在正文；修订进 `CHANGELOG.md`。

## 归档与安装

- 不再维护的技能移入 `skills/_archived/`，SKILL.md 顶部加「⚠️ 已归档」，不进 README 主列表。
- 安装：把 `skills/<name>/` 复制到 `C:\Users\<USER>\.workbuddy\skills\<name>\`。
- 新增技能五件事：加目录、README 加行、CHANGELOG 加版本节、AGENTS 基线更新、DEVELOPMENT 补坑。

## 与 repo-kit 的边界

`SKILL.md` 的 `name/description` 是技能加载器的契约，和 repo-kit 的页面 frontmatter 不是同一套。
Phase 1 只把 `SKILL.md` 当**链接检查对象**，不当通用内容页；强行套 `id/type/source` 会破坏技能格式。
技能 frontmatter 的 schema 校验应作为独立的 `skills` profile，而不是塞进通用页面 schema。
