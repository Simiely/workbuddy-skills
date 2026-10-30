# Illustrator 2026 脚本 API 坑位（实测）

> 环境：Adobe Illustrator 2026（build 30）、Windows 11、ExtendScript（`#target illustrator`）。
> 记录时间：2026-10-30。以下每条都是**实测撞到并验证过**的，不是文档推测。
> 换机/换版本后需重新采一遍。

## 1. `TransformAbout` 枚举不存在 → `resize()` 不能常规调用

- 现象：`it.resize(sx, sy, true, true, TransformAbout.CENTER)` → `ReferenceError: TransformAbout is not defined`。
- 判定：`typeof TransformAbout === "undefined"`（本版本确实没有这个全局枚举）。
- 绕行：
  - 能写的属性实测可用：`it.width = ...`（RasterItem 可写）、`it.position` 可读；
  - `it.resize(sx, sy, true, true)`（省略枚举）**会执行但行为不是"以中心缩放"**，实测把 2566×1445 的图缩成了 25×14 —— 不可依赖；
  - **本技能不用 resize**，改用"画板矩形剪切组"收边（零损失、可逆）。
- 附注：AI 坐标 **y 向上**，高度要按 `top − bottom` 算；写成 `bottom − top` 得到负数，会让缩放方向完全反掉（实测 `resize` 把图缩成一条线）。

## 2. `imageCapture` 只接受两个参数

- `doc.imageCapture(file, rect)` → ✅ 正常，按画板矩形精确取景。
- `doc.imageCapture(file, rect, options)` → ❌ `Illegal argument - argument 3 / Internal error`（PNG8 / PNG24 都试过）。
- `new Rectangle(...)` → ❌ `Rectangle 没有构造函数`。
- **用途**：做"改前/改后同区域逐像素比对"时用它取景，**不要用 `exportFile(PNG24)`** —— 后者按"作品外接矩形"取景，剪裁后外接矩形会变（实测 1285×724 → 1283×721），两次取景错位导致比对失效。

## 3. `doc.pageItems` 索引 0 是**最前**（最上层）

- `parent.pageItems[0]` 是最上层对象，`[length-1]` 是最底层。
- 判定叠放顺序、做 `move()` 定位时搞反会直接把元素送到错误层级。
- 实用写法：先 `sibs = []` 快照同级列表，再按身份（`===`）找索引。

## 4. 剪切组（clipping mask）的三条硬规则

1. 组内**至少两个对象**，否则 `grp.clipped = true` 抛
   `There must be at least two page items in a group to create a mask`；
2. **裁切框必须是组内最上层**（`PLACEATBEGINNING`），素材在其下（`PLACEATEND`）；
3. 把对象**移进组**用 `PLACEATEND`；用 `PLACEAFTER`（"排在某对象之后"）会把对象移到**组外面**，结果就是"组内只剩 1 个对象 → clipped 报错"。

## 5. 中文字面量在 `.jsx` 里会被破坏（ANSI vs UTF-8）

- ExtendScript 按系统 ANSI 读取**无 BOM** 的 `.jsx` → 脚本里的中文字面量变成乱码 → `doc.layers.getByName("背景")` 返回 `undefined` → 后续 `bgLayer.pageItems[0]` 抛 `TypeError: undefined 不是对象`。
- **规避**：脚本里**不写任何中文字面量**；图层名只读取、用于日志；定位靠结构特征（如"找溢出的元素"）而不是按名字找。
- 若确实要写中文：把 `.jsx` 存成 **UTF-8 with BOM** 再由 Illustrator 执行（本次未采用）。
- 同理 `.ps1` / `.vbs` 一律保持**纯 ASCII**（PowerShell 5.1 读无 BOM 的 UTF-8 脚本会报"字符串缺少终止符"）。
- 读取 UTF-8 日志要 `Get-Content -Encoding UTF8`，否则显示乱码（文件本身正常）。

## 6. `visibleBounds` 比 `bounds` 稳

- 部分对象取 `bounds` 会失败/与预期不符；`visibleBounds`（含描边、可见几何）在本次所有对象上都正常返回。
- 注意 `visibleBounds` 是 `[left, top, right, bottom]`，**y 向上**：判断"上溢出"要用 `b[1] > artboardTop`，不是 `b[1] < ...`。

## 7. 外部启动脚本时的环境事实

- `$.fileName` 为**空**（外部启动的正常现象）→ 脚本里一律用绝对路径；
- `arguments[0]` 是 `[object BridgeTalk]` 或空 → **位置参数不转发**，要传参用配置文件/环境变量；
- `#targetengine "session"` 可让变量在多次调用之间保留；
- 建议在脚本开头 `app.preferences.setBooleanPreference("ShowExternalJSXWarning", false)` 关闭"外部脚本运行"安全警告（官方做法），并在结尾 `app.quit()` 让偏好正常落盘。

## 8. 跨盘路径会触发模态 "File not found" 并阻塞

- 实测：`-r "D:\...\x.jsx"` → Illustrator 弹**模态** "File not found"（路径显示还丢了盘符），**不点掉弹窗脚本永不开始**（实测 240 s 零产出）；`-r "C:\ai\jobs\x.jsx"`（与 AI 同盘）→ 直接跑通、零弹窗。
- 反证实验：把 D 盘路径的镜像复制到 C 盘同名位置后仍不通 → **不是"剥掉盘符后能在 C 盘找到"**，而是跨盘路径本身触发。
- 结论：启动前把脚本复制到 `%SystemDrive%`（Illustrator 所在盘）→ `run_headless.ps1` 已内置。

## 9. Startup Scripts 在本版本不触发（不可作为自动化通道）

- 官方 Scripting Guide 记载：`.jsx` 放进 `C:\Program Files\Adobe\Adobe Illustrator <版本>\Startup Scripts\`（需自建文件夹）会在启动时自动执行。
- 实测（build 30）：安装成功（文件确实落到 Startup Scripts）、任务目录已建，**但派发器完全没被执行**（派发日志为空）→ **本版本不适用**。
- 结论：无头自动化走 `-r`（同盘暂存）或 COM `DoJavaScriptFile`；Startup Scripts 仅留作其他版本备选。

## 10. 目录与文件系统的坑（Windows + Git Bash + AI 混合环境）

- Git Bash 的 `/c/` `/d/` 与 Windows 盘符对应：`/d/xxx` 是 **D 盘**，`/c/xxx` 是 C 盘。写"临时文件放 C 盘"时容易搞错落点（本次就先踩了一次：文件写到了 `D:\ai\jobs`）。
- 路径含中文（`D:\work\260810\02project\527_充电效果\`）时：
  - PowerShell / AI 脚本里**不要写中文字面量**（见第 5 条）；
  - 用 Bash 的 `cp` 在盘符之间搬运文件没有编码问题（文件名原样保留），可用"AI 处理 ASCII 临时路径 → Bash 搬回中文路径"的两段式。
- Illustrator 的 `imageCapture`/`exportFile` 写文件时用**正斜杠**路径最稳（`C:/ai/jobs/x.png`）。

## 11. 无头运行的判据纪律

- **判据只看日志**：日志文件是否生成、是否出现 `done` / `ERROR`；弹窗一律不管。
- **超时不要杀 AI**：脚本可能在做大文件操作（打开 7.6 MB SVG、导出 PNG），杀掉进程会把脚本腰斩，日志永远到不了 `done`。
- 退出码语义化（0 成功 / 2 参数或文件不存在 / 3 旧实例杀不掉 / 4 脚本 ERROR / 5 超时 / 6 超时且强制杀）。
