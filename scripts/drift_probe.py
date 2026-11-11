#!/usr/bin/env python3
"""repo-kit v2.3 正对照 + 负对照（kit 自测，不是仓库验收）。

- 负对照：合法的基线仓库必须 ERROR=0、WARN=0。
- 正对照：逐条注入 8 类已知漂移，确认校验器真的会红，再恢复并复跑基线。
- 生成对照：generate.py --check 在基线上必须通过。

依赖 kit 自带的 `examples/` 夹具；消费仓库没有这些文件时会 SKIP（退出 0）。
仓库验收请跑 check_repo.py 与 generate.py --check。

用法：
    python scripts/drift_probe.py --root .
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

CASES = [
    ("重命名文件但不更新引用", "examples/code/docs/retry.md", "rename", "LINK_BROKEN"),
    ("改标题但不更新锚点", "examples/code/docs/config.md", "anchor", "ANCHOR_BROKEN"),
    ("使用词表之外的新标签", "examples/knowledge/note-a.md", "vocab", "VOCAB"),
    ("同一概念在两处定义", "examples/knowledge/note-b.md", "ssot", "DEFINES_DUP"),
    ("真源改键但文档没跟着改", "examples/code/config.py", "truth", "TRUTH_DRIFT"),
    ("嵌套 frontmatter", "docs/index.md", "nested", "FM_STRUCTURE"),
    ("source_commit 乱填", "examples/code/docs/config.md", "commit", "SCHEMA"),
    ("superseded 缺 superseded_by", "examples/knowledge/note-b.md", "superseded", "SUPERSEDED_MISSING"),
]


def copy_repo(src: Path, dst: Path) -> None:
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "*.pyc"),
    )


def run_check(root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HERE / "check_repo.py"), "--root", str(root), "--json"],
        capture_output=True, text=True,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"errors": -1, "warnings": -1, "items": [], "raw": proc.stdout + proc.stderr}


def mutate(root: Path, rel: str, kind: str):
    p = root / rel
    original = p.read_text(encoding="utf-8")
    moved = None
    if kind == "rename":
        moved = p.with_name("retry-legacy.md")
        p.rename(moved)
    elif kind == "anchor":
        p.write_text(original.replace("# 运行时配置", "# 配置说明"), encoding="utf-8")
    elif kind == "vocab":
        p.write_text(original.replace("topics: [pricing]", "topics: [pricing, growth]"), encoding="utf-8")
    elif kind == "ssot":
        p.write_text(
            original.replace('owner: "@research"', 'owner: "@research"\ndefines: value-before-price'),
            encoding="utf-8",
        )
    elif kind == "truth":
        p.write_text(original.replace('"cache_ttl": 600', '"cache_lifetime": 600'), encoding="utf-8")
    elif kind == "nested":
        p.write_text(
            original.replace("related: []\n---", "related: []\nmeta:\n  nested: true\n---", 1),
            encoding="utf-8",
        )
    elif kind == "commit":
        p.write_text(original.replace("source_commit: 7eaf524c", "source_commit: not-a-hash"), encoding="utf-8")
    elif kind == "superseded":
        p.write_text(original.replace("status: active", "status: superseded"), encoding="utf-8")
    return p, original, moved


def restore(p: Path, original: str, moved: Path | None) -> None:
    if moved is not None and moved.exists():
        moved.rename(p)
    elif p.exists():
        p.write_text(original, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="repo-kit 正负对照（kit 自测）")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    source = Path(args.root).resolve()
    missing = sorted({rel for _, rel, _, _ in CASES if not (source / rel).exists()})
    if missing:
        print("SKIP: drift_probe 是 repo-kit 校验器的自测，需要 kit 自带的 examples/ 夹具。")
        print("      当前仓库缺少：" + ", ".join(missing))
        print("      仓库验收请跑 check_repo.py 与 generate.py --check。")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix="repo-kit-v2-probe-"))
    root = tmp / "kit"
    copy_repo(source, root)

    baseline = run_check(root)
    if baseline.get("errors") != 0:
        print(f"负对照失败：基线不干净，ERROR={baseline.get('errors')}")
        for item in baseline.get("items", [])[:10]:
            print(" ", item["severity"], item["code"], item["file"], item["message"])
        return 1
    print(f"负对照：基线 PASS（WARN={baseline.get('warnings', 0)}）\n")

    gen = subprocess.run(
        [sys.executable, str(HERE / "generate.py"), "--root", str(root), "--check"],
        capture_output=True, text=True,
    )
    gen_ok = gen.returncode == 0
    print(f"生成对照：{'PASS' if gen_ok else 'FAIL'}")
    if not gen_ok:
        print(gen.stdout.strip(), gen.stderr.strip())

    results = []
    for name, rel, kind, expect in CASES:
        p, original, moved = mutate(root, rel, kind)
        try:
            data = run_check(root)
            codes = {i["code"] for i in data.get("items", []) if i["severity"] == "ERROR"}
            caught = data.get("errors", 0) > 0 and expect in codes
            results.append((name, expect, caught, sorted(codes)))
        finally:
            restore(p, original, moved)

    final = run_check(root)
    print("\n%-28s %-22s %-6s %s" % ("注入的漂移", "期望捕获", "结果", "实际触发"))
    print("-" * 96)
    for name, expect, caught, codes in results:
        print("%-28s %-22s %-6s %s" % (name, expect, "拦截" if caught else "漏过", ",".join(codes) or "无"))
    print("-" * 96)

    ok = all(r[2] for r in results) and final.get("errors") == 0 and gen_ok
    print(
        "DRIFT PROBE: %s  (%d/%d 被拦截，恢复后 ERROR=%d)"
        % ("PASS" if ok else "FAIL", sum(1 for r in results if r[2]), len(results), final.get("errors", -1))
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
