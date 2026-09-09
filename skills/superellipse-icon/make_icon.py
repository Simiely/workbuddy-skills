#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超椭圆图标生成脚本（superellipse-icon skill 附带工具）
======================================================
把任意矩形源图按 WindowTinter 标准裁成超椭圆（squircle）应用图标：
  源图 -> 超椭圆裁剪(n=4 大尺寸 / n=8 小尺寸) -> 6 分辨率 ICO(16/32/48/64/128/256, 32bpp PNG)

依赖：Pillow（仅读写/缩放）；掩膜用纯 Python 计算，无需 NumPy。

用法：
  python make_icon.py 源图.png -o app.ico
  python make_icon.py 源图.png --sizes 16,32,48,64,128,256 --small-n 8 --large-n 4
  python make_icon.py 源图.png --verify app.ico     # 只校验 ICO 内嵌条目，不生成
"""
import argparse, io, os, struct
from PIL import Image

SMALL = (16, 32, 48)          # 小尺寸指数 n=8（更方，小图清晰）
DEFAULT_SIZES = [16, 32, 48, 64, 128, 256]

OFMT = {   # SizeToIconType wBitCount
    32: 2,  # 扩展镜像
}


def superellipse_mask(size, n, ss=4):
    """size x size 的 L 模式 0-255 alpha 掩膜：超椭圆内部不透明、四角淡出透明。
    ss 为超采样倍率，降采样后得到抗锯齿软边。"""
    ms = size * ss
    half = (ms - 1) / 2.0
    inv = 1.0 / half if half > 0 else 1.0
    ne = float(n)
    hi = [0] * (ms * ms)
    for j in range(ms):
        base = j * ms
        vy = abs(j - half) * inv
        vy_pow = vy ** ne
        for i in range(ms):
            if ((abs(i - half) * inv) ** ne + vy_pow) <= 1.0:
                hi[base + i] = 255
    mhi = Image.frombytes('L', (ms, ms), bytes(hi))
    return mhi.resize((size, size), Image.LANCZOS)


def build_ico(src, sizes, small_n, large_n, ss, out, preview_prefix):
    base = Image.open(src).convert('RGBA')
    blobs = []
    for s in sizes:
        n = small_n if s <= max(SMALL) else large_n
        rgb = base.convert('RGB').resize((s, s), Image.LANCZOS)
        out_img = rgb.convert('RGBA')
        out_img.putalpha(superellipse_mask(s, n, ss))
        if preview_prefix:
            pv = os.path.abspath('%s%d.png' % (preview_prefix, s))
            out_img.save(pv)
        buf = io.BytesIO()
        out_img.save(buf, format='PNG')
        blobs.append((s, buf.getvalue()))
    # 手写多分辨率 ICO：PNG 压缩条目，32bpp（与 WindowTinter 结构一致）
    n = len(blobs)
    hdr = struct.pack('<HHH', 0, 1, n)
    entries = b''
    offset = 6 + 16 * n
    for s, data in blobs:
        w = 0 if s == 256 else s
        h = 0 if s == 256 else s
        entries += struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(out, 'wb') as f:
        f.write(hdr + entries + b''.join(d for _, d in blobs))
    print('wrote %s (%d bytes, %d images)' % (out, offset, n))


def verify(ico_path):
    d = open(ico_path, 'rb').read()
    _, _, cnt = struct.unpack_from('<HHH', d, 0)
    print('count=%d  total=%dB' % (cnt, len(d)))
    ok = True
    for i in range(cnt):
        w, h, _, _, _, bpp, size, off = struct.unpack_from('<BBBBHHII', d, 6 + 16 * i)
        w = w or 256; h = h or 256
        fmt = 'PNG' if d[off:off + 8] == b'\x89PNG\r\n\x1a\n' else 'BMP'
        good = (bpp == 32 and fmt == 'PNG')
        ok = ok and good
        print('  %4dx%-4d %-3dbpp %-3s %dB  %s' % (w, h, bpp, fmt, size, 'OK' if good else 'X'))
    print('RESULT: %s' % ('PASS (6 entries, 32bpp PNG)' if ok else 'FAIL'))
    return ok


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('src', help='源图片路径')
    ap.add_argument('-o', '--out', default='app.ico', help='ICO 输出路径')
    ap.add_argument('--sizes', default=','.join(map(str, DEFAULT_SIZES)), help='分辨率阶梯')
    ap.add_argument('--small-n', type=float, default=8.0)
    ap.add_argument('--large-n', type=float, default=4.0)
    ap.add_argument('--ss', type=int, default=4, help='掩膜超采样倍率(抗锯齿)')
    ap.add_argument('--preview-prefix', default='app_', help='预览 PNG 前缀(空=不产预览)')
    ap.add_argument('--verify', metavar='ICO', help='仅校验既有 ICO 条目并退出')
    args = ap.parse_args()

    if args.verify:
        syscode = 0 if verify(args.verify) else 1
        raise SystemExit(syscode)

    sizes = [int(x) for x in args.sizes.split(',') if x.strip()]
    build_ico(args.src, sizes, args.small_n, args.large_n, args.ss, args.out, args.preview_prefix)


if __name__ == '__main__':
    main()