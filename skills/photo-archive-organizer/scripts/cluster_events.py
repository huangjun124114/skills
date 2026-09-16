#!/usr/bin/env python3
"""Mode B, step P5: group dated photos into events.

Algorithm (never merge across months — early versions leaked 2018→2021 into
one "event"):
  1. Within each YYYYMM, sort by date and cut sessions where the gap between
     consecutive days exceeds `--gap` (default 2).
  2. Any session larger than `--target` (default 70) is split with **Ward**
     agglomerative clustering on `[PCA(visual, 64) | day_offset * alpha]`.
     Average linkage was tried and collapses into one giant cluster plus
     singletons — do not switch it back.
  3. Sub-clusters smaller than `--min-size` (default 5) merge back into the
     nearest surviving cluster of the same session.
  4. Whatever is still below `--min-size` is dropped per the rules.

Usage:
    python cluster_events.py --feats feats.json --visual visual.npy \
        --out events.json --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def day_num(d: str | None):
    if not d or len(d) != 8:
        return None
    try:
        return date(int(d[:4]), int(d[4:6]), int(d[6:8])).toordinal()
    except ValueError:
        return None


def build_sessions(recs, gap):
    """Cut a month's photos into sessions of near-contiguous days."""
    sessions, cur = [], []
    prev = None
    for r in sorted(recs, key=lambda x: (x["d"] or "99999999", x["path"])):
        dn = day_num(r["d"])
        if prev is not None and dn is not None and (dn - prev) > gap:
            sessions.append(cur)
            cur = []
        cur.append(r)
        if dn is not None:
            prev = dn
    if cur:
        sessions.append(cur)
    return sessions


def split_session(sess, visual, idx_of, target, maxk, alpha, min_size):
    """Return a list of index-lists: one per sub-event."""
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.decomposition import PCA

    idxs = [idx_of[r["path"]] for r in sess]
    if len(idxs) <= target:
        return [idxs]

    days = []
    for r in sess:
        dn = day_num(r["d"])
        days.append(dn if dn is not None else 0)
    base = min(d for d in days if d) if any(days) else 0
    tcoord = np.array([(d - base) if d else 0 for d in days],
                      dtype="float32").reshape(-1, 1) * alpha

    X = visual[idxs]
    n_comp = min(64, X.shape[0], X.shape[1])
    pca = PCA(n_components=n_comp, random_state=0).fit(X)
    Z = np.hstack([pca.transform(X), tcoord])

    k = max(2, min(maxk, len(idxs) // max(min_size, 1)))
    labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(Z)

    groups = defaultdict(list)
    for lbl, i in zip(labels, idxs):
        groups[int(lbl)].append(i)
    big = [g for g in groups.values() if len(g) >= min_size]
    small = [i for g in groups.values() if len(g) < min_size for i in g]
    if not big:
        return [idxs]
    # fold singletons into the largest cluster of this session
    big.sort(key=len, reverse=True)
    big[0].extend(small)
    return big


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", required=True, help="extract_features.py JSON")
    ap.add_argument("--visual", required=True, help="visual matrix .npy")
    ap.add_argument("--out", required=True)
    ap.add_argument("--gap", type=int, default=2)
    ap.add_argument("--target", type=int, default=70)
    ap.add_argument("--maxk", type=int, default=4)
    ap.add_argument("--alpha", type=float, default=2.0)
    ap.add_argument("--min-size", type=int, default=5)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    import numpy as np
    recs = json.loads(Path(args.feats).read_text(encoding="utf-8"))
    visual = np.load(args.visual)
    if len(recs) != visual.shape[0]:
        print(f"ERROR: {len(recs)} 条元数据 vs {visual.shape[0]} 行视觉特征，不匹配")
        return 1
    idx_of = {r["path"]: i for i, r in enumerate(recs)}

    by_month = defaultdict(list)
    for r in recs:
        by_month[r["ym"]].append(r)

    events, dropped = [], 0
    eid = 0
    for ym in sorted(by_month):
        for sess in build_sessions(by_month[ym], args.gap):
            for grp in split_session(sess, visual, idx_of, args.target,
                                     args.maxk, args.alpha, args.min_size):
                if len(grp) < args.min_size:
                    dropped += len(grp)
                    continue
                members = [recs[i] for i in grp]
                ds = sorted(m["d"] for m in members if m["d"])
                events.append({
                    "eid": eid, "ym": ym, "n": len(members),
                    "d0": ds[0] if ds else None, "d1": ds[-1] if ds else None,
                    "paths": [m["path"] for m in members],
                })
                eid += 1

    sizes = [e["n"] for e in events]
    print(f"事件总数 {len(events)}   照片 {sum(sizes)} 张   "
          f"不足 {args.min_size} 张被丢弃 {dropped} 张")
    if sizes:
        print(f"单事件最少 {min(sizes)} 张 / 最多 {max(sizes)} 张 / 中位 "
              f"{sorted(sizes)[len(sizes)//2]} 张")
    spans = sorted({e["ym"] for e in events})
    print(f"覆盖年月 {spans[0]} ~ {spans[-1]}（共 {len(spans)} 个月）")
    print("\n最大的 10 个事件：")
    for e in sorted(events, key=lambda x: -x["n"])[:10]:
        print(f"  E{e['eid']:3d} {e['ym']} {e['d0']}~{e['d1']} n={e['n']}")

    if not args.apply:
        print("\n[dry-run] 未写入文件，加 --apply 执行")
        return 0
    Path(args.out).write_text(json.dumps(events, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
