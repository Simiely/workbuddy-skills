---
name: wpf-visual-tree-ai-eyes
description: WPF"AI 眼睛"——让 AI 直接"看"运行中的 WPF 程序做自动视觉验收。接入 WpfVisualTreeMcp(self-hosted,DEBUG-only)后用 CLI 读元素树、按 name/文本/类型定位控件、拿 screenBounds 量化坐标/间距/位移、模拟点击驱动状态,替代"改→截图→再改"人工往返。当用户报 WPF UI 形状不对/遮挡/位置不对/被拉伸/跳动,或要自动验收 UI 改动、量化控件几何(坐标/尺寸/间距)、诊断布局遮挡时使用。触发词:AI眼睛、WPF视觉验收、WpfVisualTreeMcp、visual tree、自动验收UI、控件坐标、量化UI布局、布局位移。仅适用 WPF/.NET 桌面项目;Web 端用浏览器自动化,不在本 skill 范围。
agent_created: true
---

# WPF AI 眼睛(WpfVisualTreeMcp)自动视觉验收

> 一句话:让 AI 直接读运行中 WPF 程序的元素树与控件坐标,用**数字当证据**验收 UI,替代"改→截图→再改"的人工往返。

## 适用场景(触发条件)

- UI 改动需**自动验收**(改了布局/显隐/样式,想知道坏没坏、位移了多少)
- 用户报"形状不对 / 遮挡 / 位置不对 / 被拉伸 / 跳动",需要**量化证据**而非猜测
- 需要**模拟点击**驱动状态(进批量模式、开关勾选、开弹窗),再验证结果

## A. 主线(必做流程)

### 步骤 1:确认工具已装(缺则安装)
- **动作**:检查 `C:\Users\<USER>\.workbuddy\tools\WpfVisualTreeMcp\`,应有 `server\WpfVisualTreeMcp.Server.exe` + `inspector\WpfVisualTreeMcp.Inspector.dll`(v0.12.0)
- **产出**:工具在列
- **铁律**:release zip **不含 native 注入 bootstrapper 属正常**——直接 `attach` 注入模式必失败,必须走 **self-hosted**(官方 Recommended),不要试图补 MSVC 编译

### 步骤 2:目标 app 接入(self-hosted, DEBUG-only)
- **动作**:csproj 加 Debug 且 DLL 存在条件下的 `<Reference>`(Inspector + Shared 两 DLL)+ `DefineConstants` 加 `WPFMCP_INSPECTOR`;`App.xaml.cs OnStartup` 在 `#if WPFMCP_INSPECTOR` 内 `InspectorService.Initialize(Environment.ProcessId)`,失败仅记日志
- **产出**:Debug 构建可自托管;**Release 构建完全不含 inspector 代码(纯净可发布)**
- **完整代码**:`references/wpfvisualtreemcp-setup.md`
- **铁律**:接入条件必须含 `'$(Configuration)'=='Debug'`——Release 发布产物绝不能带 inspector

### 步骤 3:启动并确认就绪
- **动作**:先退出用户实例(单实例 app 先 `taskkill /F /IM <exe>`);用 Bash 工具 **run_in_background=true** 后台启动 Debug exe;看日志出现 `inspector-ready`
- **产出**:进程跨会话存活 + 日志就绪
- **铁律**:git-bash/PowerShell 前台 `&` 启动的进程会随工具调用会话结束被回收,必须 run_in_background 托管;task 结束通知 = 实例被我们杀/用户关,属预期

### 步骤 4:attach + 看结构
- **动作**:`Server.exe list --compact` 找 PID → `attach --pid <PID> --compact`,期望回 `"inspectorStatus":"Loaded (self-hosted)"` → `tree --pid <PID> --depth 12 --compact` 管道进 python 美化打印(见 B1)
- **产出**:整棵元素树(typeName / name / text / 层级)
- **铁律**:默认 depth 太小会 miss 弹窗/深层卡片,显式 `--depth 12`

### 步骤 5:定位 + 交互
- **动作**:`find` 按 `--name ViewGrid` / `--text 编辑` / `--type CardView` 定位,返回 handle + **screenBounds(虚拟屏坐标 x/y/w/h)——量化验收的主证据**;`click --pid <PID> --handle <H> --compact` 驱动状态,期望 `method:Invoke`
- **产出**:目标控件坐标 + 状态切换(如点编辑进/出批量模式,前后 find 对比 toggle)
- **铁律**:每次交互后元素 handle 可能变化,**以最新 find 结果为准**;`--text` 可能命中多个且首元素是 ContentPresenter(非 Button),best-effort click 会失败——要选 `typeName=='Button'` 且带 name 的那个再 Invoke
- **铁律**:self-hosted 下 props 属性读取返回空 properties(上游坑 3,跨 runtime TypeDescriptor 失效)——**不要浪费时间试属性读取**,用 screenBounds + 交互做证据

### 步骤 6:量化结论 + 清理
- **动作**:用 screenBounds 算相对位置/位移,报**数字**;完事退出 Debug 实例、删临时文件/测试数据,别占单实例锁
- **产出**:"勾选框距卡右缘 20px、顶 24px,不遮标题" 这类可复核结论
- **落盘**:过程要点与结论记入当日 memory(见 C)

## ★ 典型场景:布局位移验收(改 UI 显隐/行结构时必做)

- **两根因(同一根因的两个方向)**:WPF Grid 行高由最高子元素决定——隐藏徽章/按钮类控件 → Auto 行高收缩 → 内容**上移**;或隐藏行内部分内容后 Auto 行塌缩、固定高容器(卡 Height=190, Grid Auto/*/Auto)的 `*` 行吸收多余空间 → 内容**向下拉伸**。用户报"压缩上移"与"向下拉伸"是同一根因,排查显隐改动时两个方向都要查
- **修复原则一:原位替换而非隐藏**——新控件占被替换控件同尺寸同位(如同 26×26 同 Margin),其余元素不动,行高不变
- **修复原则二:无法原位替换(整组隐藏)时用 MinHeight 锁行高**——MinHeight 必须 = 该行内**所有**固定元素之和(如分隔线 Border 高 1 + 其 margin 8 + 操作按钮 26 = **35px**),不能只算最高子控件(实测只设 26 仍差 9px,第一次修复不到位)。XAML 注释里写清计算式,防后人改错
- **验收方法(量化零位移)**:进/出目标模式前后,`find --name TitleText`(或任意行内基准元素)对比 `screenBounds.y`——**普通/模式中/退出三次 Y 完全一致即通过**。拉伸场景额外对比行尾基准:meta 行元素(如"复制 N 次"文本)与 body 摘要文本的 Y——标题→meta 间距与 body 文本 Y 在模式切换前后恒等,才证明 `*` 行未被拉高

## B. 工具库(按需查)

### B1 server CLI + JSON 解析
- **触发**:任何读树/定位/点击操作
- server exe:`C:/Users/<USER>/.workbuddy/tools/WpfVisualTreeMcp/server/WpfVisualTreeMcp.Server.exe`;CLI 输出是 JSON 到 stdout,用 python 管道解析(tree 美化脚本、find 取 handle 见 references)
- 每次交互后重新 find;state 类验证用前后对比(如批量模式 `find --name SelChk` isVisible False→True 再点回 False)

### B2 后台启动托管
- **触发**:需要 app 常驻被查
- Bash 工具 run_in_background=true 启动 Debug exe;退出实例用 `taskkill /F /IM <exe>.exe`(git-bash 单斜杠即可,双斜杠会报错)

### B3 上游坑速查(WpfVisualTreeMcp v0.12.0)
| 坑 | 现象 | 对策 |
|---|---|---|
| 1 release 无 native bootstrapper | 注入模式 attach 报 `Bootstrapper DLL not found` | 走 self-hosted(步骤 2) |
| 2 Inspector NaN/∞ 裸输出(已本地 patch) | `FormatValue` 把 double NaN 输出成非法 JSON → props 解析崩 | tools 里 Inspector.dll 是 **patch 版**;重装/升级丢 patch,重打见 references |
| 3 self-hosted props properties 为空 | Inspector 用 TypeDescriptor 跨 runtime 枚举 DP 失效 | tree/find/click/screenBounds 不受影响;属性级读取暂缺,用坐标+交互代替 |

### B4 下载 GitHub 资产(装/升工具)
- **触发**:tools 目录缺失或需升级
- 沙箱内 curl/git 走代理可能被墙或 0 字节 → 用 node fetch 写原生脚本直连 api.github.com 下载 WpfVisualTreeMcp release zip(上游仓库 faze79/WPFVisualTreeMcp)

## C. 检查与沉淀

### 代码审查点
- [ ] csproj 接入条件含 `'$(Configuration)'=='Debug'`,Release 构建不含 inspector
- [ ] `Initialize` 失败仅记日志,不崩 app
- [ ] 目标项目 TargetFramework 为 net8.0-windows 或更高(net9 可引用 net8 Inspector DLL)

### 流程合规点
- [ ] 启动用 run_in_background 托管;完事退出实例、清理临时文件与测试数据
- [ ] 验收给数字(screenBounds 算出的 px),不写"应该好了"
- [ ] 布局位移验收:普通/模式中/退出三次基准 Y 一致才判过;拉伸场景补 meta/body 间距对比
- [ ] 量化过程/上游坑/结论记入当日 memory(含命令与结果路径)

### 详细参考
- `references/wpfvisualtreemcp-setup.md`:安装步骤 / 接入完整代码 / NaN patch 重打步骤 / CLI 命令与 JSON 解析脚本
