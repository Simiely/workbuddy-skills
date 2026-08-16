---
name: isolated-diag-page
description: 隔离诊断页法——针对"环境相关/API 相关/多环节链路说不清"的 bug,写一个独立诊断页面,实测每个环节 API 的可用性与数据落盘情况(写后读回自证),用真实数据定位根因,不靠猜测。当用户报的 bug 反复修复无效、涉及浏览器 API(剪贴板/权限/iframe)、环境差异(预览面板 vs 独立浏览器)、或链路环节多且怀疑有干扰项时使用。触发词:写个测试页、针对性测试、诊断页、实测一下、为什么还是不行、找出干扰项。
---

# 隔离诊断页法(Isolated Diag Page)

> 一句话:不猜。写一个**独立于主应用的诊断页面**,把疑似出问题的每个环节做成可点击的测试按钮,全部用**实测数据**说话——尤其是「写入后立即读回自证」,区分「API 返回成功」与「数据真实落盘」。

## 适用场景(触发条件)

- Bug 涉及**浏览器 API**:剪贴板(clipboard.read/write/execCommand/paste 事件)、权限(Permissions Policy)、iframe 沙箱
- **环境差异**:预览面板(iframe)里不行,独立浏览器标签页却行(或反之)
- **链路环节多**(复制→存→显→再复制),且怀疑有**干扰项**叠加
- 已多轮修复无效、补丁叠补丁——此时停止改主应用代码,先诊断环境

## 核心方法论(4 步)

### 第 1 步:环境信息检测(先摸清场地)

诊断页首屏输出环境事实(不猜):

```
window !== top (iframe?): true/false   ← iframe 判定
navigator.clipboard: 存在/不存在        ← API 可用性
ClipboardItem: 存在/不存在
isSecureContext: true/false
document.hasFocus(): true/false
```

**依据**:iframe 里 Clipboard API 需要父页面 `allow="clipboard-write/read"`(Permissions Policy),未授权则 API 被拦;execCommand 在沙箱 iframe 可能失败。**先确认是不是 iframe、API 在不在,再谈逻辑。**

### 第 2 步:单项 API 实测(每个环节一个按钮)

把疑似环节拆成独立按钮,每个按钮做**一件事**并输出结果:

| 环节 | 按钮动作 | 输出 |
|---|---|---|
| 写入 A | `navigator.clipboard.write(ClipboardItem html+plain)` | 成功/失败 + 错误名 |
| 写入 B | `execCommand('copy')` + copy 事件 setData | 返回 true/false |
| 读取 A | `navigator.clipboard.read()` → 遍历 types | types 列表 + html 长度 |
| 读取 B | paste 事件 `e.clipboardData.getData('text/html')` | html 长度 + 关键标记 |
| 读取 C | `navigator.clipboard.readText()` | 文本前 120 字 |

### 第 3 步:写后读回自证(关键!不靠粘贴判断)

**「API 返回成功」≠「数据真实落盘」**。每个写入按钮执行后,**立即用 read() 读回**,打印:

```
✅ 写入成功
读回 html 长度: 44          ← 长度是否≈输入?缩水 = 被浏览器处理(sanitize/压缩)
含 <style>: true/false      ← 关键标记是否保留
含 xmlns:w: true/false      ← Word 识别来源的标记
前 200 字: ...
```

**判定表**:

| 读回结果 | 结论 |
|---|---|
| 读回长度 ≈ 输入长度,关键标记在 | 写入真实成功,问题在接收端/目标应用 |
| 读回长度 << 输入,标记丢失 | 浏览器强制处理(如 Chromium 122+ `ClipboardWellFormedHtmlSanitizationWrite` 剥 `<style>`/html/xmlns 只留 inline style)——**这是铁律,无法绕过,只能适配** |
| 读回无该类型 | 写入实际失败(返回成功是假象) |

### 第 4 步:端到端最小模拟 + 对比定位干扰项

- **端到端最小模拟**:把完整链路浓缩成一个按钮(如「把刚粘贴的 Word html 用 execCommand 复制 → 读回」),一次性复现"来源→处理→落盘"关键路径
- **对比法**:诊断页(干净环境)与主应用(有干扰)跑同一操作——
  - 诊断页成功 + 主应用失败 → **干扰项在主应用**(全局监听冲突/环境差异/数据内容不同)
  - 两边都失败 → 环境或浏览器行为本身

## 实战案例(2026-08-16 富文本 Word 复制,本方法全程定位)

**问题**:富文本卡复制 → Word 粘贴无格式/字体变宋体,多轮修复无效。

**诊断页实测结论**(每一步都有数据):
1. 环境:非 iframe,clipboard/execCommand/paste 全可用
2. `clipboard.write` 完整 Word html → 读回仅 **98B**(Chromium 122+ sanitize 剥 html/head/style/xmlns)
3. `execCommand + setData` 原始 Word html(43150B)→ 读回 4590B,**inline style 完整保留**(`font-family:等线 Light;font-size:24pt`)
4. paste 事件能取到完整原始 Word html(含 `xmlns:w`)
5. **端到端**:execCommand 复制带 xmlns 的完整文档 → 用户粘贴 Word → **格式正确 ✅**

**根因链**:浏览器写剪贴板强制剥 style 块/xmlns 只留 inline style + Word 识别"来自 Word"靠 `xmlns:w` 标记 + execCommand setData 不受 sanitize 影响 → 解法 = 存入时样式内联化(`normalizeRichHtml`)+ 复制时包装 xmlns(`buildWordDoc`)+ execCommand 主路径。

**误区纠正**:期间多次"修复无效"实为**测试方法错误**(粘贴到 WorkBuddy 聊天框=纯文本输入框必无格式;演示数据是 style 块版本未内联)——诊断页数据 + 追问粘贴目标后真相大白。

## 诊断页模板要点

- **独立 HTML 文件**,不依赖主应用 JS/CSS(避免主应用干扰),放服务可访问路径(如 `/diag.html` 路由)
- 每个环节独立 `<button>` + `<pre id="rXxx">` 输出,结果就地显示,用户直接复制回传
- 输出要带**关键标记检查**(`含 <style>`/`含 xmlns:w`/`含 <b>`),一眼看出是否被处理
- 中文界面,操作步骤清晰(先做什么→再做什么)
- 服务端加最小路由(`server.mjs` 里 `pathname === "/diag.html"` 读文件返回)

## 检查清单(用前对照)

- [ ] 环境信息检测(iframe?API 存在性?权限状态?)已输出
- [ ] 每个疑似环节有独立按钮
- [ ] 写入类按钮都有「写后读回自证」(长度 + 关键标记)
- [ ] 端到端最小模拟按钮(复现完整链路关键路径)
- [ ] 引导用户确认**粘贴目标**(纯文本输入框必无格式,先排除)
- [ ] 诊断页与主应用对比(找干扰项)
- [ ] 修复后**回归**:改完主应用,再跑诊断页同一步骤,确认读回结果达到预期才关闭

## 可复用模板

- **`templates/clipboard-diag.html`**:剪贴板/浏览器 API 诊断页完整模板——含环境检测(含 `navigator.permissions.query` 权限状态)、写入 A/B + 读回自证、读取 A/B、端到端模拟。复制到项目服务可访问路径即可用。
- 服务端接入(如 Node http server 加路由):
  ```js
  if (url.pathname === "/diag.html") {
    const html = fs.readFileSync(path.join(__dirname, "public", "diag.html"));
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "X-Content-Type-Options": "nosniff" });
    return res.end(html);
  }
  ```
- 通用化提示:不同场景改 `templates/clipboard-diag.html` 里的测试 html 常量、按钮动作(如换成文件 API/权限 API),骨架(环境→单项→读回→端到端)不变。

## 修复闭环(诊断后的标准动作)

1. 诊断页定位根因(数据说话)
2. 改主应用(一次改一处,不叠补丁)
3. **回归**:重跑诊断页同一步骤,读回结果达到预期(如关键标记保留/长度不再缩水)
4. 再让用户在主应用 + 真实目标(Word/目标软件)验证
5. 同步沉淀:根因 + 解法写入项目 DEVELOPMENT.md(一坑一篇)、坑库、CHANGELOG

## 与 scenario-walkthrough 的分工

- **scenario-walkthrough**:走**代码逻辑链路**(函数调用/状态机/权限矩阵),静态分析为主——用于"逻辑通不通"
- **本 skill(隔离诊断页)**:实测**运行环境与 API 行为**(浏览器权限/iframe/数据落盘)——用于"环境/API 到底行不行"
- 组合用法:逻辑走查发现问题 → 隔离诊断页实测环境 → 数据定位 → 修复 → 双回归(逻辑链 + 诊断页)

## 反模式(避免)

- ❌ 不写诊断页直接猜/改主应用(补丁叠补丁)
- ❌ 只测"API 返回成功"不读回(成功可能是假象)
- ❌ 忽略粘贴目标(WorkBuddy 输入框/记事本 = 纯文本,必无格式)
- ❌ 忽略环境差异(预览 iframe vs 独立浏览器,剪贴板权限不同)
- ❌ 修复后不回归诊断页(改完没验证是否真解决)
