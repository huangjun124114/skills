#!/usr/bin/env python3
"""Phase 7 — Verify: md5 content-conservation + structure checks.

Structure checks: top level contains only allowed dirs; every folder matches
YYYYMM- (except semantic-keep names); zero no-extension files.
Content check (optional --backup): every unique content hash present in the
backup is also present in the organized root (0 missing) — proves no file lost.

Usage:
  verify.py --root DIR --allow 我的照片,美女,合家欢 [--backup BACKUP_DIR]
"""
import argparse
import re
from pathlib import Path

from _common import md5_file, iter_files, KEEP

ALLOW_DEFAULT = ["我的照片", "美女", "合家欢"]


def structure_check(root: Path, allow):
    top_dirs = [p for p in root.iterdir() if p.is_dir()]
    bad = [d.name for d in top_dirs
           if not re.match(r"^\d{6}-", d.name) and d.name not in allow and d.name not in KEEP]
    no_ext = [str(f.relative_to(root)) for f in iter_files(root) if "." not in f.name]
    loose = [f.name for f in root.iterdir() if f.is_file()]
    return top_dirs, bad, no_ext, loose


def content_check(root: Path, backup: Path):
    print("计算备份内容哈希 ...")
    backup_hashes = {md5_file(f) for f in iter_files(backup)}
    print(f"  备份唯一内容: {len(backup_hashes)}")
    print("计算整理后内容哈希 ...")
    root_hashes = {md5_file(f) for f in iter_files(root)}
    print(f"  整理后唯一内容: {len(root_hashes)}")
    missing = backup_hashes - root_hashes
    return missing


def main():
    ap = argparse.ArgumentParser(description="Verify archive integrity.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--backup", help="Backup directory for content-conservation check")
    ap.add_argument("--allow", default=",".join(ALLOW_DEFAULT),
                    help="Comma-separated allowed non-YYYYMM top dirs")
    args = ap.parse_args()

    allow = [a.strip() for a in args.allow.split(",") if a.strip()]
    root = Path(args.root)

    top_dirs, bad, no_ext, loose = structure_check(root, allow)
    print(f"顶层目录数: {len(top_dirs)}")
    print(f"非 YYYYMM- 且未允许的目录: {bad if bad else '无'}")
    print(f"无扩展名文件数: {len(no_ext)}")
    print(f"根目录松散文件数: {len(loose)}")

    ok = not bad and not no_ext and not loose

    if args.backup:
        missing = content_check(root, Path(args.backup))
        print(f"\n内容守恒：缺失 {len(missing)} 个")
        if missing:
            ok = False

    print("\n=== 核验结果 ===")
    print("✅ 通过" if ok else "❌ 存在问题，请修复后再删除备份")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
