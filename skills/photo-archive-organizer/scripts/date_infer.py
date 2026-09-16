#!/usr/bin/env python3
"""Mode B, step P4: layered date inference without filesystem timestamps.

Priority chain (mode B — flat/unsorted sources):
    1. EXIF DateTimeOriginal
    2. YYYYMMDD in the filename
    3. 13-digit epoch-ms timestamp (WeChat mmexport, Xiaohongshu)
    4. XMP photoshop:DateCreated
    5. folder name `YYYY年MM月`   (promoted to #1 with --folder-first)
    6. iPhone IMG_#### sequence interpolation (gated by a LOO check)

Filesystem mtime/ctime are NEVER used. Anything still undated is reported as
NONE and must be excluded by the caller, never guessed.

Usage:
    python date_infer.py --root DIR --out dated.json
    python date_infer.py --root DIR --out dated.json --folder-first --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (B_PHOTO_EXTS, clamp_ym, ensure_heif, ensure_pillow,
                     exif_date_full, loo_validate, parse_ts13, parse_ymd,
                     seq_of, xmp_date)

CN_YM = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月")


def folder_ym(path: Path, root: Path):
    """`YYYY年MM月` / `YYYYMM` taken from any folder component above the file."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None, None
    for part in rel.parts[:-1]:
        m = CN_YM.search(part)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
            if 1990 <= y <= 2035 and 1 <= mo <= 12:
                return None, f"{y:04d}{mo:02d}"
        m = re.match(r"^((?:19|20)\d{2})(\d{2})$", part.strip())
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
            if 1990 <= y <= 2035 and 1 <= mo <= 12:
                return None, f"{y:04d}{mo:02d}"
    return None, None


def walk(root: Path, exts: set[str]):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="source directory (read-only)")
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--folder-first", action="store_true",
                    help="promote folder-name dates (mode A style structures)")
    ap.add_argument("--min-ym", default="201501")
    ap.add_argument("--max-ym", default="202612")
    ap.add_argument("--seq-win", type=int, default=150)
    ap.add_argument("--seq-min-k", type=int, default=3)
    ap.add_argument("--seq-agree", type=float, default=0.7)
    ap.add_argument("--min-loo", type=float, default=0.95,
                    help="minimum LOO accuracy before interpolation is allowed")
    ap.add_argument("--ext", default="", help="comma-separated extension override")
    ap.add_argument("--apply", action="store_true",
                    help="actually write --out (default is dry-run)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}")
        return 1
    exts = ({e if e.startswith(".") else "." + e
             for e in args.ext.split(",") if e.strip()} if args.ext else B_PHOTO_EXTS)

    ensure_pillow()
    ensure_heif()

    files = list(walk(root, exts))
    print(f"扫描到 {len(files)} 个媒体文件")

    chain = (["folder"] if args.folder_first else [])
    chain += ["exif", "name_ymd", "ts13", "xmp"]
    if not args.folder_first:
        chain.append("folder")

    recs = []
    for p in files:
        full = ym = None
        src = "NONE"
        for step in chain:
            if step == "folder":
                full, ym = folder_ym(p, root)
            elif step == "exif":
                full, ym = exif_date_full(p)
            elif step == "name_ymd":
                full, ym = parse_ymd(p.name)
            elif step == "ts13":
                full, ym = parse_ts13(p.name)
            elif step == "xmp":
                full, ym = xmp_date(p)
            if ym:
                src = step
                break
        in_range = True
        if ym:
            ym, in_range = clamp_ym(int(ym[:4]), int(ym[4:6]), args.min_ym, args.max_ym)
            if not in_range:
                src = "OUT_OF_RANGE"
                full = ym = None
        recs.append({"path": str(p), "rel": str(p.relative_to(root)),
                     "name": p.name, "d": full, "ym": ym,
                     "src": src, "seq": seq_of(p.name)})

    # ---- sequence interpolation, gated by a leave-one-out check ----
    seq_items = [(r["seq"], r["d"]) for r in recs]
    acc, conf = loo_validate(seq_items, args.seq_win, args.seq_min_k, args.seq_agree)
    print(f"序号插值留一验证：准确率 {acc:.3f}（门槛 {args.min_loo}）"
          f"  平均置信度 {conf:.2f}")
    interp_n = 0
    if acc >= args.min_loo:
        dated = [(s, d) for s, d in seq_items if s is not None and d]
        for r in recs:
            if r["d"] or r["seq"] is None:
                continue
            near = [d2 for s2, d2 in dated if abs(s2 - r["seq"]) <= args.seq_win]
            if len(near) < args.seq_min_k:
                continue
            best, n = Counter(near).most_common(1)[0]
            if n / len(near) >= args.seq_agree:
                r["d"], r["ym"], r["src"] = best, best[:6], "interp"
                interp_n += 1
        print(f"插值补出 {interp_n} 张")
    else:
        print("LOO 未达门槛，本批次不启用插值")

    dist = Counter(r["src"] for r in recs)
    total = len(recs)
    dated_n = sum(1 for r in recs if r["ym"])
    print(f"\n日期来源分布（共 {total} 张，有日期 {dated_n} 张，覆盖 {dated_n/total:.1%}）")
    for k, v in dist.most_common():
        print(f"  {k:14s} {v:5d}")
    none_n = dist.get("NONE", 0) + dist.get("OUT_OF_RANGE", 0)
    print(f"\n无法推断 {none_n} 张 —— 按规则排除，禁止用 mtime/年龄猜测")

    if not args.apply:
        print("\n[dry-run] 未写入文件，加 --apply 执行")
        return 0
    Path(args.out).write_text(json.dumps(recs, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
