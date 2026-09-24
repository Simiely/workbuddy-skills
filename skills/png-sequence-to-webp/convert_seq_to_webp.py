# -*- coding: utf-8 -*-
"""序列帧 PNG -> WebP 批量转换 + 逐像素核验

用法:
    python convert_seq_to_webp.py <源目录> [输出目录] [--q90|--q85|--mixed]

默认: 无损 WebP (lossless=True, method=6, exact=True)，输出到 <源目录>_webp

模式说明:
    默认(无损)      全部帧无损，逐像素 0 误差 —— 小尺寸扁平色 UI 素材首选
    --q90           全部帧有损 quality=90
    --mixed         扁平色组无损 + 梯度组 q90（需人工指定哪几组是梯度组，见 --gradient）
    --gradient 前缀  配合 --mixed，指定按有损处理的子目录名前缀/关键词

保持子文件夹名与文件名序号完全不变，只把 .png 换成 .webp。
每个输出文件写完立刻重读回解码，与源做逐像素比对，任何一张不一致即报错退出。
"""
import argparse
import io
import os
import sys
from glob import glob

import numpy as np
from PIL import Image

LOSSLESS_KW = dict(lossless=True, method=6, exact=True)


def encode(im, mode="lossless", quality=90):
    buf = io.BytesIO()
    if mode == "lossless":
        im.save(buf, "WEBP", **LOSSLESS_KW)
    else:
        im.save(buf, "WEBP", lossless=False, quality=quality, method=6)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--q90", action="store_true")
    ap.add_argument("--q85", action="store_true")
    ap.add_argument("--mixed", action="store_true")
    ap.add_argument("--gradient", default="", help="--mixed 时按有损处理的子目录关键词，逗号分隔")
    a = ap.parse_args()

    src_root = os.path.abspath(a.src)
    dst_root = os.path.abspath(a.dst) if a.dst else src_root + "_webp"
    mode = "lossless"
    quality = 90
    if a.q90:
        mode, quality = "lossy", 90
    elif a.q85:
        mode, quality = "lossy", 85
    elif a.mixed:
        mode = "mixed"
    gkeys = [k.strip() for k in a.gradient.split(",") if k.strip()]

    if not os.path.isdir(src_root):
        print("源目录不存在:", src_root)
        return 1

    subdirs = sorted(d for d in os.listdir(src_root)
                     if os.path.isdir(os.path.join(src_root, d)))
    if not subdirs:
        print("未找到子文件夹:", src_root)
        return 1

    stat = []
    n_ok = n_fail = 0
    for sub in subdirs:
        sdir = os.path.join(src_root, sub)
        ddir = os.path.join(dst_root, sub)
        os.makedirs(ddir, exist_ok=True)

        if mode == "mixed":
            use = "lossy" if any(k in sub for k in gkeys) else "lossless"
        else:
            use = mode

        pngs = sorted(glob(os.path.join(sdir, "*.png")))
        s_sum = d_sum = 0
        bad = []
        for src in pngs:
            base = os.path.splitext(os.path.basename(src))[0]
            dst = os.path.join(ddir, base + ".webp")
            with Image.open(src) as im:
                im = im.convert("RGBA")
                data = encode(im, use, quality)
                a_arr = np.asarray(im, dtype=np.uint8)
            with open(dst, "wb") as fh:
                fh.write(data)
            with Image.open(dst) as rt:
                b_arr = np.asarray(rt.convert("RGBA"), dtype=np.uint8)
            if a_arr.shape == b_arr.shape and bool((a_arr == b_arr).all()):
                n_ok += 1
            else:
                n_fail += 1
                bad.append(base)
            s_sum += os.path.getsize(src)
            d_sum += os.path.getsize(dst)
        stat.append((sub, use, len(pngs), s_sum, d_sum, bad))

    T = [0, 0]
    print("=" * 88)
    print(f"{'子文件夹':<46}{'模式':>9}{'帧':>5}{'源':>11}{'转出':>11}{'占比':>8}")
    print("-" * 88)
    for sub, use, n, s, d, bad in stat:
        name = sub if len(sub) <= 44 else sub[:18] + "..." + sub[-23:]
        lab = "无损" if use == "lossless" else f"q{quality}"
        print(f"{name:<46}{lab:>9}{n:>5}{s/1024:>10.1f}K{d/1024:>10.1f}K{d/s*100 if s else 0:>7.1f}%")
        T[0] += s
        T[1] += d
    print("-" * 88)
    lab = "无损" if mode == "lossless" else ("混合" if mode == "mixed" else f"q{quality}")
    print(f"{'合计':<46}{lab:>9}{n_ok+n_fail:>5}{T[0]/1024:>10.1f}K{T[1]/1024:>10.1f}K{T[1]/T[0]*100:>7.1f}%")
    print("=" * 88)
    print(f"逐像素核验: {n_ok} 张一致 / 失败 {n_fail} 张")
    for sub, _, _, _, _, bad in stat:
        for b in bad:
            print(f"  !! {sub}\\{b}")
    print("输出目录:", dst_root)
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
