# workbuddy-skills

WorkBuddy 可复用技能（Skills）集——把验证有效的 AI 工作流沉淀成可安装技能，随时复用、持续扩展。

## 技能列表

| 技能 | 一句话 | 入口 | 状态 |
|---|---|---|---|
| **scenario-walkthrough** 场景走查 | 先按真实功能生成操作剧本（点哪→输什么→得什么），再逐条读代码模拟执行，找链路断裂/权限漏洞/状态机矛盾 | [skills/scenario-walkthrough/SKILL.md](skills/scenario-walkthrough/SKILL.md) | v3 稳定 |
| **isolated-diag-page** 隔离诊断页 | 写独立诊断页实测环境/API 可用性与数据落盘（写后读回自证），用真实数据定位根因，不靠猜——适用 API/iframe/权限类反复修不好的 bug | [skills/isolated-diag-page/SKILL.md](skills/isolated-diag-page/SKILL.md) | v1 稳定 |

## 安装

每个技能是一个目录，内含 `SKILL.md`。安装到 WorkBuddy 用户技能目录：

```bash
# Windows
# 复制 skills/<技能名>/ 到你的用户技能目录
# 例：scenario-walkthrough → C:\Users\<你>\.workbuddy\skills\scenario-walkthrough\
```

安装后在对话中说对应触发词（见各技能 description）即可使用。

## 维护规范

遵循 [knowledge-base 单项目规范](https://github.com/Simiely/knowledge-base/tree/main/模板库/单项目规范)：

- **四件套**：README（用户向）/ AGENTS（AI 向+文档基线）/ DEVELOPMENT（开发者向）/ CHANGELOG（版本记录）
- **文档基线**：AGENTS.md 顶部标日期 + commit hash，改后更新（断点续传）
- **生长式拆分**：主文件超阈值才拆（README >150 行、AGENTS >150 词、DEVELOPMENT >200 行），平时保持精简
- **新增技能五件事**：`skills/` 加目录 + README 技能列表加行 + CHANGELOG 加版本节 + AGENTS 基线行更新 + DEVELOPMENT 补坑记录（一坑一篇）

## 相关

- 知识库（跨项目文档沉淀）：https://github.com/Simiely/knowledge-base
