#!/usr/bin/env python3
"""Mode B, semantic cleanup: self-labelled classifier for content decisions.

Labels come for free from the previous round — survivors in the archive are
positives, files already moved to quarantine are negatives.

The threshold is NEVER auto-selected. `--threshold` is required: picking by
"max recall" produced a 62% false-kill rate on real photos once (731 candidates
cut to 145). Print the table, then decide deliberately.

Usage:
    python train_classifier.py --positive ARCHIVE --negative QUARANTINE \
        --score feats.json --out scores.json --threshold 0.55 --apply

    --positive/--negative  directories (or .json lists) used as training labels
    --score                extract_features.py JSON to be scored
    --threshold            REQUIRED decision threshold on the "reject" score
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (B_PHOTO_EXTS, SCREEN_AR, chunked_pool, ensure_heif,
                     ensure_pillow)

THUMB = 512


def _feat_job(p_str):
    # multiprocessing on Windows uses spawn: the child does NOT inherit the
    # HEIF opener registered by the parent, so register lazily per worker.
    ensure_heif()
    p = Path(p_str)
    try:
        import math
        import numpy as np
        from PIL import Image, ImageFilter
        with Image.open(p) as raw:
            raw.load()
            w0, h0 = raw.size
            im = raw.convert("RGB")
        im.thumbnail((THUMB, THUMB), Image.LANCZOS)
        hsv = np.asarray(im.convert("HSV"), dtype="float32")
        sat = float(hsv[..., 1].mean())
        val = hsv[..., 2]
        white = float((val > 235).mean())
        paper = float(((val > 225) & (hsv[..., 1] < 40)).mean())
        g = im.convert("L")
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
        ar = min(w0, h0) / max(w0, h0)
        ext = p.suffix.lower()
        return p_str, [sat, white, paper, hi, flat, ent, float(ga.std()), ar,
                       float(min(abs(ar - s) for s in SCREEN_AR)),
                       math.log10(w0 * h0 + 1),
                       1.0 if ext == ".png" else 0.0,
                       1.0 if ext in (".heic", ".heif") else 0.0]
    except Exception:
        return p_str, None


def collect(src_spec):
    """Accept a directory (walked) or a .json list of paths."""
    out = []
    if src_spec.lower().endswith(".json"):
        data = json.loads(Path(src_spec).read_text(encoding="utf-8"))
        for item in data:
            out.append(item["path"] if isinstance(item, dict) else item)
        return out
    for p in sorted(Path(src_spec).rglob("*")):
        if p.is_file() and p.suffix.lower() in B_PHOTO_EXTS:
            out.append(str(p))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positive", required=True, help="keep-set dir/json")
    ap.add_argument("--negative", required=True, help="reject-set dir/json")
    ap.add_argument("--score", required=True, help="extract_features.py JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold", type=float, required=True,
                    help="REQUIRED — never auto-selected, see module docstring")
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true",
                    help="override the AUC < 0.65 refusal (not recommended)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not (0.0 < args.threshold < 1.0):
        print("ERROR: --threshold 必须在 0~1 之间")
        return 1

    ensure_pillow()
    ensure_heif()

    for label, path in (("--positive", args.positive),
                        ("--negative", args.negative),
                        ("--score", args.score)):
        if not Path(path).exists():
            print(f"ERROR: {label} 指向的路径不存在: {path}")
            return 1

    pos = collect(args.positive)
    neg = collect(args.negative)
    pool = json.loads(Path(args.score).read_text(encoding="utf-8"))
    print(f"正样本 {len(pos)}   负样本 {len(neg)}   待打分 {len(pool)}")

    # reuse 12-d features already in the pool; compute the rest
    have = {r["path"]: r["f"] for r in pool if r.get("f")}
    need = [p for p in pos + neg if p not in have]
    print(f"复用已有特征 {len(have)} 组，需新算 {len(need)} 组")
    for p_str, f in chunked_pool(_feat_job, need, args.chunk, args.workers):
        if f:
            have[p_str] = f

    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (precision_recall_fscore_support,
                                 roc_auc_score)
    from sklearn.model_selection import (StratifiedKFold, cross_val_predict)
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    Xp = [have[p] for p in pos if p in have]
    Xn = [have[p] for p in neg if p in have]
    if len(Xp) < 20 or len(Xn) < 20:
        print(f"ERROR: 样本不足（正 {len(Xp)} / 负 {len(Xn)}），至少需要各 20")
        return 1
    X = np.array(Xp + Xn, dtype="float32")
    y = np.array([1] * len(Xp) + [0] * len(Xn), dtype="int32")

    pipe = make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=2000, C=1.0,
                                            class_weight="balanced"))
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    pcv = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]
    auc = roc_auc_score(y, pcv)
    rscore = 1.0 - pcv  # "reject" score

    print(f"\n交叉验证 AUC = {auc:.4f}")
    print(f"{'阈值':>6s} {'精确率':>8s} {'召回':>8s} {'正样本误杀':>10s}")
    for thr in (0.30, 0.40, 0.50, 0.55, 0.60, 0.70, 0.80):
        pred = (rscore >= thr).astype(int)
        prec, rec, _, _ = precision_recall_fscore_support(
            (y == 0).astype(int), pred, average="binary", zero_division=0)
        fpr = float(pred[y == 1].mean())
        mark = "  ← 本次采用" if abs(thr - args.threshold) < 1e-9 else ""
        print(f"{thr:6.2f} {prec:8.3f} {rec:8.3f} {fpr:10.3f}{mark}")

    if auc < 0.75:
        print("\n⚠ AUC < 0.75：判别能力不足。"
              "结果只能用于「排序提议」，不得用于自动删除。")
    if auc < 0.65 and not args.force:
        print("\n❌ AUC < 0.65：判别能力不足以支撑任何自动决策，已中止打分。")
        print("   改走纯人工分档（联系表复核）。")
        print("   确需继续请加 --force（风险自负）。")
        return 1

    # ---- score the pool ----
    pipe.fit(X, y)
    Xall = np.array([r["f"] for r in pool if r.get("f")], dtype="float32")
    rs = 1.0 - pipe.predict_proba(Xall)[:, 1]
    scored = {}
    for r, s in zip([r for r in pool if r.get("f")], rs):
        scored[r["path"]] = float(s)
    hit = sum(1 for s in scored.values() if s >= args.threshold)
    print(f"\n阈值 {args.threshold}: {len(scored)} 张中 {hit} 张判为剔除"
          f"（{hit/len(scored):.1%}）")

    if not args.apply:
        print("\n[dry-run] 未写入文件，加 --apply 执行")
        return 0
    Path(args.out).write_text(json.dumps(
        {"auc": float(auc), "threshold": args.threshold, "scores": scored},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
