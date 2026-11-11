---
id: docs.decisions.0001
title: ADR-0001 用 repo-kit v2.2 做文档机器校验层
summary: 不重构技能库，只给根文档、docs/ 与 SKILL.md 链接加机器校验。
type: explanation
kind: decision
status: active
owner: "@simiely"
topics: [governance]
source_type: doc
source: scripts/check_repo.py
last_reviewed: 2026-11-11
related: []
---
# ADR-0001 用 repo-kit v2.2 做文档机器校验层

- Status: Accepted
- Date: 2026-11-11
- Owners: @simiely

## Context

仓库已有成熟的人工治理：README / AGENTS / DEVELOPMENT / CHANGELOG 四件套、文档基线、
新增技能五件事、`skills/_archived/` 归档惯例。22 个 Markdown 文件里，18 个是技能或参考资料。

问题是机器校验几乎为零：

- 根文档与技能之间的链接没有检查，改标题/移动目录会软断链；
- AGENTS 的「文档基线」是手写日期 + 版本，容易忘记更新；
- 没有统一的页面索引/反链；新增文档靠 README 手工挂载；
- 技能 frontmatter 是 `name/description`，与通用页面 schema 不同，不能强行套。

## Decision

采用 repo-kit v2.2，但只做**机器校验层**，不重构技能库：

1. `include` 覆盖根文档、`docs/**`、`skills/**/SKILL.md`。
2. `entry_files` = README / DEVELOPMENT / CHANGELOG；`context_files` = AGENTS。
3. `exempt_basenames` = `SKILL.md`：技能只做链接检查，不做通用页面 schema 校验。
4. 新增 `docs/index.md`、`docs/concepts/skill-model.md`、`docs/decisions/`，给人看的治理索引。
5. `schema/agents.template.md` 复制现有 AGENTS，生成器原样写回，不覆盖手写规则。
6. 生成 `llms.txt`、`docs/_generated/index.md`、`docs/_generated/backlinks.md`。
7. `SKILL.md` 的 `name/description` schema 留给未来的 `skills` profile，不在本 ADR 里硬塞。

## Consequences

正面：

- 根文档、治理页、技能链接都有机器检查；软断链会在 CI 里红。
- 生成索引/反链/llms.txt，新增治理页不必手写导航。
- 现有四件套和技能格式不被破坏。

代价：

- 18 个 SKILL.md/参考资料没有 frontmatter 校验；技能契约仍是人工约定。
- 新 `docs/` 页需要 frontmatter；这是治理页的成本，不是技能的成本。
- AGENTS 仍是手写，生成器只是原样写回，不自动生成规则。

## Verification

```bash
python -m pip install -r requirements.txt
python scripts/check_repo.py --root .
python scripts/generate.py --root . --check
```

预期：根文档 + 治理页 + SKILL.md 链接全绿；2 个已知目录链接只作为 WARN。

## NOT RUN

- 未校验 SKILL.md 的 `name/description` schema。
- 未纳入 `skills/**/references/**/*.md`；这些长资料暂不强制 frontmatter。
- 未接 zhlint、站点 build、CI；本次只做本地测试。
- 未 push；工作副本保留在本地。

## Supersession

None。要改本决策，写新 ADR 并标 `Supersedes: ADR-0001`，本文只翻 status，正文不动。
