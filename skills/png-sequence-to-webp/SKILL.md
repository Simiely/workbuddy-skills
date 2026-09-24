---
name: png-sequence-to-webp
description: 把设计交付的序列帧（AE/Blender/C4D 导出的 PNG 序列、工具导出的 SVG 序列、已转好的 WebP 序列）批量转成 WebP 单帧并/或合成动态 WebP，保持目录结构与文件名序号，逐像素核验。三个核心结论：① **无损 vs 有损取决于"有没有渐变"，不取决于尺寸** —— 必须按组跑全量基准再定，别整套一刀切；② **动图不能用 Pillow `save_all=True`**（会偷合并重复帧、透明区残留上一帧），须走容器级 mux 复用原始 VP8L 码流；③ **帧率不能猜**，从同项目 mp4 的 `mdhd.timescale` / `stts.delta` 反推。当用户说「把这些序列帧转成 webp」「png 批转 webp」「svg 序列转 webp」「合成动态 webp / animated webp」「把白色改成 #XXXXXX」「序列帧压一下」「导出 webp 序列」时使用。附两个零依赖脚本：单帧批量转换 + 动图 mux（含配色替换与双重核验）。
agent_created: true
---

# png-sequence-to-webp —— 设计序列帧 → WebP 交付

职责单一：把设计交付的**序列帧**落成可用的 WebP —— ① 单帧批量转换（保结构改名）② 动态 WebP 合成 ③ 配色适配（浅色/深色版本）。不负责动效制作，不碰视频编码。

> 一句话：**先按组量，再决定**。同一批素材里扁平色组无损更小，渐变组有损才省得动 —— 既不能凭直觉选 `quality=85`，也不能凭直觉选无损，**两块基准都要跑**。

## 什么时候用

- 交付目录里有若干 `xxx_01_静帧 / _02_xxx序列 / _03_xxx循环 / _04_xxx循环` 子文件夹，每个装几十到几百张帧。
- 典型来源：AE 导出 PNG 序列、Blender 渲染序列、UI 动效切图。
- 典型规格：`160×160` / `212×212` / `256×256` / `1080×1080`，RGBA，单张 2–30 KB。
- 需要**动态 WebP** 给人看（浏览器/PPT/Windows 照片直接循环播放），或需要**浅色/深色两套配色**。

## 反模式（务必避免）

1. **动图不要用 Pillow `save_all=True`** —— 它走 libwebp `WebPAnimEncoder`，会偷合并完全相同的连续帧（实测 9 帧→8 帧、50 帧→41 帧）并改写时长；且写出的 `ANMF` flags 是 `dispose=none`，libwebp 在 no-blend 下**跳过 alpha==0 的像素**，导致透明区残留上一帧。改用容器级 mux（B2）。
2. **`ANMF` flags 不要写 `0x00`**（dispose-none）—— 带透明通道的序列会逐帧叠加。必须 `0x01`（dispose-to-background + no-blend）。
3. **不要凭"看起来是白的"写换色 FROM** —— "白色"可能是米白 `#FCF9F7`，写 `FFFFFF` 会 0 命中，静默产出没改色的文件。先量色值。
4. **不要用抽样基准下结论** —— 抽样极易被少数大体积帧带偏（实测 17 张抽样得出无损 19.7%，全量是 35.3%）。
5. **不要整套一刀切编解码参数** —— 同批素材里扁平色组和渐变组的结论可能完全相反。
6. **帧率不要猜** —— 猜错 = 整批动图速度全错。按 B4 反推或问用户。
7. **别把中间产物留在交付目录** —— 验收对照图用 `_` 前缀（`_验收对照.png`），中间序列放 `_` 前缀独占目录。

## A 主线（必做）

### 1. 只读侦察目录

```bash
cd "<目标目录>" && for d in */; do echo "=== $d"; ls "$d" | wc -l; ls "$d" | head -2; done
```

用 Pillow 汇总「尺寸 / 色彩模式」，确认没混入异尺寸（混入则不能一把梭）：

```python
for d in sorted(glob.glob('*/')):
    info = {}
    for f in sorted(glob.glob(d + '*.png')):
        im = Image.open(f); info.setdefault((im.size, im.mode), []).append(f)
    print(d, {k: len(v) for k, v in info.items()})
```

理解序列语义的实用手段（比逐张读图快得多）：
- **拼图预览**：每组均匀抽样 ≤24 帧合成 contact sheet，在**棋盘格底**上合成（`bg.paste(im,(0,0),im)`），一次看清动画结构。
- **min 投影找恒定轨道层**：`stack.min(axis=0)` 逐像素取 alpha 最小值，剩下的就是「每帧都在的低透明度轨道/底环」（曾用它识别出 90 帧加载环里 alpha≈15 的恒定圆轨）。
- **alpha 均值曲线**：逐帧 `alpha.mean()` 一眼分辨「入场展开」（单调上升）与「循环」（周期起伏），也用于确认循环首尾能否接上。

**产物**：每组帧数 / 尺寸 / 命名规律 / 语义（静帧·切换序列·循环）。

### 2. 跑全量基准，选编码参数

```python
def probe(tag, files, **kw):
    tot = 0
    for f in files:
        im = Image.open(f).convert('RGBA')
        b = io.BytesIO(); im.save(b, 'WEBP', **kw); tot += len(b.getvalue())
    print(tag, f'{tot/1024:.1f} KB')
```

候选：`lossless=True, method=6, exact=True` / `quality=95` / `quality=80`。

**判定规则**（看每组 `无损 / q90` 两列）：
- 差额 < 10% → 该组扁平色，**用无损**（同体积下零误差，严格占优）。
- 差额悬殊 → 该组含软渐变，此时才是有损的战场。

**混合模式是最优解**：扁平色组无损 + 渐变组有损，体积与全有损几乎相同（实测 223.6K vs 223.0K）但扁平部分保持 0 误差。全有损被混合**严格占优**，不要选。

**产物**：每组定下模式（无损 / q90），例：静帧+切换序列无损、循环帧 q90。

### 3. 单帧转换（保结构改名）

```bash
PY="C:/Users/<USER>/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SK="C:/Users/<USER>/.workbuddy/skills/png-sequence-to-webp"   # 本机安装位
"$PY" "$SK/convert_seq_to_webp.py" "<源目录>"                 # 默认无损 → <源目录>_webp
"$PY" "$SK/convert_seq_to_webp.py" "<源目录>" --q90           # 全部有损
"$PY" "$SK/convert_seq_to_webp.py" "<源目录>" --mixed --gradient 循环   # 混合：含"循环"的组有损
```

铁律：
- `exact=True` **必须加**：保留透明区 RGB，才能做到真·逐像素 0 误差（否则透明区 RGB 被清零，比对该出"差异"）。
- 输出到**同级目录 + `_webp` 后缀**，子文件夹名与文件名序号**完全不变**，只换扩展名 → 前端按序号取帧的逻辑一行不用改。
- 脚本内置逐像素核验，**任何一张不一致即非零退出**。

**产物**：`<源目录>_webp/` + 「N / N 张 100% 一致」的读数。

### 4. 合成动态 WebP

```bash
"$PY" "$SK/mux_anim_webp.py" "<序列帧目录>" --fps 30 [--out out.webp] [--once]
```

脚本跑完会打印结构层 + 解码层双重核验，**全过才输出 `RESULT: OK`**。输出命名建议 `<编号>_<序号>_<英文名>_anim.webp`，与既有交付命名体系保持一致。

批量多组时用循环（一个交付目录常带 3–4 个序列子目录）：

```bash
B="<交付目录>"
"$PY" "$SK/mux_anim_webp.py" "$B/<...>_02_xxx序列" --fps 30 --out "$B/362_02_XXXSequence_anim.webp"
"$PY" "$SK/mux_anim_webp.py" "$B/<...>_03_xxx循环" --fps 30 --out "$B/362_03_XXXLoop_anim.webp"
```

`_01_静帧` 是单帧或彼此独立的元素（如 `Background` + `Microphone`），**不合成动图**。

**产物**：各组 `*_anim.webp`。

### 5. 配色适配（浅色 / 深色版本，按需）

源素材是**单色**时（进度环、波形、扫描线这类很常见：不透明区 `唯一 RGB == 1`，只有 alpha 在变）直接换色：

```bash
"$PY" "$SK/mux_anim_webp.py" "<序列目录>" --fps 30 \
  --recolor FCF9F7=2E2D2D --out "<目录>/xxx_2E2D2D.webp"
```

- **先量源色值再写 FROM**（B5 的色值统计）。同批素材可能一个用纯白 `#FFFFFF`、一个用米白 `#FCF9F7` → **逐组量，别一把梭**。
- 多色素材（蓝底 + 白图标）只指定要换的那个色，`--recolor` 可给多次。
- 改色必然重编码（无损 VP8L），核验口径随之从「码流 IDENTICAL」改为「**alpha 与源逐字节一致 + 不透明区 RGB 唯一等于目标色**」。

**产物**：`xxx_<色值>.webp` + 验收对照图。

### 6. 交付

```bash
"$PY" "$SK/<脚本>" --verify ...   # 按 C 组清单核验
```

交付话术见文末；**路径、体积、误差三件事一次说全**。

## B 工具库（按需查）

### B1 convert_seq_to_webp.py —— 单帧批量转换

| 参数 | 默认 | 说明 |
|---|---|---|
| `src`（位置） | 必填 | 源目录（含若干序列子文件夹） |
| `dst`（位置） | `<src>_webp` | 输出目录 |
| `--q90` / `--q85` | 关 | 全部有损 |
| `--mixed` | 关 | 扁平色组无损 + 指定组有损 |
| `--gradient` | `""` | 配合 `--mixed`，按子目录名关键词（逗号分隔）指定有损组 |

打印按组的 源/转出/占比 表 + 模式标注，末尾给「N 张一致 / M 张失败」。失败即非零退出。

### B2 mux_anim_webp.py —— 动态 WebP 合成（容器级 mux）

| 参数 | 默认 | 说明 |
|---|---|---|
| `seq_dir`（位置） | 必填 | 序列帧目录（`*.webp`，按文件名排序） |
| `--fps` | 30 | 帧率（**先按 B4 自证**） |
| `--out` | `<父目录>/<目录名>_anim.webp` | 输出路径 |
| `--loop` | `0` | 0 = 无限循环 |
| `--once` | 关 | 只播一次（loop=1） |
| `--recolor FROM=TO` | 无 | 替换 RGB，可多次；alpha 不变 |

**原理**：直接复用源文件里已编码好的 VP8L 码流，塞进 `ANMF` 块 —— 不指定 `--recolor` 时是**零重编码**，解码像素与原帧逐字节一致。

关键实现点（对应 ANMF 规范，写错就静默出瑕疵）：

- **flags 位布局（RFC 9649）：bit0 = disposal method，bit1 = blending method。** 必须 `0x01`（dispose-to-background + no-blend）= 「每帧先清画布、再整帧绘制」。实测矩阵（9 帧带透明序列，判据 = 解码读回逐字节一致）：

  | flags | 结果 |
  |---|---|
  | `0x00` dispose-none + no-blend | ❌ frame1~8 全不一致 |
  | `0x02` 仅首帧（Pillow 的配置） | ❌ 同上 |
  | **`0x01` dispose-to-bg + no-blend** | ✅ **全部一致** |
  | `0x02` 全部 / `0x03` | ✅ 一致，但依赖"帧覆盖整画布"，不稳健 |

- `ANMF` 内的帧数据是「**带 chunk 头的完整 VP8L chunk**」（不是裸 bitstream），照搬源文件切片即可，别画蛇添足。
- `VP8X` flags = `0x12`（animation + alpha），canvas 24-bit LE 存 `宽-1 / 高-1`；`ANIM` 块 6 字节（背景 BGRA + loop）。
- **帧时长按累计时间取整分配**：`d_i = round(i*1000/fps) - round((i-1)*1000/fps)` → 30fps 得 `33,34,33,33,34,33,33,34,33`，9 帧精确 300ms。固定 33ms 会让 90 帧变成 **2.97s**（少 30ms）。
- 双重核验：结构层（ANMF 数量 / 每帧时长 / 每帧码流 vs 源文件字节）+ 解码层（回读逐像素）。

**体积预期**：无损 mux 不做帧差分，可能**比逐帧总和还大**（实测 405 KB vs 逐帧 374 KB）。要压体积就必须接受重编码，别指望 mux 两头兼顾。

### B3 SVG 序列的浏览器光栅化

SVG 序列不能直接进 WebP 编码器。**光栅化器的选择决定成品真假**：

| 光栅化器 | `feGaussianBlur`/filter | `mask` | 结论 |
|---|---|---|---|
| **Chromium / Edge（headless）** | ✅ 完整 | ✅ 完整 | **唯一可靠** |
| cairosvg / rsvg-convert | ❌ 静默忽略 | 部分 | 画面"对"但光晕全丢 |
| ImageMagick（内置 MSVG） | 差 | 差 | 同上 |

含 `<filter>` / `<mask>` / `<radialGradient>` 的一律走浏览器（用本机已有 Edge + `playwright-core`，不必另下 Chromium）：

```js
const { chromium } = require('playwright-core');
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  headless: true,
  args: ['--force-color-profile=srgb', '--disable-lcd-text', '--hide-scrollbars'],
});
const page = await browser.newPage({ viewport: { width: 1080, height: 1080 }, deviceScaleFactor: 1 });
await page.goto('file:///abs/path/frame_0000.svg', { waitUntil: 'load' });
await page.screenshot({ path: 'frame_0000.png', omitBackground: true, type: 'png' });
```

- **`omitBackground: true` 必须加**，否则截图铺白底、alpha 全丢（结果"每帧都不透明"，容易被误当成素材没问题）。
- SVG 作为**顶级文档**加载时无 `body` margin 问题，`width/height` 与 viewport 一致即 1:1，别套 HTML。
- 分辨率从 SVG 头部 `width="(\d+)"` 正则取，不要写死。速度参考：1080×1080 × 90 帧 ≈ **4.5 秒**。
- **光栅化完先读像素自证**：用**覆盖曲线**（逐帧 `alpha>0` 占比）+ 回查 SVG 源码坐标，不要靠单帧观感定生死。扫描/入场类动效首尾帧全透明是常态（曾把"mask 圆心在画布外"的正确渲染误判成渲染失败）。

### B4 帧率怎么确定（别猜）

优先级：① 用户已确认的规格（同批次直接沿用，别重复问）→ ② 从同项目导出的 mp4 反推 → ③ 都没有才问。

```
fps = mdhd.timescale / stts.delta
```

| 常见 fps | timescale | delta |
|---|---|---|
| 30 | 30000 | 1000 |
| 25 | 25000 | 1000 |
| 29.97 | 30000 | **1001** |

实测：人脸弹窗 mp4 → `timescale=30000, delta=1000` → 30fps（190 帧 / 6.333s）；声纹弹窗 mp4 → 同样 30fps（221 帧 / 7.367s）。**看到 1001 就是 29.97，别当成 30。**

解析要点：`stts` 藏在 `moov > trak > mdia > minf > stbl > stts`，**不在 `mdia` 的直接子级** —— 只在 `mdia` 下遍历会找不到它。另外 `mvhd` 的 timescale 通常是 90000（时间基，与帧率无关），别拿它算。

### B5 素材自检（无依赖，纯 struct / numpy）

**容器结构自检**（不装任何图像库）：

```python
import struct
d = open('x.webp','rb').read()
off = 12
while off + 8 <= len(d):
    cid = d[off:off+4]; sz = struct.unpack('<I', d[off+4:off+8])[0]
    print(cid.decode('latin1'), sz)
    if cid == b'ANMF':
        p = off + 8
        print('   dur=%d flags=0x%02x' % (int.from_bytes(d[p+12:p+15],'little'), d[p+15]))
    off += 8 + sz + (sz & 1)
```

`ANMF` 的 `flags` 应是 `0x01`（不是 `0x00`）、`VP8X` flags 应是 `0x12`。

**色值统计**（决定 `--recolor` 的 FROM，以及判断是否单色）：

```python
import numpy as np
from PIL import Image
im = Image.open(f); im.seek(0)
A = np.array(im.convert("RGBA")); px = A[A[:,:,3] > 0][:, :3]
print("唯一 RGB =", len(np.unique(px, axis=0)), "主色 =", np.unique(px, axis=0)[np.unique(px, axis=0, return_counts=True)[1].argmax()])
```

`唯一 RGB == 1` 即可整体换色。

### B6 验收对照图

首次转新格式、或做了配色适配时，导一张对照图比任何口头承诺都有说服力 —— 单纯给色值，用户看不出「在浅底上到底还看不看得见」。

- **单帧转换**：`源 | 转出 | 差异 ×20` 三联。
- **配色适配**：行 = 白底 / 浅灰底，列 = 原色 / 改色。
- 文件用 `_` 前缀（`_配色对照_04_识别循环.png`），一眼可辨是附属物。

画图要点：
- **PIL 默认字体不含中文**：`ImageDraw.text` 不传 `font=`，中文会渲染成方块豆腐。必须 `ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 12)`；纯英文标签用 `arial.ttf` 更紧凑。
- **棋盘底色跟着素材走**：浅色素材用**浅棋盘**（196/232 灰阶），深色素材用深棋盘；沿用错了深灰图标会糊在底里。
- **标签文字加描边**：`dr.text(..., stroke_width=2, stroke_fill=...)`，否则粉/黄系标签压在浅底上看不清。

## C 检查与沉淀

### 代码审查点
- [ ] 单帧转换写了 `exact=True`（否则透明区 RGB 被清零，"逐像素一致"必然失败）。
- [ ] 动图 `ANMF` flags = `0x01`、`VP8X` flags = `0x12`（容器结构自检 B5 可验）。
- [ ] 帧时长走累计取整分配，不是固定 `1000/fps` 取整（否则长序列总时长偏短）。
- [ ] `--recolor` 的 FROM 是从素材量出来的真实色值，且脚本报了命中像素数（0 命中要当失败处理）。
- [ ] 核验是「结构层 + 解码层」双证据，不是只看文件生成成功。

### 流程合规点
- [ ] 基准**按组全量**跑过，不是抽样、不是一刀切。
- [ ] 帧率有据（用户规格 / mp4 反推），不是拍的。
- [ ] 子文件夹结构与文件名序号原样保留，只换扩展名。
- [ ] 逐像素核验给到「N / N 张 100% 一致」的读数。
- [ ] 中间产物在 `_` 前缀目录/文件名下，交付目录干净。
- [ ] 交付时报了**完整绝对路径**（路径 / 体积 / 误差一次说全）+「在哪能看到效果」（哪个软件打开、要不要额外解码器）。
- [ ] 写完回读文件名核验（见"沉淀"里的改名坑）。

### 沉淀
- 遇到新坑记入本 skill 或工作仓库 `DEVELOPMENT.md`「坑记录（一坑一篇）」。

**已知坑（本 skill 收录）**：
- **报告口径**：有损的"最大像素差 = 255"常全部出现在**完全透明**的像素上（RGB 无意义）。要先按 `alpha > 0` 掩码再算，或改用预乘 alpha。分开报两档：实体像素（`α ≥ 128`）峰值 2/255、均值 1.00/255（真实观感）；含半透明边缘峰值 255（不可见，但要在图注标注，否则用户以为压坏了）。
- **别用 MAE 充 RMSE** 再去套 PSNR 公式（会得到"58 dB"这种假高值）。要么老实算 MSE，要么只报 maxErr/meanErr + 不透明区 PSNR。
- **判断"有损伪影是否可见"要用对放大倍数**：`2×` 接近真实观感（定"能不能接受"），`8×` 定"伪影在哪、什么形态"。16px 宏块 = 160px 图的 10%，不是亚像素级，不能拿"看不到"糊弄。
- **改色会让原本"看不见"的低 alpha 层显出来**：米白贴浅底 = 隐形，换成深灰后同 alpha 也会显形。这是设计上正常的渐变拖尾，不是瑕疵，但要在对照图里呈现并说明。
- **Git Bash 下的中文路径**：先 `cd` 进目录再相对操作，避免把中文路径拼进命令时乱码。
- **写完必须回读文件名核验，别假设自己写的名字还在**：实测遇到输出目录被**外部进程/另一会话**改名（写出的 `frame_0000..0089.png` 被改成倒序的 `xulie_01..90.png`；靠 mtime 与单帧字节数确认是同一批产物被改名）。规避：中间产物写进自己独占的 `_` 目录，交付物最后一次性落盘，落盘后 `ls` 回读确认。

## 交付话术

第一句给**完整绝对路径**（序列目录 + 动图文件），然后一张体积对照表 + 一句「逐像素核验 N/N 通过」，最后说明「子文件夹结构与文件名序号原样保留，前端只需把 `.png` 改成 `.webp`」。

做了动图就补一句帧率与总时长（如「90 帧 / 3000ms / 30fps，无限循环」）；做了改色就补 alpha 是否原样保留、命中多少像素。

**别让用户来问路径。**
