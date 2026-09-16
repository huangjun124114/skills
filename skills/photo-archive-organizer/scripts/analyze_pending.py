#!/usr/bin/env python3
"""Phase 6a — Analyze pending (unclassifiable) files and extract naming clues.

Walks a 待溯源-* directory, extracts naming clues (subfolder as event candidate,
filename date fragments, media-creation dates from EXIF/mvhd), and writes a
pending-analysis table (CSV + Markdown). It does NOT move anything. Items lacking
any objective signal are flagged needs_user=yes for the user to advise.

Usage:
  analyze_pending.py --root DIR --pending DIR/待溯源-帅哥 --report OUT_PREFIX
"""
import argparse
import csv
import re
from pathlib import Path

from _common import exif_date, video_date, parse_filename_date, VIDEO_EXTS, PHOTO_EXTS


def source_suffix_from_name(pending_name: str) -> str:
    m = re.match(r"待溯源[-_](.+)", pending_name)
    return m.group(1) if m else pending_name


def analyze(pending: Path, suffix: str):
    rows = []
    for f in pending.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(pending)
        sub = rel.parts[0] if len(rel.parts) > 1 else ""
        m = re.match(r"^(\d{6}|\d{4}[-_]\d{2}|\d{8})[-_ ]?", sub)
        event_candidate = sub[m.end():].strip("-_ ").strip() if m else sub.strip()
        media = exif_date(f) if f.suffix.lower() in PHOTO_EXTS else video_date(f)
        fname_date = parse_filename_date(f.name)
        ym = media or fname_date
        if ym and event_candidate:
            suggested = f"{ym}-{event_candidate}-{suffix}"
            conf, needs = ("high" if media else "medium"), "no"
        elif ym and not event_candidate:
            kind = "视频" if f.suffix.lower() in VIDEO_EXTS else "照片"
            suggested = f"{ym}-{kind}-{suffix}"
            conf, needs = "medium", "no"
        else:
            suggested, conf, needs = "", "low", "yes"
        rows.append({
            "item": str(rel),
            "subfolder": sub,
            "event_candidate": event_candidate,
            "filename_date": fname_date or "",
            "media_date": media or "",
            "suggested_folder": suggested,
            "confidence": conf,
            "needs_user": needs,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Analyze pending files & extract clues.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--pending", required=True, help="Path to a 待溯源-* directory")
    ap.add_argument("--report", required=True, help="Output prefix, writes .csv and .md")
    args = ap.parse_args()

    pending = Path(args.pending)
    suffix = source_suffix_from_name(pending.name)
    rows = analyze(pending, suffix)

    csv_path = args.report + ".csv"
    md_path = args.report + ".md"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 待溯源分析表：{pending.name}\n\n")
        f.write(f"共 {len(rows)} 项；需用户确认：{sum(1 for r in rows if r['needs_user']=='yes')}\n\n")
        f.write("| item | subfolder | event_candidate | filename_date | media_date | suggested_folder | confidence | needs_user |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write("| " + " | ".join(str(r[k]) for k in
                     ["item", "subfolder", "event_candidate", "filename_date",
                      "media_date", "suggested_folder", "confidence", "needs_user"]) + " |\n")

    print(f"分析完成：{len(rows)} 项")
    print(f"  CSV: {csv_path}")
    print(f"  MD : {md_path}")
    need = [r for r in rows if r["needs_user"] == "yes"]
    if need:
        print(f"\n需用户分类建议 ({len(need)} 项)：")
        for r in need:
            print(f"  - {r['item']}  (线索: 子目录='{r['subfolder']}', 文件名='{r['item']}')")
        print("\n请向用户询问这些文件的事件名/年月/来源，得到建议后调用 apply_pending.py。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
