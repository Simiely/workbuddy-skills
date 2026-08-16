# DEVELOPMENT.md · 开发说明

## 项目概览

workbuddy-skills 是 WorkBuddy 可复用技能的仓库。每个技能一个子目录，`SKILL.md` 为唯一入口。遵循 knowledge-base 单项目规范（四件套 + 文档基线 + 生长式拆分）。

## 架构说明

```
README.md           用户向门面：技能列表 + 安装方式 + 维护规范
AGENTS.md           AI 向：文档基线 + 关键坑 + 约定（核心约束精简，细节 @引用）
DEVELOPMENT.md      开发者向：本文（架构 + 一坑一篇）
CHANGELOG.md        版本记录（按版本分节，不拆）
skills/             每个技能一个子目录
  <技能名>/SKILL.md   技能本体（frontmatter + 三层正文）
```

**SKILL.md 格式约定**：
- frontmatter：`name`（英文短名）+ `description`（触发词 + 适用对象 + 能力摘要 + 核心价值）
- 正文三层：**A 主线**（必做流程，每步写 动作/产出/铁律/工具引用，读者 2 分钟掌握全流程）/ **B 工具库**（按需查，每个工具标触发条件）/ **C 检查与沉淀**（checklist 分"代码审查点/流程合规点"两组 + 落盘规范）
- 版本历史不留在正文（只留当前版本一行），修订痕迹进 CHANGELOG

## 关键问题与方案（一坑一篇）

### 问题：scenario-walkthrough 从 v1 到 v3 的结构演化

**TL;DR**：功能增量叠加导致主线/支线缠绕（247 行全平铺），v3 重构为三层结构（主线/工具库/检查）才清晰。

- 问题：v2.2 后出现 4 处缠绕——步骤 2 超载四件套、步骤 3 时序 5 问与探索会话平级错位、步骤 5/6 边界模糊、版本痕迹泄漏（正文版本历史 + checklist 版本前缀）
- 根因：增量补丁式写作，没有分层设计
- 解决：v3 三层——A 主线 6 步必做（每步 动作/产出/铁律/工具引用）+ B 工具库 8 件按需（B1-B8 各带触发条件）+ C 检查与沉淀（checklist 去版本前缀，分两组）
- 预防：新增能力先归位（主线还是工具库），不在主线堆细节

### 问题：素材只有基础案例，深链路 bug 挖不出

**TL;DR**：素材复杂度分级 L1-L9，进阶层逼状态机/并发/离线/权限/故障，覆盖矩阵每列映射一个等级。

- 问题：初版只有三类素材（基础/复杂/误操作），状态机矛盾（P-1）、并发竞态（P-89）、权限漏洞（P-6）测不到
- 根因：素材类型没有复杂度维度
- 解决：L1-L9 分级（L1-L3 基础层 / L4-L9 进阶层，每级带写法公式+示例+逼出的 bug 类型）；覆盖矩阵列=等级，空白即盲区
- 预防：有状态机/并发/离线/权限能力的项目必须含 ≥1 条 L4+ 链

### 问题：修完一轮就停，修不干净

**TL;DR**：迭代停止准则——四项收敛条件（🔴 清零 / 新发现减半连续 2 轮 / 回归全绿含冒烟集 / 探索收敛）全部满足才停；轮次上限 3 防无限循环。

- 问题：原方案"回归通过即闭环"，修复副作用、探索会话新链无兜底，可能停太早或永远修不完
- 根因：没有退出准则（业界：严重缺陷清零 + 缺陷收敛曲线 + 回归无新增 + 风险可控 + 预算盒）
- 解决：步骤 6 停止条件四项全满足才停；强制停止（3 轮上限/预算盒）输出残余风险报告收尾
- 预防：每轮输出轮次小结，四问驱动继续/停止

### 问题：GitHub 推送通道

**TL;DR**：沙箱 git push 不通，改用 GitHub Contents API 逐文件 PUT（建仓 POST /user/repos → PUT contents → GET sha 更新）。

- 问题：`git push` 到 github.com:443 Connection reset，无法走常规 git 通道
- 根因：沙箱网络限制（api.github.com 可通）
- 解决：`POST /user/repos` 建仓 → `PUT /repos/{owner}/{repo}/contents/{path}`（body：base64 content + message + branch）逐文件提交 → 更新已有文件先 `GET` 取 sha
- 预防：token 走环境变量不进文件；发布附件走 `uploads.github.com`；token 用经典 PAT（`x-access-token:` 前缀仅 GitHub App 令牌）

### 问题：浏览器 API/环境类 bug 反复修不好，补丁叠补丁

**TL;DR**：沉淀为 isolated-diag-page 技能——写独立诊断页逐环节实测，写后读回自证，用真实数据定位而非猜测。

- 问题：富文本复制链路"修了 10 轮还在失败"——iframe 权限假设、Chromium sanitize 假设、Word 行为假设全被实测推翻；补丁互相干扰
- 根因：多环节链路（来源→捕获→存储→渲染→再复制）中不确定"哪个环节坏了"，靠猜必然错
- 解决：独立诊断页（`public/diag.html`）逐项实测——①环境信息（iframe?API 存在?isSecureContext?）②clipboard.write ③execCommand ④clipboard.read ⑤paste 事件取 html ⑥readText ⑦端到端模拟+读回自证 ⑧xmlns 保留验证。关键原则：**「API 返回成功」≠「数据真实落盘」，写入后立即 read 读回比长度/关键标记**
- 实测结论：环境非 iframe、API 全可用；Word 无格式 = Word 粘贴默认「合并格式」+ Chromium 122+ sanitize 剥 style 块（浏览器强制行为，非代码缺陷）；存入 html 捕获断点（paste 事件漏 text/html）才是真 bug
- 预防：API/环境/多环节链路 bug 先写诊断页实测（skill 触发词"实测/为什么还是不行/找干扰项"），不直接改主应用

## 新增技能流程（行动清单）

1. `skills/` 下建 `<技能名>/SKILL.md`（frontmatter + 三层正文）
2. README.md 技能列表加行（名称/一句话/入口/状态）
3. CHANGELOG.md 加版本节
4. AGENTS.md 基线行更新（新日期 + 新 commit hash）
5. 推送（Contents API，先本地测试再推）
