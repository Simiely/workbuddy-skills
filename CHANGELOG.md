# CHANGELOG

## v1.9.0（2026-09-24）

- 新增：**png-sequence-to-webp v1**（设计序列帧 → WebP 交付：单帧批量 + 动态动图 + 配色适配）——沉淀自 362 人脸/声纹弹窗动效切图交付实战。
  - **主线**：只读侦察 → **按组跑全量基准**定编码参数 → 单帧转换（`exact=True` 保透明区 RGB + 逐像素核验）→ 合成动态 WebP → 配色适配 → 交付。
  - **核心结论**：无损 vs 有损的胜负取决于「**有没有渐变**」，不取决于尺寸 —— 扁平/单色组无损更小且零误差（实测单色细线组无损 800.5K < q90 的 1099.7K，有损纯负收益），只有软渐变填充组才是有损的战场；**混合模式严格占优**（扁平组无损 + 渐变组 q90，体积与全有损几乎相同但扁平部分保持 0 误差）。且**必须按组全量跑基准**，抽样会被少数大体积帧带偏（实测抽样 19.7% vs 全量 35.3%）。
  - **动图核心坑（本次实测定位）**：① Pillow `save_all=True` 走 libwebp `WebPAnimEncoder`，会**偷合并完全相同的连续帧**（9 帧→8 帧、50 帧→41 帧）并改写时长；② 其写出的 `ANMF` flags 是 `dispose=none`，libwebp 在 no-blend 下**跳过 alpha==0 的像素** → 透明区残留上一帧，误差精确满足 `got_a = 2a - a²/255`（即与自身再混合一次）。
  - **解法：容器级 mux** —— 直接复用源文件里已编码好的 VP8L 码流塞进 `ANMF`，零重编码、解码逐字节还原；`ANMF` flags 固定 `0x01`（dispose-to-background + no-blend，按 RFC 9649 bit0=disposal / bit1=blending，实测 `0x00` 会帧帧叠加）；帧时长按累计取整分配（`round(i*1000/fps) - round((i-1)*1000/fps)`，30fps 得 `33,34,33,33,34,33,33,34,33`，9 帧精确 300ms；固定 33ms 会让 90 帧变成 2.97s）。
  - **帧率不自证就会整批错**：`fps = mdhd.timescale / stts.delta` 从同项目 mp4 反推（30fps → 30000/1000，29.97 → 30000/**1001**）；`stts` 在 `moov>trak>mdia>minf>stbl>stts`，**不在 `mdia` 直接子级**（只在 mdia 下遍历找不到）；`mvhd` 的 timescale 通常 90000 与帧率无关。
  - **配色适配 `--recolor`**：精确 RGB 匹配 + **alpha 原样保留**（实测 212×212×90 帧 alpha 差异 **0 像素**、alpha 取值分布逐帧一致）。坑：**"白色"未必是 `#FFFFFF`** —— 实测某素材为米白 `#FCF9F7`，同批另一组才是纯白，写错 FROM 会 0 命中静默产出未改色的文件；必须先量色值。
  - **附脚本**：`convert_seq_to_webp.py`（批量转换 + 保结构改名 + 按组体积表 + 逐像素核验，失败即非零退出）、`mux_anim_webp.py`（容器级 mux + 结构层/解码层双重核验 + `--recolor`），均纯 Python（Pillow / numpy），脚本与 SKILL.md 同目录。
- 文档：README 技能列表加行 / CHANGELOG v1.9.0 / AGENTS 基线行更新（下一提交补 hash）/ DEVELOPMENT 坑记录。

## v1.8.0（2026-09-09）

- 新增：**superellipse-icon v1**（超椭圆图标裁剪/应用图标标准化）——沉淀自登录态切换器 app.ico 接入实战，把 WindowTinter 仓库的超椭圆图标标准固化：任意方形源图 → 超椭圆裁剪（n=4 大尺寸 / n=8 小尺寸）→ 6 分辨率 ICO（16/32/48/64/128/256, 32bpp PNG 条目）。
  - **实现**：附零配置 `make_icon.py`（仅依赖 Pillow；掩膜超椭圆纯 Python 计算，无需 NumPy）；`--verify` 一键校验产物条目数/位深/格式。
  - **核心坑固化**：① Pillow `img.save('.ico', sizes=..., append_images=...)` **只写第一张**（16px），必须手动组装 `ICONDIR + 逐尺寸 PNG 条目`；② 掩膜 `ss=4` 超采样 + `LANCZOS` 降采样得到四角抗锯齿软边（硬裁会锯齿）；③ 小尺寸指数 n=8（更方、小图清晰）、大尺寸 n=4（圆润）。
  - **接入**：exe 用 PyInstaller `EXE(icon=...)` 嵌入；tkinter 窗口图标 `iconbitmap` 经 `App._apply_icon()` 设置（打包取 `sys._MEIPASS` 内附版、源码取工程根）。
- 文档：README 技能列表加行 / CHANGELOG v1.8.0 / AGENTS 基线行更新（下一提交补 hash）/ DEVELOPMENT 坑记录。

## v1.7.1（2026-09-04）

- 修订：github-env-fix / github-push-universal / github-release 三技能与 AGENTS.md 中硬编码的机器路径 `C:/Users/260803/...` 统一占位化为 `C:/Users/<USER>/...`（共 7 处），仓库不再绑死单机；github-env-fix「正确基线」节补一行说明：`<USER>` = 本机 Windows 用户名，移植时按实际用户名替换。
- 约定：仓库内凡示例/本机路径一律用 `<USER>` 占位符；本地安装位（`~/.workbuddy/skills`）需 `sed -i 's|C:/Users/<USER>|C:/Users/<本机用户名>|g'` 后使用。

## v1.7.0（2026-09-04）

- 新增：**wpf-visual-tree-ai-eyes v1**（WPF"AI 眼睛"自动视觉验收，沉淀自 clipboard-tool exe 项目实战）——让 AI 直接读运行中 WPF 程序的元素树与控件坐标，用数字当证据验收 UI，替代"改→截图→再改"人工往返：
  - **接入**：WpfVisualTreeMcp(self-hosted, DEBUG-only)两步接入——csproj Debug+Exists 条件引用 Inspector/Shared 两 DLL + `WPFMCP_INSPECTOR` 常量;App.xaml.cs OnStartup `#if` 内 `InspectorService.Initialize`。Release 构建纯净不含 inspector。
  - **验收流**：run_in_background 托管启动 → attach(`Loaded (self-hosted)`)→ tree 美化看结构 → find 按 name/文本/类型定位拿 handle+screenBounds → click Invoke 驱动状态 → 前后对比出量化结论。
  - **布局位移量化验收法**（实战沉淀）：隐藏控件→Auto 行高收缩→上移 / `*` 行吸收空间→向下拉伸（同一根因两方向）;修复用原位替换或 MinHeight=行内所有固定元素之和（含计算式）;验收=普通/模式中/退出三态基准 Y 全等 + 拉伸场景 meta/body 间距恒等。
  - **上游坑登记**：① release 无 native bootstrapper→必须 self-hosted;② v0.12.0 Inspector NaN/∞ 输出非法 JSON（已本地 patch，重装需重打）;③ self-hosted props properties 为空（跨 runtime TypeDescriptor）→用坐标+交互代替属性读取。
  - 路径全部泛化为 `<USER>`（不绑死单机），完整代码/patch/命令在 `references/wpfvisualtreemcp-setup.md`。
- 文档：README 技能列表加行 / CHANGELOG v1.7.0 / AGENTS 基线行（下一提交补 hash）/ DEVELOPMENT 坑记录。

## v1.6.0（2026-09-03）

- 新增：**github-env-fix v1**（推送/发布前环境修复）——git 三件套（connect-diag/push-universal/release）的**前置步骤**。职责：先检测并根治 git 凭据弹窗（全局设 `credential.helper=` + 删 `helperselector.selected`），确认 7890(Clash) 代理保留，跑完环境即就绪再交棒给兄弟 skill。含就绪检测清单 + 修复A(改前备份) + 验证 + 回滚 + 反模式。
- 🔧 **修正认知（v1.5.0 及三个 git skill 曾写错）**：此前误以为"git 走 7890(Clash) 代理会 TLS 挂起、需清代理直连才通"。**实测证明这是错的**——用户墙内必须走 7890 代理才能访问 github，走代理**必通**；真正让 git 卡死/弹窗的是 **credential helper（helper-selector/GCM）**，不是代理。据此：
  - 修正 `github-connect-diag` / `github-push-universal` / `github-release` 三个 SKILL.md 的"清代理直连"错误表述 → 统一为"**保留 7890 代理，只禁 credential helper**"。
  - 修正 connect-diag 端口残留错误 `50730` → `51141`（WorkBuddy 注入隧道代理端口）。
  - 修正 push-universal 反模式第 2 条：不再"清代理直连"，改为"保留 7890；脚本 run() 清的是 WorkBuddy 注入的 51141 env 代理隧道，清后 git 回落 .gitconfig 的 7890 好代理"。
- 依据：用户实测 + WebSearch 高可信内容为前提，推翻历史臆测假设。方法论沉淀进 env-fix 的"⚠️ 必须先读本节"。
- 与兄弟 skill 协作链路（AGENTS 已登记）：先 **github-env-fix**（根治弹窗）→ push-universal（推码）/ release（发布）；异常走 connect-diag。
- 文档：README 技能列表加 env-fix 行 + 修正 connect-diag 描述 / CHANGELOG v1.6.0 / AGENTS 基线行 + 关键坑修正 / DEVELOPMENT 坑记录。

## v1.5.0（2026-09-03）

- 新增：github 三件套（职责单一拆分）——把 git 相关能力从"分散 + 捆绑"重构为三个独立 skill：
  - **github-connect-diag v1**（诊断）：git push 失败/挂起/弹 credentialhelperselector 的根因诊断。症状→根因对照表（GCM 弹窗 / 7890 代理挂起 / curl 劫持假失败 / schannel SSL / 空代理覆盖兜底）+ Python urllib 判网（不用 curl）+ 清代理直连 + 禁 GCM。只诊断不推送。
  - **github-push-universal v1**（推送，Python `push_repo.py`）：本地代码推到 GitHub 分支。git 优先 → 失败自动回退 GitHub Contents API（基于 HEAD 树 vs 远端树幂等对齐，PUT/DELETE，一致跳过）。只推代码不发布。
  - **github-release v1**（发布，Python `release_repo.py`）：打 tag + 创建/更新 Release + 传 zip 资产，纯 API（urllib），幂等（tag 有 Release 则 PATCH）。只发布不推码。
- 归档（移入 `skills/_archived/` + 标注）：
  - git-push-proxy-fix → 诊断职责被 github-connect-diag 吸收（空代理覆盖列为兜底分支）
  - github-contents-api-push → 推送职责被 github-push-universal 取代（Node → Python，含自动回退）
- 拆分依据：把"诊断 + 推送 + 发布"合成一个大 skill 违背单一职责、每次载入不相关上下文；改为按功能逻辑拆 3 个可独立调用也能串联的 skill。
- 与兄弟 skill 协作：先 push-universal 推码 → 再 release 发布；失败/慢/弹窗先 connect-diag 诊断。
- 文档：README 技能列表 + 归档区 / AGENTS 基线行 + 关键坑 / DEVELOPMENT 坑记录 + 归档规范 同步。

## v1.4.0（2026-09-02）

- 新增：git-push-proxy-fix v1（Git 推送代理修复技能）
  - 适用：`git push` 到 GitHub 反复失败（超时/Connection reset/Authentication failed），但 Clash 测速正常、curl 走代理也通——这种矛盾组合根因是 git 全局配置残留针对 github.com 的**空代理覆盖**（`http.https://github.com.proxy=`）强制直连被墙
  - 4 步闭环：①可靠连通验证（避开 PowerShell `curl -w` 假失败）②查 git 全局配置空代理覆盖 ③`--unset-all` 删除修复 ④重试 push + 成功判定（看 `old..new main -> main`，防被 RemoteException 误报误导）
  - 关键陷阱：PowerShell 下 `curl -w "%{http_code}"` 的 `%{}` 被 PS 解析为脚本块 → curl 报 bad argument（exit 43）输出 000 **假失败**，必须用无 `-w` 写法或 Invoke-WebRequest 验证
  - 与 github-contents-api-push 分工：本技能修"git 通道可救"的情形；彻底连不上且 api.github.com 可达时切 Contents API
  - 实战来源：Simiely/content-archive（2026-09-02）推送 v0.6.5 连挂 3 次，实为 git 全局两行空代理覆盖所致，删除后一次成功

## v1.3.0（2026-08-26）

- 新增：minimal-repro-diagnosis v1（最小单元链路诊断技能）
  - 5 步闭环：①新建最小单元复现（⚠️ 必须真实用户数据，理想样例常复现不出）②链路拆 N 步 + 每步特征统计（长度/标签集合/属性集合）③前后对比 lost/gained（lost 才是问题，gained 是正向变换勿误报）④权威资料交叉验证（MS Learn/MDN/官方文档）⑤修复 + 全链路回归
  - 特色工具：**还原开关实验台**（链路输出特征做成可开关组合 → 生成 → 复制 → 用户粘贴目标程序对比，反推外部程序认什么）；格式对照清单（按目标程序支持度标注每条声明）
  - 关键陷阱：clipboard.read() 剥壳假象（验证用真实粘贴回读）/ CSSOM cssText 丢私有属性（需字符串级处理）/ 静态缓存需重启 / 旧数据混淆
  - 实战来源：clipboard-tool v0.6.12（富文本"还原部分"——CSSOM 剥 mso 私有属性 + body 属性不在 innerHTML，两处静默丢属性定位）
  - 与 isolated-diag-page 分工：本技能侧重"数据在链路哪一步丢失/变形"，isolated-diag-page 侧重"环境/API 行不行"

## v1.2.0（2026-08-18）

- 新增：docs-ssot-convergence v1（文档 SSOT 收敛技能）
  - 七步流程：盘点角色 → 定载体（Markdown）→ 三视角重构（主线=用户旅程/支线=机制自包含/模块化=实现）→ 提取去重 → 旧快照降级标注 → 脚本化交叉核验 → 文档级场景走查
  - 文档级走查检查清单（10 类坑型，衔接 scenario-walkthrough）：声明≠可操作 / 写端点×版本语义真值表 / 触发边界防无限环 / 乐观锁粒度 / 状态机唯一入口 / 失败态恢复路径 / 异步写原子性 / 高频状态决策 / 边界值 / 降级路径
  - 实战来源：knowledge-retrieval-system v2.0.0（7 轮走查 22 坑全修：状态机矛盾/乐观锁粒度/能力缺口/版本语义全表/通知无限环）

## v1.1.0（2026-08-16）

- 新增：isolated-diag-page v1（隔离诊断页技能）
  - 方法论 4 步：环境检测（iframe/API/权限）→ 单项实测 → 写后读回自证 → 端到端模拟 + 对比找干扰项
  - 关键原则：「API 返回成功」≠「数据真实落盘」，写入后立即 read 读回自证
  - 附可复用模板 `templates/clipboard-diag.html`（剪贴板/浏览器 API 诊断页完整代码）
  - 含实战案例（富文本 Word 复制链路定位）+ 修复闭环 + 与 scenario-walkthrough 分工界定
- 补齐：github-contents-api-push（GitHub Contents API 推送技能,此前已在远端、本地目录缺失）
  - 沙箱 git push 不通时的可靠通道：Contents API 逐文件 PUT
  - 覆盖：连通探测 → 更新/新建/删除 → 远端验证 → packed-refs 修正
  - 附推送模板 `push_repo.js`
- 文档：README 技能列表 / AGENTS 基线行 / DEVELOPMENT 坑记录（一坑一篇：诊断页实战）同步；新增技能流程"三件事→五件事"

## v1.0.0（2026-08-14）

- 新增：scenario-walkthrough v3（场景走查技能）
  - 主线 6 步：能力清单 → 素材剧本+覆盖矩阵 → 分级走查 → 报告 → 修复闭环 → 迭代停止
  - 工具库 8 件：复杂度 L1-L9 / 矩阵对账 / 规则真值表 / 时序 5 问 / 探索会话 SBTM / 变更影响 / 风险评分 / 报告模板
  - 检查沉淀：checklist（代码审查 10 项 + 流程合规 10 项）+ 落盘规范
- 规范：四件套文档（README / AGENTS / DEVELOPMENT / CHANGELOG），遵循 knowledge-base 单项目规范
