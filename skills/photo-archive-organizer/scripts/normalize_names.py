#!/usr/bin/env python3
"""Phase 4b — Normalize folder names to the YYYYMM-<event> convention.

Handles: YYYYMMDD -> YYYYMM- ; YYYY-MM- -> YYYYMM- ; YYYY+中文 -> YYYY01- ;
YYYYMM+中文(no separator) -> YYYYMM- ; trailing junk cleanup. Does NOT touch
semantic-keep folders (e.g. 全家福). Dry-run by default.
"""
import argparse
import re
from pathlib import Path

KEEP = {"全家福"}


def normalize(name: str) -> str | None:
    if name in KEEP:
        return None
    if re.match(r"^\d{6}-", name):
        return None  # already canonical
    # YYYYMMDD -> YYYYMM-
    m = re.match(r"^(\d{4})(\d{2})\d{2}(?:[-_ ].*)?$", name)
    if m:
        return f"{m.group(1)}{m.group(2)}-" + (name[m.end():].lstrip("-_ ") or "")
    # YYYY-MM- / YYYY_MM- -> YYYYMM-
    m = re.match(r"^(\d{4})[-_](\d{2})[-_ ]?(.*)$", name)
    if m:
        suffix = m.group(3).lstrip("-_ ")
        return f"{m.group(1)}{m.group(2)}-" + suffix
    # YYYY + 中文(无连字符) -> YYYY01-
    m = re.match(r"^(\d{4})(?!\d)(?![-_])(\D.*)$", name)
    if m:
        suffix = m.group(2).lstrip("-_ ")
        return f"{m.group(1)}01-" + suffix
    # YYYYMM + 中文(无连字符) -> YYYYMM-
    m = re.match(r"^(\d{6})(\D.*)$", name)
    if m:
        suffix = m.group(2).lstrip("-_ ")
        return f"{m.group(1)}-" + suffix
    return None


def main():
    ap = argparse.ArgumentParser(description="Normalize folder names to YYYYMM-.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--apply", action="store_true", help="Rename folders (default: dry-run)")
    args = ap.parse_args()

    root = Path(args.root)
    planned = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        new = normalize(d.name)
        if new and new != d.name:
            planned.append((d.name, new))

    print(f"=== 待归一化文件夹 ({len(planned)}) ===")
    for old, new in planned:
        print(f"  {old} -> {new}")

    if not planned:
        print("全部文件夹已符合 YYYYMM- 规范。")
        return 0
    if not args.apply:
        print("\n[DRY-RUN] 加 --apply 执行重命名。")
        return 0
    for old, new in planned:
        (root / old).rename(root / new)
        print(f"重命名: {old} -> {new}")
    print(f"\n已归一化 {len(planned)} 个文件夹。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
