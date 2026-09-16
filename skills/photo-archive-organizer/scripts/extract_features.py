#!/usr/bin/env python3
"""Mode B, steps P5-P6: one pass over every image, three outputs.

Reading each image is the expensive part, so all three feature families are
computed in a single pass:

  1. **Visual vector** (3120-d) for event clustering:
     32x32 RGB flattened (3072) + 16-bin colour histogram per channel (48).
     Saved as a .npy matrix; too large for JSON.
  2. **Discriminator features** (12-d) for the semantic-cleanup classifier:
     saturation, white ratio, paper ratio, text-edge density, flat ratio,
     grey entropy, grey std, aspect ratio, screen-AR distance, log10(pixels),
     is-PNG, is-HEIC.
  3. **Quality metrics** for ranking, z-scored over the pool then combined by
     `_common.quality_score`. Valid for RANKING within one pool only —
     absolute values are never comparable across datasets.

Usage:
    python extract_features.py --dated dated.json --out feats.json \
        --visual-out visual.npy --apply
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (SCREEN_AR, chunked_pool, ensure_heif, ensure_pillow,
                     md5_file, quality_score)

THUMB, GRID, HBINS = 512, 32, 16


def _job(rec):
    # multiprocessing on Windows uses spawn: the child does NOT inherit the
    # HEIF opener registered by the parent, so register lazily per worker.
    ensure_heif()
    p = Path(rec["path"])
    try:
        import numpy as np
        from PIL import Image, ImageFilter

        with Image.open(p) as raw:
            raw.load()
            w0, h0 = raw.size
            im = raw.convert("RGB")

            # ---- visual vector: 32x32 RGB + per-channel histogram ----
            small = im.resize((GRID, GRID), Image.LANCZOS)
            vis = np.asarray(small, dtype="float32").reshape(-1) / 255.0
            arr = np.asarray(small, dtype="float32")
            hist = np.concatenate([
                np.histogram(arr[..., c], bins=HBINS, range=(0, 256))[0]
                for c in range(3)]).astype("float32")
            hist /= hist.sum() + 1e-9
            visual = np.concatenate([vis, hist])

            # ---- discriminator features (12-d) on a separate copy ----
            big = im.copy()
        big.thumbnail((THUMB, THUMB), Image.LANCZOS)
        hsv = np.asarray(big.convert("HSV"), dtype="float32")
        sat = float(hsv[..., 1].mean())
        val = hsv[..., 2]
        white = float((val > 235).mean())
        paper = float(((val > 225) & (hsv[..., 1] < 40)).mean())
        g = big.convert("L")
        ga = np.asarray(g, dtype="float32")
        gx = np.abs(np.diff(ga, axis=1))
        gy = np.abs(np.diff(ga, axis=0))
        hi = float(((gx > 40).mean() + (gy > 40).mean()) / 2)
        lap = np.asarray(g.filter(ImageFilter.Kernel(
            (3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=0)),
            dtype="float32")
        flat = float((np.abs(lap) < 4).mean())
        gh = np.histogram(ga, bins=32, range=(0, 256))[0].astype("float32")
        gh /= gh.sum() + 1e-9
        ent = float(-(gh * np.log(gh + 1e-9)).sum())
        grey_std = float(ga.std())
        ar = min(w0, h0) / max(w0, h0)
        screen = min(abs(ar - s) for s in SCREEN_AR)
        px = math.log10(w0 * h0 + 1)
        ext = p.suffix.lower()
        is_png = 1.0 if ext == ".png" else 0.0

        # ---- raw quality metrics ----
        sharp = float(lap.var())
        rgbf = np.asarray(big, dtype="float32")
        rg = rgbf[..., 0] - rgbf[..., 2]
        yb = 0.5 * (rgbf[..., 0] + rgbf[..., 2]) - rgbf[..., 1]
        colour = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2)
                       + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
        dark = float((ga < 20).mean())
        blown = float((ga > 250).mean())

        return {"path": str(p), "rel": rec.get("rel"), "d": rec.get("d"),
                "ym": rec.get("ym"), "src": rec.get("src"), "md5": md5_file(p),
                "w": w0, "h": h0,
                "f": [sat, white, paper, hi, flat, ent, grey_std, ar,
                      float(screen), px, is_png,
                      1.0 if ext in (".heic", ".heif") else 0.0],
                "vis": visual,
                "raw_q": [sharp, px, ent, colour, dark, blown, is_png]}
    except Exception as e:
        return {"path": str(p), "rel": rec.get("rel"), "d": rec.get("d"),
                "ym": rec.get("ym"), "src": rec.get("src"), "md5": None,
                "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dated", required=True, help="date_infer.py output JSON")
    ap.add_argument("--out", required=True, help="metadata + 12-d features JSON")
    ap.add_argument("--visual-out", default="", help="3120-d visual matrix .npy")
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    ensure_pillow()
    ensure_heif()

    recs = json.loads(Path(args.dated).read_text(encoding="utf-8"))
    todo = [r for r in recs if r.get("ym")]
    print(f"待提取 {len(todo)} 张（排除无日期 {len(recs) - len(todo)} 张）")

    out = chunked_pool(_job, todo, chunk=args.chunk, workers=args.workers)
    ok = [r for r in out if r.get("f")]
    bad = [r for r in out if not r.get("f")]
    print(f"成功 {len(ok)}  失败 {len(bad)}")
    for r in bad[:10]:
        print(f"  FAIL {r['path']}: {r.get('error')}")

    import numpy as np
    # ---- z-score quality metrics over this pool, then combine ----
    mat = np.array([r["raw_q"] for r in ok], dtype="float64")
    z = np.zeros_like(mat)
    for c in range(mat.shape[1]):
        s = mat[:, c].std()
        z[:, c] = (mat[:, c] - mat[:, c].mean()) / s if s > 1e-9 else 0.0
    qs = quality_score(z[:, 0], z[:, 1], z[:, 2], z[:, 3], z[:, 4], z[:, 5], z[:, 6])
    order = np.argsort(-qs)
    rank = np.empty(len(qs), dtype="int64")
    for i, idx in enumerate(order):
        rank[idx] = i

    visual = np.stack([r.pop("vis") for r in ok]).astype("float32")
    for i, r in enumerate(ok):
        r["q"] = float(qs[i])
        r["q_rank"] = int(rank[i])
        r.pop("raw_q", None)
    ok.sort(key=lambda r: r["q_rank"])

    print(f"\n视觉特征矩阵 {visual.shape}   12 维判别特征 {len(ok)} 组")
    print("质量分分布：")
    for pct in (5, 25, 50, 75, 95):
        print(f"  p{pct:<3d} {np.percentile(qs, pct):+.3f}")
    print(f"  最优 {ok[0]['rel']}  q={ok[0]['q']:+.3f}")

    if not args.apply:
        print("\n[dry-run] 未写入文件，加 --apply 执行")
        return 0
    Path(args.out).write_text(json.dumps(ok, ensure_ascii=False), encoding="utf-8")
    print(f"\n已写入 {args.out}")
    if args.visual_out:
        np.save(args.visual_out, visual)
        print(f"已写入 {args.visual_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
