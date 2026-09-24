# -*- coding: utf-8 -*-
"""
webp 序列帧 -> 动态 webp / animated WebP（容器级 mux，零重编码）。

用法：
    python mux_anim_webp.py <序列帧目录> [--fps 30] [--out out.webp] [--loop 0] [--once]
                                            [--recolor FCF9F7=2E2D2D ...]

为什么不用 Pillow 的 save(save_all=True)：
  1. Pillow 走 libwebp WebPAnimEncoder，会**合并完全相同的连续帧**并改写时长
     （实测 9 帧丢成 8 帧、50 帧丢成 41 帧；帧数/时间轴与源序列对不上）。
  2. Pillow 写出的 ANMF flags 为 dispose-none，libwebp 在 no-blend 模式下会
     **跳过 alpha==0 的像素**，导致透明区域残留上一帧 → 帧内容叠加（实测逐字节差异）。
本脚本直接复用源文件里已编码好的 VP8L 码流，不重编码，因此解码像素与原帧逐字节一致。

ANMF flags 位布局（RFC 9649）：bit0 = disposal method，bit1 = blending method。
本脚本用 0x01 = dispose-to-background + no-blend，语义为「每帧先清画布再整帧绘制」，
是唯一能让带透明通道的序列逐帧独立、解码可逐字节还原的取值。

--recolor（可选）：把指定的 RGB 替换成另一个 RGB，**alpha 通道原样保留**。
  典型场景 = 浅色 / 深色配色适配：白色元素在浅色底上看不见，换成深灰（如 FCF9F7=2E2D2D）。
  只有指定了 --recolor 才会解码 → 改色 → 无损重编码；不指定时仍是纯 mux，零重编码。
"""
import argparse
import glob
import io
import os
import struct
import sys

from PIL import Image

ANMF_FLAGS = 0x01


def frame_durations(n, fps):
    """按累计时间取整分配每帧毫秒，总时长精确 = n/fps 秒，长序列不漂移。"""
    out, prev = [], 0
    for i in range(1, n + 1):
        cur = round(i * 1000.0 / fps)
        out.append(cur - prev)
        prev = cur
    return out


def hex2rgb(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise SystemExit("color must be RRGGBB: %s" % s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def image_chunk_from_bytes(b):
    """从 webp 字节流中取出图像 chunk 原始字节（VP8L，或有损时的 ALPH+VP8），含 chunk 头与补齐。"""
    if b[:4] != b"RIFF" or b[8:12] != b"WEBP":
        raise ValueError("not a webp stream")
    off, out = 12, b""
    while off + 8 <= len(b):
        cid = b[off:off + 4]
        sz = struct.unpack("<I", b[off + 4:off + 8])[0]
        tot = 8 + sz + (sz & 1)
        if cid in (b"VP8L", b"ALPH", b"VP8 "):
            out += b[off:off + tot]
        off += tot
    if not out:
        raise ValueError("no image chunk found")
    return out


def image_chunk_bytes(path):
    b = open(path, "rb").read()
    if b[:4] != b"RIFF" or b[8:12] != b"WEBP":
        raise ValueError("not a webp: %s" % path)
    return image_chunk_from_bytes(b)


def recolor(im, mapping):
    """按精确 RGB 匹配替换颜色，alpha 保持不变。返回 (新图, 命中像素数)。"""
    import numpy as np
    arr = np.array(im.convert("RGBA"))
    hit = 0
    for frm, to in mapping.items():
        m = (arr[:, :, 0] == frm[0]) & (arr[:, :, 1] == frm[1]) & (arr[:, :, 2] == frm[2])
        n = int(m.sum())
        if n:
            arr[m, 0], arr[m, 1], arr[m, 2] = to
            hit += n
    return Image.fromarray(arr, "RGBA"), hit


def encode_lossless(im):
    buf = io.BytesIO()
    im.save(buf, "WEBP", lossless=True, method=6, exact=True)
    return buf.getvalue()


def mux(frame_chunks, out_path, durations, w, h, loop=0):
    chunks = b""
    for data, d in zip(frame_chunks, durations):
        hdr = ((0).to_bytes(3, "little") + (0).to_bytes(3, "little")
               + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")
               + d.to_bytes(3, "little") + bytes([ANMF_FLAGS]))
        payload = hdr + data
        chunks += b"ANMF" + struct.pack("<I", len(payload)) + payload \
            + (b"\x00" if len(payload) & 1 else b"")

    vp8x = b"VP8X" + struct.pack("<I", 10) + bytes([0x12]) + b"\x00\x00\x00" \
        + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")
    anim = b"ANIM" + struct.pack("<I", 6) + b"\x00\x00\x00\x00" + struct.pack("<H", loop)
    body = b"WEBP" + vp8x + anim + chunks
    open(out_path, "wb").write(b"RIFF" + struct.pack("<I", len(body)) + body)


def verify(out_path, expected_frames, durs, src_paths=None):
    """结构层（直接解析文件字节）+ 解码层（回读逐字节）双重核验。"""
    ok = True
    blob = open(out_path, "rb").read()
    if blob[:4] != b"RIFF" or blob[8:12] != b"WEBP":
        return False, None

    off, boxes = 12, []
    while off + 8 <= len(blob):
        cid = blob[off:off + 4]
        sz = struct.unpack("<I", blob[off + 4:off + 8])[0]
        boxes.append((cid, off + 8, sz))
        off += 8 + sz + (sz & 1)

    vp8x_flags = loop = None
    anmf = []
    for cid, po, sz in boxes:
        if cid == b"VP8X":
            vp8x_flags = blob[po]
        elif cid == b"ANIM":
            loop = struct.unpack("<H", blob[po + 4:po + 6])[0]
        elif cid == b"ANMF":
            anmf.append((int.from_bytes(blob[po + 12:po + 15], "little"), blob[po + 16:po + sz]))
    durs_got = [a[0] for a in anmf]

    if vp8x_flags != 0x12:
        print("  !! VP8X flags=0x%02x != 0x12" % vp8x_flags); ok = False
    if loop != 0:
        print("  !! loop=%s" % loop); ok = False
    if len(anmf) != len(expected_frames):
        print("  !! ANMF count %d != %d" % (len(anmf), len(expected_frames))); ok = False
    if durs_got != durs:
        print("  !! durations %s != %s" % (durs_got, durs)); ok = False

    # 只有未重编码时才做码流逐字节比对（recolor 必然重编码）
    if src_paths is not None:
        for i, (a, p) in enumerate(zip(anmf, src_paths)):
            if a[1] != image_chunk_bytes(p):
                print("  !! frame %d bitstream differs" % i); ok = False

    im = Image.open(out_path)
    if im.n_frames != len(expected_frames):
        print("  !! decoded frames %d != %d" % (im.n_frames, len(expected_frames))); ok = False
    bad = 0
    for i, exp in enumerate(expected_frames):
        im.seek(i)
        if im.convert("RGBA").tobytes() != exp.convert("RGBA").tobytes():
            print("  !! frame %d decoded pixels differ" % i); bad += 1
    if bad:
        ok = False

    total = sum(durs_got) if durs_got else 0
    stats = dict(frames=len(anmf), w=im.size[0], h=im.size[1], total=total,
                 bytes=os.path.getsize(out_path),
                 fps=(1000.0 * len(anmf) / total) if total else 0,
                 decoded="IDENTICAL" if bad == 0 else "DIFF(%d)" % bad,
                 bitstream=("IDENTICAL" if src_paths is not None else "RECODED"))
    return ok, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seq_dir", help="序列帧目录（*.webp，按文件名排序）")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--out", default=None)
    ap.add_argument("--loop", type=int, default=0, help="0 = 无限循环")
    ap.add_argument("--once", action="store_true", help="只播一次（loop 置为 1）")
    ap.add_argument("--recolor", action="append", default=[],
                    metavar="FROM=TO", help="替换 RGB，如 FCF9F7=2E2D2D（可多次）；alpha 不变")
    args = ap.parse_args()

    src = sorted(glob.glob(os.path.join(args.seq_dir, "*.webp")))
    if not src:
        raise SystemExit("no *.webp in %s" % args.seq_dir)
    out = args.out or (os.path.dirname(os.path.abspath(args.seq_dir))
                       + os.sep + os.path.basename(args.seq_dir.rstrip(os.sep)) + "_anim.webp")
    loop = 1 if args.once else args.loop
    durs = frame_durations(len(src), args.fps)
    w, h = Image.open(src[0]).size

    print("[%s] src=%d frames %dx%d -> %s"
          % (os.path.basename(args.seq_dir), len(src), w, h, os.path.basename(out)))

    src_paths = None
    if args.recolor:
        mapping = {}
        for spec in args.recolor:
            f, t = spec.split("=")
            mapping[hex2rgb(f)] = hex2rgb(t)
        print("  recolor: " + ",  ".join("#%02X%02X%02X -> #%02X%02X%02X" % (k + v)
                                         for k, v in mapping.items()))
        frames, chunks, total_hit, zero_frames = [], [], 0, []
        for i, p in enumerate(src):
            new, hit = recolor(Image.open(p), mapping)
            if hit == 0:
                zero_frames.append(i)
            total_hit += hit
            frames.append(new)
            chunks.append(image_chunk_from_bytes(encode_lossless(new)))
        print("  recolor 命中 %d 像素 / %d 帧" % (total_hit, len(src)))
        if zero_frames:
            print("  !! 这些帧没有命中任何 FROM 颜色: %s（FROM 可能写错）" % zero_frames[:10])
        expected = frames
    else:
        chunks = [image_chunk_bytes(p) for p in src]
        expected = [Image.open(p) for p in src]
        src_paths = src

    mux(chunks, out, durs, w, h, loop)
    ok, st = verify(out, expected, durs, src_paths)
    print("  frames=%d %dx%d total=%dms fps=%.2f bytes=%d bitstream=%s decoded=%s"
          % (st["frames"], st["w"], st["h"], st["total"], st["fps"], st["bytes"],
             st["bitstream"], st["decoded"]))
    print("RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
