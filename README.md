# workbuddy-skills

WorkBuddy 可复用技能（Skills）集——把验证有效的 AI 工作流沉淀成可安装技能，随时复用、持续扩展。

## 技能列表

| 技能 | 一句话 | 入口 | 状态 |
|---|---|---|---|
| **scenario-walkthrough** 场景走查 | 先按真实功能生成操作剧本（点哪→输什么→得什么），再逐条读代码模拟执行，找链路断裂/权限漏洞/状态机矛盾 | [skills/scenario-walkthrough/SKILL.md](skills/scenario-walkthrough/SKILL.md) | v3 稳定 |
| **minimal-repro-diagnosis** 最小单元链路诊断 | 排查"效果不对/只还原一部分"——新建最小单元复现（必须真实数据）→ 链路拆 N 步逐步对比特征差异（lost/gained）→ 差异集中步即根因，权威资料交叉验证后修复、全链路回归；附还原开关实验台反推外部程序行为 | [skills/minimal-repro-diagnosis/SKILL.md](skills/minimal-repro-diagnosis/SKILL.md) | v1 稳定 |
| **github-contents-api-push** GitHub 推送 | 沙箱内 git push 不通时的可靠通道——GitHub Contents API 逐文件 PUT（连通探测→更新/新建/删除→远端验证→packed-refs 修正） | [skills/github-contents-api-push/SKILL.md](skills/github-contents-api-push/SKILL.md) | v1 稳定 |
| **docs-ssot-convergence** 文档 SSOT 收敛 | 分散多文档收敛为单一权威源(SSOT)+派生视图,按 主线→支线→模块化 三视角组织总领文档,手册去重引用,旧快照降级标注,最后文档级场景走查挖净死角(声明≠可操作/触发边界防环/版本语义真值表) | [skills/docs-ssot-convergence/SKILL.md](skills/docs-ssot-convergence/SKILL.md) | v1 稳定 |
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
