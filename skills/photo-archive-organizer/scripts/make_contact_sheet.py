#!/usr/bin/env python3
"""Human-in-the-loop review sheet for semantic cleanup.

Generates a **self-contained HTML** contact sheet (thumbnails embedded as
base64), so the reviewer can click any tile to open the full image and decide
keep/drop without needing the source tree. Tiles at or above `--mark` are
outlined in red.

Two input modes:
    --scored   train_classifier.py output JSON  (tiles carry a score label)
    --dir      any directory                    (no scores, plain browsing)

Usage:
    python make_contact_sheet.py --scored scores.json --out review.html
    python make_contact_sheet.py --scored scores.json --out review.html \
        --top 300 --thumb 320 --mark 0.7
    python make_contact_sheet.py --dir ARCHIVE --out review.html --link-only
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import B_PHOTO_EXTS, SCREEN_AR, chunked_pool, ensure_heif, ensure_pillow

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:16px;background:#f5f5f5;
     font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB",sans-serif}
h1{font-size:17px;margin:0 0 4px}
.meta{font-size:12px;color:#666;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(__CW__px,1fr));gap:10px}
.tile{background:#fff;border:1px solid #ddd;border-radius:4px;padding:6px;
      cursor:pointer;transition:box-shadow .12s}
.tile:hover{box-shadow:0 2px 10px rgba(0,0,0,.18)}
.tile.mark{border:2px solid #d32f2f}
.tile img{width:100%;height:__TH__px;object-fit:contain;display:block;background:#111}
.cap{font-size:11px;margin-top:5px;line-height:1.35;word-break:break-all;color:#333}
.cap b{color:#d32f2f}
.ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9;
    padding:20px;overflow:auto}
.ov.on{display:block}
.ov img{max-width:100%;max-height:82vh;margin:0 auto;display:block}
.ov .cap2{color:#fff;font-size:13px;text-align:center;margin-top:10px;
          word-break:break-all}
"""

JS = """
document.addEventListener('click',function(e){
  var t=e.target.closest('.tile'); if(!t) return;
  var ov=document.getElementById('ov'), im=document.getElementById('ovi'),
      cp=document.getElementById('ovc');
  im.src=t.dataset.full; cp.textContent=t.dataset.cap; ov.classList.add('on');
});
document.getElementById('ov').addEventListener('click',function(){
  this.classList.remove('on');
});
"""


def _file_uri(path: Path) -> str:
    """file:// URI so the browser can open the full image from disk."""
    from urllib.parse import quote
    return "file:///" + quote(str(path.resolve()).replace("\\", "/"))


def thumb_b64(path: Path, size: int, embed_full: bool):
    """Return (small_b64, large_src).

    Thumbnails are always embedded (small, tens of KB). The full image is
    referenced by a file:// URI unless `--embed-full` is given — embedding
    1600px images costs ~700 KB each, so a 300-photo sheet would reach 200 MB
    and no browser would open it.
    """
    try:
        from PIL import Image
        with Image.open(path) as raw:
            raw.load()
            im = raw.convert("RGB")
            small = im.copy()
            small.thumbnail((size, size), Image.LANCZOS)
            if embed_full:
                big = im.copy()
                big.thumbnail((1600, 1600), Image.LANCZOS)
                buf = io.BytesIO()
                big.save(buf, "JPEG", quality=80)
                large = "data:image/jpeg;base64," + base64.b64encode(
                    buf.getvalue()).decode()
            else:
                large = _file_uri(path)
        buf = io.BytesIO()
        small.save(buf, "JPEG", quality=80)
        enc = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        return enc, large
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _job(a):
    p_str, size, embed_full = a
    ensure_heif()
    s, b = thumb_b64(Path(p_str), size, embed_full)
    return p_str, s, b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", default="", help="train_classifier.py output JSON")
    ap.add_argument("--dir", default="", help="or: a directory to browse")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=0, help="0 = all")
    ap.add_argument("--thumb", type=int, default=320)
    ap.add_argument("--mark", type=float, default=0.7, help="score to highlight")
    ap.add_argument("--embed-full", action="store_true",
                    help="also embed the 1600px images (much larger file; "
                         "default embeds thumbnails only and links the rest)")
    ap.add_argument("--only-marked", action="store_true",
                    help="only include tiles at or above --mark")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    ensure_pillow()
    ensure_heif()

    items = []  # (path, score|None)
    if args.scored:
        data = json.loads(Path(args.scored).read_text(encoding="utf-8"))
        scores = data.get("scores", data)
        thr = data.get("threshold")
        if thr is not None and args.mark is None:
            args.mark = thr
        for p, s in scores.items():
            if args.only_marked and s < args.mark:
                continue
            items.append((p, s))
        items.sort(key=lambda x: -x[1])
    elif args.dir:
        d = Path(args.dir)
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix.lower() in B_PHOTO_EXTS:
                items.append((str(p), None))
    else:
        print("ERROR: 需指定 --scored 或 --dir")
        return 1

    if args.top:
        items = items[:args.top]
    print(f"待生成 {len(items)} 张缩略图"
          f"（{'全内嵌' if args.embed_full else '缩略图内嵌 + 大图引用路径'}）")

    jobs = [(p, args.thumb, args.embed_full) for p, _ in items]
    res = {}
    for p, s, b in chunked_pool(_job, jobs, 20, 8):
        res[p] = (s, b)
    ok = [p for p, _ in items if res.get(p, (None, None))[0]]
    print(f"成功 {len(ok)}  失败 {len(items) - len(ok)}")

    tiles = []
    for p, sc in items:
        small, big = res.get(p, (None, None))
        if not small:
            continue
        folder = Path(p).parent.name
        label = f"{folder} {sc:.2f}" if sc is not None else folder
        cls = "tile mark" if (sc is not None and sc >= args.mark) else "tile"
        cap = (f'{html.escape(folder)} <b>{sc:.2f}</b>'
               if sc is not None else html.escape(folder))
        tiles.append(
            f'<div class="{cls}" data-full="{html.escape(big)}" '
            f'data-cap="{html.escape(Path(p).name + "  |  " + label)}">'
            f'<img loading="lazy" src="{html.escape(small)}" alt="">'
            f'<div class="cap">{cap}</div></div>')

    # Build by plain concatenation + placeholder replacement: the CSS/JS blocks
    # are full of { } and % characters, which break f-strings and %-formatting.
    css = CSS.replace("__CW__", str(args.thumb + 12)).replace("__TH__",
                                                             str(args.thumb))
    head = ('<!doctype html>\n<meta charset="utf-8">\n'
            '<title>复核表 ' + str(len(tiles)) + ' 张</title>\n'
            '<style>' + css + '</style>\n'
            '<h1>照片复核表</h1>\n'
            '<div class="meta">共 ' + str(len(tiles)) + ' 张 · '
            '红框 = 判别分数 ≥ ' + str(args.mark) + '（疑似需剔除） · '
            '点击缩略图看大图 · 再点背景关闭</div>\n')
    body = ('<div class="grid">\n' + "\n".join(tiles) + '\n</div>\n'
            '<div class="ov" id="ov">\n'
            '  <img id="ovi" src="" alt="">\n'
            '  <div class="cap2" id="ovc"></div>\n'
            '</div>\n'
            '<script>' + JS + '</script>\n')
    doc = head + body
    if not args.apply:
        print("\n[dry-run] 未写入文件，加 --apply 执行")
        return 0
    Path(args.out).write_text(doc, encoding="utf-8")
    size_mb = Path(args.out).stat().st_size / 1024 / 1024
    print(f"\n已写入 {args.out}（{size_mb:.1f} MB）")
    print("用浏览器打开，逐张点开确认后在对话中给出分档决策。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
