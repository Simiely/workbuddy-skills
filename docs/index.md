---
id: docs.index
title: 文档治理索引
summary: workbuddy-skills 的治理入口；技能本体仍在 skills/，不复制。
type: reference
kind: index
status: active
owner: "@simiely"
topics: [governance]
source_type: doc
source: README.md
last_reviewed: 2026-11-11
related: ["docs.concepts.skill-model:see-also", "docs.decisions.0001:see-also"]
---
# 文档治理索引

本仓库首先是**技能库**，其次才是文档库。技能本体在 `skills/<name>/SKILL.md`，有自己的
`name/description` frontmatter；本目录只放治理说明，不复制技能正文。

## 仓库四件套

- [README](../README.md) — 用户向：技能列表、安装、维护规范
- [AGENTS](../AGENTS.md) — AI 向：文档基线、关键坑、约定
- [DEVELOPMENT](../DEVELOPMENT.md) — 开发者向：结构、流程、一坑一篇
- [CHANGELOG](../CHANGELOG.md) — 版本记录

## 治理

- [技能单元模型](concepts/skill-model.md) — 一技能一目录、SKILL.md 唯一入口、三层正文
- [决策索引](decisions/index.md) — ADR
- [生成索引](_generated/index.md) — 从 frontmatter 生成
- [反向链接](_generated/backlinks.md) — 从 `related` 派生

## 机器校验

```bash
python -m pip install -r requirements.txt
python scripts/check_repo.py --root .
python scripts/generate.py --root . --check
```

Phase 1 只校验根文档、`docs/**` 与 `skills/**/SKILL.md` 的链接；`SKILL.md` 不做通用页面 schema
校验，避免破坏技能加载器。
