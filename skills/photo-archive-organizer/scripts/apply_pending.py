#!/usr/bin/env python3
"""Phase 6b — Apply the user's classification advice to pending files.

Reads a mapping (CSV with columns source_rel,target_folder) produced from the
user's advice, and moves each source file into root/target_folder. Dry-run by default.

Usage:
  apply_pending.py --root DIR --map advice.csv --apply
"""
import argparse
import csv
from pathlib import Path

from _common import print_affected


def main():
    ap = argparse.ArgumentParser(description="Apply user advice to pending files.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--map", required=True, help="CSV with columns: source_rel,target_folder")
    ap.add_argument("--apply", action="store_true", help="Execute moves (default: dry-run)")
    args = ap.parse_args()

    root = Path(args.root)
    moves = []
    with open(args.map, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            src = root / r["source_rel"].strip()
            folder = r["target_folder"].strip()
            if not folder:
                continue
            dst = root / folder / src.name
            moves.append((src, dst))

    print_affected("按用户建议移动", [f"{s}  ->  {d}" for s, d in moves])
    if not args.apply:
        print("\n[DRY-RUN] 加 --apply 执行移动。")
        return 0
    done = 0
    for s, d in moves:
        if not s.exists():
            print(f"WARN 源不存在: {s}")
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            print(f"SKIP 已存在: {d}")
            continue
        s.replace(d)
        done += 1
    print(f"\n已移动 {done} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
