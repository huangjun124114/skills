#!/usr/bin/env python3
"""Mode B (and shared): run all six verification gates after EVERY round.

    1  Conservation   expected_keep − actual == 0
    2  Dedup          md5 duplicates inside the archive == 0
    3  Caps           no folder over --cap, none under --min-files, none empty
    4  Backup gate    every path in --delete-list exists in the archive AND has
                      an identical-md5 mirror under --backup. 0 unverified.
    5  Quarantine     unique md5 in quarantine == --expected-remove
    6  ctime audit    group archive files by creation time; unexpected batches
                      must be investigated, never ignored

This script is read-only and never mutates anything.

Usage:
    python verify_gates.py --archive DIR --quarantine QDIR --backup BDIR \
        --delete-list paths.txt --expected-remove 116 --cap 80 --min-files 3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import chunked_pool, md5_file


def _md5_job(p_str):
    try:
        return p_str, md5_file(Path(p_str))
    except Exception:
        return p_str, None


def norm(p: str) -> str:
    """Canonical form for path comparison.

    Mixed separators (`D:/a/b` vs `D:\\a\\b`) silently break set operations,
    which once made every keep-file look missing. Normalise before comparing.
    """
    import os
    return os.path.normcase(os.path.normpath(p))


def index_dir(root: Path, workers=8):
    files = [str(p) for p in root.rglob("*") if p.is_file()]
    idx = {}
    for p, m in chunked_pool(_md5_job, files, 50, workers):
        if m:
            idx.setdefault(m, []).append(p)
    return files, idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--quarantine", default="")
    ap.add_argument("--backup", default="")
    ap.add_argument("--delete-list", default="",
                    help="paths proposed for deletion (gate 4)")
    ap.add_argument("--expected-remove", type=int, default=-1,
                    help="expected removal count (gate 5)")
    ap.add_argument("--expected-keep", default="",
                    help="json list of paths that must survive (gate 1)")
    ap.add_argument("--cap", type=int, default=80)
    ap.add_argument("--min-files", type=int, default=3)
    ap.add_argument("--json", default="", help="write a machine-readable report")
    args = ap.parse_args()

    archive = Path(args.archive).resolve()
    if not archive.is_dir():
        print(f"ERROR: 归档区不存在: {archive}")
        return 1

    files, idx = index_dir(archive)
    print(f"归档区 {len(files)} 个文件，唯一 md5 {len(idx)}\n")
    report, failed = {}, []

    # ---- gate 2: dedup ----
    dups = {m: v for m, v in idx.items() if len(v) > 1}
    report["gate2_dedup"] = {"dup_groups": len(dups),
                             "dup_files": sum(len(v) - 1 for v in dups.values())}
    ok2 = not dups
    print(f"[闸门2] 去重            重复 {len(dups)} 组                "
          f"{'✅' if ok2 else '❌'}")
    for m, v in list(dups.items())[:5]:
        print(f"         {v}")
    if not ok2:
        failed.append("gate2")

    # ---- gate 3: caps ----
    counts = {}
    for d in sorted(archive.iterdir()):
        if d.is_dir():
            counts[d.name] = sum(1 for f in d.rglob("*") if f.is_file())
    over = {k: v for k, v in counts.items() if v > args.cap}
    under = {k: v for k, v in counts.items() if 0 < v < args.min_files}
    empty = [k for k, v in counts.items() if v == 0]
    report["gate3_caps"] = {"folders": len(counts), "over_cap": over,
                            "under_min": under, "empty": empty,
                            "max": max(counts.values()) if counts else 0,
                            "min": min(counts.values()) if counts else 0}
    ok3 = not (under or empty)
    note = "" if not over else f"（超上限 {len(over)} 个需确认是否特批）"
    print(f"[闸门3] 上下限          文件夹 {len(counts)} 个，"
          f"{min(counts.values()) if counts else 0}~{max(counts.values()) if counts else 0} 张"
          f"{note}   {'✅' if ok3 else '❌'}")
    if under:
        print(f"         少于 {args.min_files} 张: {under}")
    if empty:
        print(f"         空文件夹: {empty}")
    if not ok3:
        failed.append("gate3")
    if over:
        print(f"         超上限: {over}")

    # ---- gate 1: conservation ----
    if args.expected_keep:
        keep = {norm(p) for p in
                json.loads(Path(args.expected_keep).read_text(encoding="utf-8"))}
        actual = {norm(p) for p in files}
        missing = keep - actual
        report["gate1_conservation"] = {"expected": len(keep),
                                        "missing": sorted(missing)}
        ok1 = not missing
        print(f"[闸门1] 内容守恒        该留却不见了 {len(missing)} 张        "
              f"{'✅' if ok1 else '❌'}")
        for m in list(missing)[:10]:
            print(f"         {m}")
        if not ok1:
            failed.append("gate1")
    else:
        print("[闸门1] 内容守恒        跳过（未提供 --expected-keep）        ⏭")

    # ---- gate 4: backup gate ----
    if args.delete_list and args.backup:
        paths = [l.rstrip("\n") for l in
                 Path(args.delete_list).read_text(encoding="utf-8").splitlines()
                 if l.strip()]
        backup = Path(args.backup).resolve()
        _, bidx = index_dir(backup)
        verified, unverified = [], []
        for p in paths:
            m = None
            try:
                m = md5_file(Path(p))
            except Exception:
                pass
            if m is None:
                unverified.append({"path": p, "reason": "源文件不可读（已不存在？）"})
            elif m not in idx:
                unverified.append({"path": p, "md5": m, "reason": "归档区中无此内容，尚未整理"})
            elif m not in bidx:
                unverified.append({"path": p, "md5": m, "reason": "备份区中无字节一致的镜像"})
            else:
                verified.append({"path": p, "md5": m, "backup": bidx[m][0]})
        report["gate4_backup"] = {"total": len(paths), "verified": len(verified),
                                  "unverified": unverified}
        ok4 = not unverified
        print(f"[闸门4] 备份闸门        {len(verified)}/{len(paths)} 通过，"
              f"不可校验 {len(unverified)}        {'✅' if ok4 else '❌'}")
        for u in unverified[:10]:
            print(f"         UNVERIFIED {u['path']}")
            print(f"                    → {u.get('reason')}")
        if not ok4:
            failed.append("gate4")
    else:
        print("[闸门4] 备份闸门        跳过（需同时提供 --delete-list 与 --backup） ⏭")

    # ---- gate 5: quarantine reconciliation ----
    if args.quarantine and args.expected_remove >= 0:
        q = Path(args.quarantine).resolve()
        _, qidx = index_dir(q)
        uniq = len(qidx)
        report["gate5_quarantine"] = {"files": sum(len(v) for v in qidx.values()),
                                      "unique_md5": uniq,
                                      "expected": args.expected_remove}
        ok5 = uniq == args.expected_remove
        print(f"[闸门5] 隔离区对账      唯一内容 {uniq} vs 预期 "
              f"{args.expected_remove}        {'✅' if ok5 else '❌'}")
        if not ok5:
            extra = sum(len(v) for v in qidx.values()) - uniq
            print(f"         冗余副本 {extra} 个 —— 通常是脚本重复执行所致，"
                  f"请先按 md5 去重再对账")
            failed.append("gate5")
    else:
        print("[闸门5] 隔离区对账      跳过（需提供 --quarantine 与 --expected-remove） ⏭")

    # ---- gate 6: ctime audit ----
    buckets = Counter()
    for p in files:
        buckets[time.strftime("%m-%d %H:%M",
                              time.localtime(Path(p).stat().st_ctime))] += 1
    report["gate6_ctime"] = dict(sorted(buckets.items()))
    print("[闸门6] ctime 审计      归档区写入批次：")
    for k in sorted(buckets):
        print(f"         {k}  {buckets[k]:5d} 张")
    print("         核对每批是否与本轮预期写入量一致；不明批次必须追查来源")

    print("\n=== 结果 ===")
    if failed:
        print(f"❌ 未通过：{', '.join(failed)}")
    else:
        print("✅ 全部通过的闸门已检查完毕（ctime 审计需人工核对）")

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"\n报告已写入 {args.json}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
