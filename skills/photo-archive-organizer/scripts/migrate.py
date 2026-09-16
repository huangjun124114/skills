#!/usr/bin/env python3
"""Phase 3 — Merge per-person folders into the shared archive with date inference.

For each source folder in --merge-map, walks its files, infers YYYYMM via the
priority chain (folder/filename date > EXIF > mvhd > explicit age cue), and plans
moves into `target/YYYYMM-事件-来源`. Files with no inferable date go to
`target/待溯源-<source>` for the human-in-the-loop Phase 6. Dry-run by default.
"""
import argparse
import json
import re
from pathlib import Path

from _common import infer_date, VIDEO_EXTS, PHOTO_EXTS, print_affected


def derive_event(folder_name: str) -> str:
    if not folder_name:
        return ""
    # strip a leading YYYYMM / YYYY-MM / YYYYMMDD date prefix if present
    m = re.match(r"^(\d{6}|\d{4}[-_]\d{2}|\d{8})[-_ ]?", folder_name)
    if m:
        return folder_name[m.end():].strip("-_ ").strip()
    return folder_name.strip("-_ ").strip()


def main():
    ap = argparse.ArgumentParser(description="Merge & auto date-infer.")
    ap.add_argument("--root", required=True, help="Archive root (contains source folders)")
    ap.add_argument("--merge-map", required=True, help='JSON: {"帅哥":{"target":"合家欢","suffix":"帅哥"}}')
    ap.add_argument("--birth-years", default="{}", help='JSON: {"帅哥":2012,"闺女":2019}')
    ap.add_argument("--apply", action="store_true", help="Execute moves (default: dry-run)")
    args = ap.parse_args()

    root = Path(args.root)
    merge_map = json.loads(args.merge_map)
    birth_years = json.loads(args.birth_years)

    moves = []  # (src_path, dst_path)
    for src_name, cfg in merge_map.items():
        src_dir = root / src_name
        target = root / cfg["target"]
        suffix = cfg["suffix"]
        birth = birth_years.get(src_name)
        if not src_dir.exists():
            print(f"WARN: source {src_dir} not found, skip")
            continue
        for f in src_dir.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src_dir)
            folder_name = rel.parts[0] if len(rel.parts) > 1 else ""
            ym, _src = infer_date(f.name, folder_name, birth, f)
            if ym:
                event = derive_event(folder_name)
                if event:
                    folder = f"{ym}-{event}-{suffix}"
                else:
                    kind = "视频" if f.suffix.lower() in VIDEO_EXTS else "照片"
                    folder = f"{ym}-{kind}-{suffix}"
                dst = target / folder / f.name
            else:
                dst = target / f"待溯源-{suffix}" / rel
            moves.append((f, dst))

    print_affected("迁移计划", [f"{s}  ->  {d}" for s, d in moves])
    pending = [s for s, d in moves if "待溯源-" in str(d)]
    print(f"\n自动归类: {len(moves) - len(pending)} | 待溯源(需用户): {len(pending)}")

    if not args.apply:
        print("\n[DRY-RUN] 加 --apply 执行迁移。")
        return 0
    for s, d in moves:
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            print(f"SKIP 已存在: {d}")
            continue
        s.replace(d)
        print(f"移动: {s.name} -> {d}")
    print(f"\n已迁移 {len(moves)} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
