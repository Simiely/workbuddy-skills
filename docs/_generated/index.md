---
id: docs.generated.index
title: 生成索引
summary: 从 frontmatter 自动生成的导航；勿手改。
type: reference
kind: index
status: active
owner: "@platform"
source_type: doc
source: schema/taxonomy.json
last_reviewed: 2026-11-11
related: []
---

# 生成索引

> 生成文件，勿手改。运行 `python scripts/generate.py --root . --write` 重建。

## 按 type

### reference

| 页面 | kind | status | owner | tier | source |
|---|---|---|---|---|---|
| [决策索引](../decisions/index.md) | index | active | @simiely | normal | `docs/decisions/ADR-0001-adopt-repo-kit.md` |
| [文档治理索引](../index.md) | index | active | @simiely | normal | `README.md` |

### explanation

| 页面 | kind | status | owner | tier | source |
|---|---|---|---|---|---|
| [技能单元模型](../concepts/skill-model.md) | standard | active | @simiely | critical | `README.md` |
| [ADR-0001 用 repo-kit v2.2 做文档机器校验层](../decisions/ADR-0001-adopt-repo-kit.md) | decision | active | @simiely | normal | `scripts/check_repo.py` |

## 全部页面

| id | 标题 | type | kind | status |
|---|---|---|---|---|
| `docs.concepts.skill-model` | [技能单元模型](../concepts/skill-model.md) | explanation | standard | active |
| `docs.decisions.0001` | [ADR-0001 用 repo-kit v2.2 做文档机器校验层](../decisions/ADR-0001-adopt-repo-kit.md) | explanation | decision | active |
| `docs.decisions.index` | [决策索引](../decisions/index.md) | reference | index | active |
| `docs.index` | [文档治理索引](../index.md) | reference | index | active |
