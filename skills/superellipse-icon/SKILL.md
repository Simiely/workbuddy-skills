---
name: superellipse-icon
description: 把任意矩形源图按 WindowTinter 超椭圆标准裁成应用图标——超椭圆裁剪(n=4 大尺寸/n=8 小尺寸) + 6 分辨率 ICO(16/32/48/64/128/256, 32bpp PNG)。当用户说"图标是方形的要裁圆角/做程序图标/生成 app.ico/图标标准化"时使用。附零配置 make_icon.py，仅需 Pillow。
agent_created: true
---

# superellipse-icon —— 超椭圆图标裁剪（应用图标标准化）

职责单一：把矩形源图（有方形角/白底/四角是纯背景色）裁成**超椭圆（squircle）**应用图标，并输出标准多分辨率 `app.ico`。不负责画图、调色或别的图像处理。

**标准出处**：WindowTinter 仓库 `DEV.md` 第17节「超椭圆图标」——源图 → 超椭圆裁剪（n=4 大尺寸 / n=8 小尺寸）→ 6 分辨率 ICO（16/32/48/64/128/256）。本 skill 把该标准固化为可复用工具。

## 什么时候用
- 程序图标显示成方形，四角露底色/白角，要裁成四角平滑透明的圆角图标。
- 用户要求「把这张图做成程序/应用图标」「生成 app.ico」「图标标准化」。
- 源图为 1:1 方形设计稿（如 1024/2048），内容居中、四角为纯背景色。

## 反模式（务必避免）
1. **不要用 Pillow 的多尺寸 ICO 保存** —— `img.save('.ico', sizes=..., append_images=...)` 实测**只写第一张**（16px），产出单条目 ICO。必须**手动组装** `ICONDIR + 逐尺寸 PNG 条目`（见 make_icon.py `build_ico`）。
2. **不要硬裁正圆** —— 参考实现是**超椭圆（squircle）**：大尺寸 n=4（圆润）、小尺寸 n=8（更方、小图不糊）。硬圆在小尺寸会失真。
3. **掩膜无需 NumPy** —— 超椭圆掩膜用纯 Python（`abs^ne` 逐像素）即可，只读写/缩放依赖 Pillow（`pip install pillow`）。
4. **四角要抗锯齿软边** —— 掩膜做 `ss=4` 超采样后 `LANCZOS` 降采样，边缘柔和，不做会有锯齿硬边。
5. 正式产出只留 `.ico`，临时 PNG/掩膜不进版本库。

## A 主线（必做）
1. **就位**：确认源图为方形且内容主体居中（1:1 最佳；如「方形珊瑚粉底 + 居中液态玻璃圆徽标」）。
2. **定位脚本**：`make_icon.py`（本 SKILL 同目录）。仅依赖 Pillow：`py -3.12 -m pip install pillow`。
3. **执行**：
   ```bash
   py -3.12 make_icon.py 源图.png -o app.ico
   ```
   产出 `app.ico`（6 分辨率、超椭圆四角透明）+ 各尺寸预览 PNG（`app_<size>.png`）。
4. **校验**：`py -3.12 make_icon.py 源图.png --verify app.ico`，确认 6 条目 / 32bpp / PNG 压缩，见 C 组。
5. **接入**：PyInstaller `EXE(icon=app.ico)`；tkinter 窗口图标用 `iconbitmap`（打包取 `sys._MEIPASS` 内附版，源码取 `dirname(__file__)`，异常吞 `tk.TclError`）。

## B 工具库（按需查）

### B1 make_icon.py 参数
| 参数 | 默认 | 说明 |
|---|---|---|
| `src`（位置） | 必填 | 输入图片路径 |
| `-o/--out` | `app.ico` | ICO 输出路径 |
| `--sizes` | `16,32,48,64,128,256` | 分辨率阶梯（默认即标准 6 档） |
| `--small-n` | `8` | 小尺寸超椭圆指数（≤48） |
| `--large-n` | `4` | 大尺寸超椭圆指数（≥64） |
| `--ss` | `4` | 掩膜超采样倍率（抗锯齿） |
| `--preview-prefix` | `app_` | 预览 PNG 前缀（空字符串则不产预览） |

### B2 校验命令
```bash
py -3.12 make_icon.py 源图.png --verify app.ico
```
应输出 6 行，每行形如 `  256x256 32bpp PNG  …  OK`，RESULT 为 PASS。

### B3 产物结构（人类可读校验，纯 struct）
```python
import struct
d=open('app.ico','rb').read()
_,_,cnt=struct.unpack_from('<HHH',d,0)          # 应cnt=6
for i in range(cnt):
    w,h,_,_,_,bpp,size,off=struct.unpack_from('<BBBBHHII',d,6+16*i)
    print((w or 256),(h or 256),bpp,'PNG' if d[off:off+8]==b'\x89PNG\r\n\x1a\n' else 'BMP')
```

## C 检查与沉淀

### 代码审查点
- [ ] ICO 内置 **6** 个条目，尺寸齐全（16/32/48/64/128/256），无缺档。
- [ ] 每条目 **32bpp ARGB**、**PNG 压缩**（非 BMP 4bit/8bit）。
- [ ] 四角透明（超椭圆外 alpha=0），边缘抗锯齿柔和、无锯齿硬边。
- [ ] 小尺寸（≤48）指数 n=8、大尺寸（≥64）指数 n=4。

### 流程合规点
- [ ] 源图内容主体无裁缺（徽标/主体完整居中）。
- [ ] 正式产出只留 `.ico`，临时 PNG/掩膜不进版本库。
- [ ] 接入 exe 后用 System.Drawing `Icon.ExtractAssociatedIcon(exe)` 提取内嵌图标目视比对（确认非默认 PyInstaller 图标）。

### 沉淀
- 遇到新坑（如 Pillow `append_images` 只写一张）记入工作仓库 `DEVELOPMENT.md`「坑记录（一坑一篇）」。
- 本 skill 由登录态切换器图标接入实战沉淀（2026-09-09）。