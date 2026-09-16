#!/usr/bin/env python3
"""Phase 2 — Safe backup before any mutation.

On Windows uses `robocopy /E /COPYALL`; elsewhere uses shutil.copytree.
The backup is removed only after verification (Phase 7) and explicit approval.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def backup(src: Path, dst: Path):
    if dst.exists():
        print(f"WARN: destination {dst} already exists; robocopy will merge.")
    if sys.platform.startswith("win"):
        # robocopy returns 0-7 on success, >=8 on failure
        cmd = ["robocopy", str(src), str(dst), "/E", "/COPYALL", "/R:1", "/W:1", "/NFL", "/NDL"]
        print("Running:", " ".join(cmd))
        rc = subprocess.run(cmd).returncode
        ok = rc < 8
        return ok, rc
    else:
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        return True, 0


def main():
    ap = argparse.ArgumentParser(description="Safe backup of a photo directory.")
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--apply", action="store_true", help="Actually perform the backup")
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    if not src.exists():
        print(f"ERROR: source {src} does not exist")
        return 1

    if not args.apply:
        print(f"[DRY-RUN] Would back up:\n  {src}\n  -> {dst}")
        print("Pass --apply to execute.")
        return 0

    ok, rc = backup(src, dst)
    print(f"Backup {'OK' if ok else 'FAILED'} (rc={rc})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
