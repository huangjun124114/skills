#!/usr/bin/env python3
"""Phase 4a — Repair missing/invalid extensions via magic bytes.

Recursively finds files lacking a recognizable extension and renames them to a
correct extension inferred from file content. Dry-run by default.
"""
import argparse
from pathlib import Path

from _common import magic_ext, print_affected


def find_no_ext(root: Path):
    out = []
    for p in root.rglob("*"):
        if p.is_file() and "." not in p.name:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Repair extensions via magic bytes.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--apply", action="store_true", help="Rename files (default: dry-run)")
    args = ap.parse_args()

    root = Path(args.root)
    files = find_no_ext(root)
    changes = []
    for p in files:
        ext = magic_ext(p.read_bytes())
        if ext and p.suffix.lower() != ext:
            new_name = p.name + ext
            changes.append((str(p), new_name))

    print_affected("扩展名修复（无扩展名文件）", [f"{o} -> {n}" for o, n in changes] or files)

    if not changes:
        print("无需修复的扩展名。")
        return 0
    if not args.apply:
        print("\n[DRY-RUN] 加 --apply 执行重命名。")
        return 0
    for old, new_name in changes:
        op = Path(old)
        op.rename(op.with_name(new_name))
        print(f"重命名: {op.name} -> {new_name}")
    print(f"\n已修复 {len(changes)} 个文件扩展名。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
