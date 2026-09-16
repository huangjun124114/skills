#!/usr/bin/env python3
"""Phase 1 — Read-only scan & plan for the photo archive organizer.

Recursively scans a directory and prints an overview (per-top-level-dir counts,
extension distribution, time span) plus a proposed plan. Never modifies files.
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from _common import VIDEO_EXTS, PHOTO_EXTS, iter_files


def scan(root: Path):
    top_dirs = defaultdict(lambda: {"files": 0, "exts": Counter(), "loose": 0})
    loose_at_root = []
    no_ext = []
    total = 0
    for p in root.iterdir():
        if p.is_dir():
            files = list(iter_files(p))
            exts = Counter(f.suffix.lower() or "(none)" for f in files)
            top_dirs[p.name]["files"] = len(files)
            top_dirs[p.name]["exts"] = exts
        else:
            loose_at_root.append(p.name)
            total += 1
            no_ext.append(p.name) if "." not in p.name else None
    # whole-tree stats
    all_files = list(iter_files(root))
    total = len(all_files)
    tree_exts = Counter(f.suffix.lower() or "(none)" for f in all_files)
    return top_dirs, loose_at_root, no_ext, total, tree_exts


def main():
    ap = argparse.ArgumentParser(description="Read-only scan & plan for photo archive.")
    ap.add_argument("--root", required=True, help="Directory to scan")
    ap.add_argument("--report", help="Optional path to write a Markdown plan")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: {root} does not exist")
        return 1

    top_dirs, loose, no_ext, total, tree_exts = scan(root)

    print(f"# 扫描报告：{root}\n")
    print(f"总文件数: {total}")
    print(f"根目录松散文件: {len(loose)}")
    print(f"无扩展名文件(全树): {len(no_ext)}\n")

    print("## 顶层目录")
    for name in sorted(top_dirs):
        d = top_dirs[name]
        ext_sample = ", ".join(f"{k}:{v}" for k, v in d["exts"].most_common(6))
        print(f"- {name}: {d['files']} 文件 | {ext_sample}")

    print("\n## 全树扩展名分布")
    for ext, cnt in tree_exts.most_common():
        print(f"- {ext}: {cnt}")

    print("\n## 初步计划（只读，未修改任何文件）")
    print("1. 确认合并映射（哪些子目录并入合家欢及来源后缀）。")
    print("2. 备份整目录后再执行迁移。")
    print("3. 对顶层松散文件与无扩展名文件执行修复与归位。")
    print("4. 无法判定日期的文件暂存待溯源，后续询问用户分类建议。")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(f"# 扫描报告：{root}\n\n总文件数: {total}\n")
            f.write(f"根目录松散文件: {len(loose)}\n无扩展名文件: {len(no_ext)}\n")
            for name in sorted(top_dirs):
                d = top_dirs[name]
                f.write(f"- {name}: {d['files']} 文件\n")
        print(f"\n报告已写入: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
