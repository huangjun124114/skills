#!/usr/bin/env python3
"""Phase 5 — Group root-level loose files by time + content relevance.

Files loose at the archive root are classified: files whose name carries clear
event semantics (Chinese event words, not a bare IMG_/sd serial) get a dedicated
`YYYYMM-事件-来源` folder; otherwise they roll up into `YYYYMM-视频/照片-来源`.
Dry-run by default.
"""
import argparse
import re
from pathlib import Path

from _common import infer_date, VIDEO_EXTS, PHOTO_EXTS, print_affected

EVENT_WORDS = ("元宵", "灯会", "足球", "父子", "奶奶", "大寿", "弋阳", "将进酒", "表演",
               "毕业", "弹钢琴", "教爸爸", "跳舞", "追鸽子", "游乐园", "插秧", "桂林",
               "ktv", "滑草", "魔方", "鹿嘴", "平板撑", "穿袜子")


def has_event_semantics(stem: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", stem):
        return True
    low = stem.lower()
    return any(w in low for w in EVENT_WORDS)


def main():
    ap = argparse.ArgumentParser(description="Group root-loose files.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--target", required=True, help="e.g. 合家欢")
    ap.add_argument("--suffix", default="", help="source suffix to append, e.g. 帅哥")
    ap.add_argument("--apply", action="store_true", help="Execute moves (default: dry-run)")
    args = ap.parse_args()

    root = Path(args.root)
    target = root / args.target
    suffix = f"-{args.suffix}" if args.suffix else ""

    moves = []
    for f in root.iterdir():
        if not f.is_file():
            continue
        ym, _ = infer_date(f.name, "", None, f)
        if not ym:
            ym = "000000"  # placeholder; will surface in pending review
        stem = Path(f.name).stem
        if has_event_semantics(stem):
            folder = f"{ym}-{stem}{suffix}"
        else:
            kind = "视频" if f.suffix.lower() in VIDEO_EXTS else "照片"
            folder = f"{ym}-{kind}{suffix}"
        moves.append((f, target / folder / f.name))

    print_affected("松散文件归位计划", [f"{s}  ->  {d}" for s, d in moves])
    if not args.apply:
        print("\n[DRY-RUN] 加 --apply 执行归位。")
        return 0
    for s, d in moves:
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            print(f"SKIP 已存在: {d}")
            continue
        s.replace(d)
        print(f"移动: {s.name} -> {d}")
    print(f"\n已归位 {len(moves)} 个松散文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
