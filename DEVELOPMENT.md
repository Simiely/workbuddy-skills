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
  <技能名>/xxx.py     技能附带的工具脚本（如 push_repo.py / release_repo.py）
skills/_archived/   已归档技能（不再维护，保留正文供查阅，SKILL.md 顶部加「⚠️ 已归档」标注）
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

### 问题：git 相关 skill 从"分散 + 捆绑"演进为职责单一的三件套

**TL;DR**：4 个 git skill（仓库 2 + 本机 2）能力重叠、边界模糊；曾尝试合成 1 个大 skill 违背单一职责。最终按功能拆成 诊断/推送/发布 3 个独立 skill，各自职责单一、可独立也可串联。

- 问题：workbuddy-skills 仓库有 git-push-proxy-fix（只诊断空代理覆盖）与 github-contents-api-push（Node 版 Contents 推送）；本机 ~/.workbuddy/skills 有 github-push-universal（Python，git 优先回退 API）与 github-release-windows。能力重叠（诊断 vs 推送 vs 发布混在 2-4 个 skill），且合成 1 个"大而全" skill 每次调用都要载入不相关上下文、违反单一职责。
- 根因：增量生长，没有按"意图"划分 skill 边界；同一主题的命令细节散落多处。
- 解决：按功能意图拆 3 个 skill——
  1. `github-connect-diag`（诊断）：只回答"为什么连不上/弹窗/慢"，症状→根因对照表，含凭据弹窗元凶（helper-selector/GCM）、curl 劫持、schannel、**空代理覆盖兜底**（git-push-proxy-fix 的根因收录为一条）。
  2. `github-push-universal`（推送）：只推代码到分支，git 优先自动回退 Contents API（Python）。
  3. `github-release`（发布）：只打 tag + Release + 资产（Python 纯 API）。
  旧 git-push-proxy-fix 与 github-contents-api-push 移入 skills/_archived/ 并标注被替代。
- 预防：新能力先归位（属于诊断/推送/发布哪一类），不新增第 4 个"杂烩" skill；脚本统一 Python（仓库旧 github-contents-api-push 是 Node，已不采用，避免 Node/Python 两套并存）。
- 归档语义：归档≠删除，保留正文供查阅（含旧 Node 细节、PowerShell curl 坑），SKILL.md 加 status:archived + 顶部横幅。

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

1. `skills/` 下建 `<技能名>/SKILL.md`（frontmatter + 三层正文）；如附脚本放同目录 `xxx.py`
2. README.md 技能列表加行（名称/一句话/入口/状态）
3. CHANGELOG.md 加版本节
4. AGENTS.md 基线行更新（新日期 + 新 commit hash）
5. 推送（Contents API，先本地测试再推）
6. DEVELOPMENT.md 补坑记录（如有）

## 归档技能流程（不再维护时）

1. 目录移入 `skills/_archived/<技能名>/`
2. 原 SKILL.md frontmatter 加 `status: archived`，正文顶部加「⚠️ 已归档」横幅（注明被谁替代 + 新用哪个 skill），旧正文保留
3. README 主列表删除该行，归档区 `### 已归档` 表格加一行
4. CHANGELOG 加版本节说明
5. AGENTS 基线行更新；约定段补归档惯例

## 坑记录（一坑一篇）

- **坑：SSOT 未收敛导致文档漂移**（2026-08-18，knowledge-retrieval-system 实战）——同一契约（API 参数/状态机/提交语义）散落在技术方案+4 本手册多处，改一处忘一处，改着改着手册之间打架。解法沉淀为 docs-ssot-convergence 技能：定义收敛到一份 Markdown（主线→支线→模块化三视角），手册引用不重复，旧快照标注降级。
- **坑：数据在链路中静默丢失/被规范化，表现为"只还原一部分/部分生效"**（2026-08-26，clipboard-tool v0.6.12 实战）——富文本复制到 Word 只还原基础格式：①CSSOM `rule.style.cssText` 只序列化浏览器认识的属性，`tab-interval/mso-*` 等 Word 私有属性全丢、`word-wrap` 被改写为 `overflow-wrap`；②Word 文档级设置写在 `<body>` 标签上，`doc.body.innerHTML` 不含 body 自身属性，必然丢。两处都是"API 返回成功但数据被静默处理"。解法沉淀为 minimal-repro-diagnosis 技能：新建最小单元 → 链路拆 N 步 → 逐步对比 lost/gained → 差异步即根因 → 权威资料验证 → 修复 + 全链路回归。**关键原则：验证数据保真别用 read() 等"重写形式"API（clipboard.read() 返回剥壳片段会误报），要用真实接收端（如真实粘贴回读）验证。**
- **坑：文档级走查与代码走查的差异**（2026-08-18）——scenario-walkthrough 面向"读代码模拟执行"；代码未写时走查链路终点是**文档定义**，断裂=🔴。补检查清单 10 类坑型（声明≠可操作/写端点×版本语义/触发边界防环等），并入 docs-ssot-convergence。
- **坑：git push 反复失败但代理正常，根因是 git 全局空代理覆盖**（2026-09-02，content-archive 实战）——推送 v0.6.5 连挂 3 次（超时 21s→Connection reset→Authentication failed），Clash 测速正常、curl 走代理访问 github 通。根因：`git config --global -l` 残留 `http.https://github.com.proxy=` 与 `https.https://github.com.proxy=` 两行**空值**，git 对 github.com 强制直连被墙。解法沉淀为 git-push-proxy-fix 技能：可靠连通验证（避 PowerShell `curl -w` 假失败）→ 定位空覆盖 → `--unset-all` 删除 → 看 `old..new main -> main` 判成功。**关键陷阱：PowerShell 下 `curl.exe -w "%{http_code}"` 的 `%{}` 被 PS 当脚本块解析，curl 报 bad argument（exit 43）输出 000 假失败，排查全程被误导；验证连通用无 `-w` 写法或 Invoke-WebRequest。**
- **坑：环境可用但 git 客户端弹 GCM 窗，git 通道不可靠，应切 API**（2026-09-03，workbuddy-skills 自身推送实战）——对公开仓库做 Contents API 拉取时 `git clone` 用内嵌 token URL 仍弹 `credentialhelperselector`（PortableGit 系统级 credential.helper=helper-selector + 无 tty）。改用 Python urllib 直接判网（api.github.com 200、token 有效）后确认问题仅在 git 客户端凭据弹窗。**结论：git 三件套脚本全走 API（urllib）推送/发布，不必依赖 git 二进制；判断网络/连通一律 Python urllib，不用 curl。**
- **坑：误判"7890 代理挂起需清代理直连"，实际墙内必须走 7890 且必通，真凶是凭据弹窗**（2026-09-03，用户实测纠正）——此前在 connect-diag/push-universal/release 三 skill 与 DEVELOPMENT 里写"git 走 7890(Clash) 代理会 TLS 挂起、清代理直连才通"，**被用户实测推翻**：走 7890 代理访问 github 必通（公开仓库、remote 内嵌 token 均正常返回 HEAD）。真凶：git 需要凭据且 remote 无内嵌 token 时被 PortableGit 系统级 `credential.helper=helper-selector` 拦截 → 弹 `credentialhelperselector`，无 tty 会话挂死。修复：全局 `git config --global credential.helper ""` + `--unset credential.helperselector.selected`（改前备份 .gitconfig），**7890 代理保留不动**。真实验证三项全绿：①7890+token+禁helper→私有仓库返回HEAD；②无token→干净报错 `could not read Username...terminal prompts disabled`(exit 128) 不弹窗不挂死；③走 .gitconfig 默认7890+token→通。**方法论：遇到 git/网络问题，任何尝试都得以搜索到的高可信内容为前提，不靠臆测假设。** 解法沉淀为 github-env-fix skill（推送前前置修复）+ 修正三个 git skill 的错误表述。
- **坑：WPF 自动验收工具落地——上游无 native bootstrapper + Inspector NaN 输出 bug + 布局位移根因**（2026-09-04，clipboard-tool exe 实战，沉淀为 wpf-visual-tree-ai-eyes）——三条独立坑：①WpfVisualTreeMcp release zip 不含 native 注入 DLL（需 MSVC 编译），直接 attach 注入模式必失败 → 必须走 self-hosted（目标 app 内嵌 Initialize，DEBUG-only，Release 纯净）；②v0.12.0 Inspector 把 double NaN/∞ 裸输出成非法 JSON → props 解析崩，本地 patch PropertyReader 后重装会丢需重打；③self-hosted 下 props properties 为空（net8 Inspector 跨 runtime TypeDescriptor 枚举 DP 失效），属性级读取暂缺 → 验收用 screenBounds 坐标 + click 交互代替。另沉淀 UI 布局位移诊断：隐藏控件 → Auto 行高收缩 → 内容上移；Auto 塌缩后 `*` 行吸收空间 → 内容向下拉伸（同一根因两方向）；修复用原位替换（同尺寸同位）或 MinHeight=行内所有固定元素之和（非只算最高子控件），验收以普通/模式中/退出三态基准元素 screenBounds.y 全等为准。
