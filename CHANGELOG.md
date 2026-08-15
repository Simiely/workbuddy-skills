# CHANGELOG

## v1.1.0（2026-08-15）

- 新增：github-contents-api-push v1（GitHub Contents API 推送技能）
  - 沙箱内 git push 不通（/dev/tty 凭证错 / Connection reset）时的可靠通道
  - 流程：连通性探测 → 逐文件 PUT（更新带 sha / 新建省略 / 删除 DELETE，中文路径分段 encodeURIComponent）→ raw md5 校验 → packed-refs 修正 → knowledge-base 盘点表回填
  - 附带 `push_repo.js` 可复用脚本模板
  - 已验证：vray-material-replacer（3 更新 + 3 新建 + 1 删除）、knowledge-base（中文路径更新），2026-08-15

## v1.0.0（2026-08-14）

- 新增：scenario-walkthrough v3（场景走查技能）
  - 主线 6 步：能力清单 → 素材剧本+覆盖矩阵 → 分级走查 → 报告 → 修复闭环 → 迭代停止
  - 工具库 8 件：复杂度 L1-L9 / 矩阵对账 / 规则真值表 / 时序 5 问 / 探索会话 SBTM / 变更影响 / 风险评分 / 报告模板
  - 检查沉淀：checklist（代码审查 10 项 + 流程合规 10 项）+ 落盘规范
- 规范：四件套文档（README / AGENTS / DEVELOPMENT / CHANGELOG），遵循 knowledge-base 单项目规范
