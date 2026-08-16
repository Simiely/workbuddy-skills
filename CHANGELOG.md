# CHANGELOG

## v1.1.0（2026-08-16）

- 新增：isolated-diag-page v1（隔离诊断页技能）
  - 方法论 4 步：环境检测（iframe/API/权限）→ 单项实测 → 写后读回自证 → 端到端模拟 + 对比找干扰项
  - 关键原则：「API 返回成功」≠「数据真实落盘」，写入后立即 read 读回自证
  - 附可复用模板 `templates/clipboard-diag.html`（剪贴板/浏览器 API 诊断页完整代码）
  - 含实战案例（富文本 Word 复制链路定位）+ 修复闭环 + 与 scenario-walkthrough 分工界定
- 文档：README 技能列表 / AGENTS 基线行 / DEVELOPMENT 坑记录（一坑一篇：诊断页实战）同步；新增技能流程"三件事→五件事"

## v1.0.0（2026-08-14）

- 新增：scenario-walkthrough v3（场景走查技能）
  - 主线 6 步：能力清单 → 素材剧本+覆盖矩阵 → 分级走查 → 报告 → 修复闭环 → 迭代停止
  - 工具库 8 件：复杂度 L1-L9 / 矩阵对账 / 规则真值表 / 时序 5 问 / 探索会话 SBTM / 变更影响 / 风险评分 / 报告模板
  - 检查沉淀：checklist（代码审查 10 项 + 流程合规 10 项）+ 落盘规范
- 规范：四件套文档（README / AGENTS / DEVELOPMENT / CHANGELOG），遵循 knowledge-base 单项目规范
