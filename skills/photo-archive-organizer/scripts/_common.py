"""Shared helpers for the photo-archive-organizer skill.

All scripts in this skill import from here. Keep this module dependency-free
except for Pillow (imported lazily with an auto-install attempt).
"""
from __future__ import annotations

import struct
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".heic", ".tiff", ".webp"}
MOVIE_BOX_EXTS = {".mp4", ".mov", ".m4v", ".3gp"}


def ensure_pillow():
    """Import PIL, auto-installing Pillow if missing. Returns the module or None."""
    try:
        from PIL import Image  # noqa: F401
        return sys.modules["PIL"]
    except ImportError:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "Pillow"],
                check=True,
            )
            from PIL import Image  # noqa: F401
            return sys.modules["PIL"]
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# Extension repair via magic bytes
# --------------------------------------------------------------------------- #
def magic_ext(buf: bytes) -> str | None:
    """Return a canonical extension (with dot) inferred from the first bytes."""
    if not buf:
        return None
    head = buf[:16]
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head[:4] == b"%PDF":
        return ".pdf"
    if head[:2] in (b"BM",):
        return ".bmp"
    if head[:4] == b"II*\x00" or head[:4] == b"MM\x00*":
        return ".tiff"
    if head[:4] == b"ftyp":
        brand = head[8:12].lower()
        if b"heic" in head[:12].lower() or b"mif1" in head[:12].lower():
            return ".heic"
        if brand.startswith(b"mp4") or brand in (b"isom", b"m4v", b"avc1"):
            return ".mp4"
        if brand.startswith(b"qt") or brand == b"qt  ":
            return ".mov"
        # default video container
        return ".mp4"
    if head[:4] == b"webp":
        return ".webp"
    return None


# --------------------------------------------------------------------------- #
# Date inference (priority order)
# --------------------------------------------------------------------------- #
def video_date(path: Path) -> str | None:
    """Read mp4/mov `mvhd` creation_time (1904-01-01 epoch) → 'YYYYMM' or None."""
    try:
        if path.suffix.lower() not in MOVIE_BOX_EXTS:
            return None
        data = path.read_bytes()
    except Exception:
        return None
    i = data.find(b"mvhd")
    while i >= 0:
        if i + 4 < len(data):
            ver = data[i + 4]
            try:
                if ver == 0:
                    val = struct.unpack(">I", data[i + 8:i + 12])[0]
                elif ver == 1:
                    val = struct.unpack(">Q", data[i + 8:i + 16])[0]
                else:
                    i = data.find(b"mvhd", i + 1)
                    continue
                if val <= 0:
                    i = data.find(b"mvhd", i + 1)
                    continue
                dt = datetime(1904, 1, 1) + timedelta(seconds=val)
                if 2000 <= dt.year <= 2035:
                    return dt.strftime("%Y%m")
                i = data.find(b"mvhd", i + 1)
                continue
            except Exception:
                i = data.find(b"mvhd", i + 1)
                continue
        break
    return None


def exif_date(path: Path) -> str | None:
    """Read photo EXIF DateTimeOriginal/CreateDate → 'YYYYMM' or None."""
    PIL = ensure_pillow()
    if PIL is None:
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            ex = im.getexif()
            for tag in (36867, 36868, 306):  # DateTimeOriginal, DateTimeDigitized, DateTime
                v = ex.get(tag)
                if v:
                    digits = "".join(ch for ch in str(v) if ch.isdigit())
                    if len(digits) >= 6:
                        return digits[:6]
    except Exception:
        return None
    return None


def parse_filename_date(name: str) -> str | None:
    """Extract a date from a filename like 微信图片_20220901180257 or 2017-08-23."""
    import re
    stem = Path(name).stem
    # explicit full timestamp / date
    m = re.search(r"(19|20)\d{2}[_.\-]?\d{2}[_.\-]?\d{2}", stem)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) >= 6:
            y, mo = int(digits[:4]), int(digits[4:6])
            if 2000 <= y <= 2035 and 1 <= mo <= 12:
                return f"{y:04d}{mo:02d}"
    # WeChat style: 微信图片_20220901180257
    m = re.search(r"(19|20)\d{4}", stem)
    if m:
        digits = m.group(0)
        y, mo = int(digits[:4]), int(digits[4:6])
        if 2000 <= y <= 2035 and 1 <= mo <= 12:
            return digits
    return None


def parse_folder_date(name: str) -> str | None:
    """Extract YYYYMM from a folder name like 201701-学习照 or 2020-03旅行."""
    import re
    m = re.search(r"(19|20)\d{2}[_\-.]?\d{2}", name)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) >= 6:
            y, mo = int(digits[:4]), int(digits[4:6])
            if 2000 <= y <= 2035 and 1 <= mo <= 12:
                return f"{y:04d}{mo:02d}"
    return None


def parse_age(name: str, birth_year: int) -> str | None:
    """Infer YYYYMM from explicit age cues like '18-24个月' or '3岁' in the name."""
    import re
    # X-Y个月 or X个月
    m = re.search(r"(\d+)(?:-(\d+))?个?月", name)
    if m:
        months = int(m.group(1))
        y = birth_year + months // 12
        mo = (months % 12) + 1
        if mo > 12:
            y += 1
            mo = 1
        return f"{y:04d}{mo:02d}"
    # X岁 / X-Y岁
    m = re.search(r"(\d+)(?:-(\d+))?岁", name)
    if m:
        years = int(m.group(1))
        y = birth_year + years
        return f"{y:04d}01"
    return None


def infer_date(name: str, folder_name: str, birth_year: int | None, path: Path):
    """Return (yyyymm, source) using the priority chain, or (None, None).

    Priority: folder/filename date > EXIF > video mvhd > explicit age cue.
    """
    for src, fn in (
        ("folder-name", lambda: parse_folder_date(folder_name)),
        ("filename-date", lambda: parse_filename_date(name)),
        ("exif", lambda: exif_date(path) if path.suffix.lower() in PHOTO_EXTS else None),
        ("video-mvhd", lambda: video_date(path)),
    ):
        val = fn()
        if val:
            return val, src
    if birth_year:
        age = parse_age(name, birth_year) or parse_age(folder_name, birth_year)
        if age:
            return age, "age-inference"
    return None, None


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #
def md5_file(path: Path, chunk: int = 1 << 20) -> str:
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def print_affected(title: str, items):
    print(f"\n=== {title} ({len(items)} 项) ===")
    for it in items[:200]:
        print(f"  {it}")
    if len(items) > 200:
        print(f"  ... 其余 {len(items) - 200} 项省略")


# --------------------------------------------------------------------------- #
# Mode B helpers (filter-archive): layered date inference, quality scoring.
# Appended below the mode-A helpers; nothing above is modified.
# --------------------------------------------------------------------------- #
B_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tiff", ".bmp"}

# Common phone / PC screen aspect ratios (short/long), used as a screenshot cue.
SCREEN_AR = [9 / 16, 9 / 19.5, 9 / 20, 9 / 21, 3 / 4, 2 / 3, 10 / 16, 16 / 24,
             9 / 18, 1 / 2.16, 1 / 2, 4 / 3, 16 / 10, 16 / 9]


def ensure_heif() -> bool:
    """Register the pillow-heif opener. Returns False when HEIC is unsupported."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return True
    except Exception:
        return False


def clamp_ym(y: int, m: int, lo: str = "201501", hi: str = "202612"):
    """Return (yyyymm, in_range). Out-of-range values are kept but flagged."""
    ym = f"{y:04d}{m:02d}"
    return ym, (lo <= ym <= hi)


def exif_date_full(path: Path):
    """Return (yyyymmdd, yyyymm) from EXIF DateTimeOriginal, else (None, None)."""
    PIL = ensure_pillow()
    if PIL is None:
        return None, None
    try:
        from PIL import Image
        with Image.open(path) as im:
            ex = im.getexif()
            for tag in (36867, 36868, 306):
                v = ex.get(tag)
                if not v:
                    continue
                digits = "".join(ch for ch in str(v) if ch.isdigit())
                if len(digits) >= 8:
                    y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
                    if 1990 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                        return f"{y:04d}{mo:02d}{d:02d}", f"{y:04d}{mo:02d}"
    except Exception:
        return None, None
    return None, None


def parse_ymd(name: str):
    """YYYYMMDD from a filename such as IMG_20211127_094726."""
    import re
    m = re.search(r"(?<!\d)((?:19|20)\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?!\d)", Path(name).stem)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1990 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}{mo:02d}{d:02d}", f"{y:04d}{mo:02d}"
    return None, None


def parse_ts13(name: str):
    """13-digit epoch-ms timestamps (WeChat mmexport, Xiaohongshu Camera_XHS)."""
    import re
    m = re.search(r"(?<!\d)(1[5-9]\d{11})\d*", Path(name).stem)
    if not m:
        return None, None
    try:
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        dt = _dt(1970, 1, 1, tzinfo=_tz.utc) + _td(milliseconds=int(m.group(1)))
        dt = dt.astimezone(_tz(_td(hours=8)))
        if 1990 <= dt.year <= 2035:
            return dt.strftime("%Y%m%d"), dt.strftime("%Y%m")
    except Exception:
        return None, None
    return None, None


def xmp_date(path: Path):
    """photoshop:DateCreated / xmp:CreateDate from an embedded XMP packet."""
    try:
        head = path.open("rb").read(1 << 18)
    except Exception:
        return None, None
    i = head.find(b"<x:xmpmeta")
    if i < 0:
        return None, None
    j = head.find(b"</x:xmpmeta>", i)
    chunk = head[i:j if j > 0 else len(head)].decode("utf-8", "ignore")
    import re
    for tag in ("photoshop:DateCreated", "xmp:CreateDate", "xmp:MetadataDate"):
        m = re.search(tag + r'[^>]*>\s*([0-9]{4})[-:]([0-9]{2})[-:]([0-9]{2})', chunk)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1990 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}{mo:02d}{d:02d}", f"{y:04d}{mo:02d}"
    return None, None


def seq_of(name: str):
    """iPhone IMG_#### sequence number, or None."""
    import re
    m = re.match(r"IMG[_-]?(\d+)", Path(name).stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def loo_validate(items, win=150, min_k=3, agree=0.7):
    """Leave-one-out accuracy for sequence-number date interpolation.

    `items` is a list of (seq, ymd) with ymd possibly None. Returns
    (accuracy, mean_confidence) over the entries that currently have a date.
    """
    dated = [(s, d) for s, d in items if s is not None and d]
    if len(dated) < min_k + 1:
        return 0.0, 0.0
    hit = 0
    conf_sum = 0.0
    for i, (s, d) in enumerate(dated):
        near = [(s2, d2) for j, (s2, d2) in enumerate(dated)
                if j != i and abs(s2 - s) <= win]
        if len(near) < min_k:
            continue
        from collections import Counter
        cnt = Counter(d2 for _, d2 in near)
        best, n = cnt.most_common(1)[0]
        conf = n / len(near)
        conf_sum += conf
        if conf >= agree and best == d:
            hit += 1
    n_tried = sum(1 for s, d in dated
                  if sum(1 for s2, _ in dated if s2 is not None and abs(s2 - s) <= win) - 1 >= min_k)
    return ((hit / n_tried) if n_tried else 0.0), ((conf_sum / n_tried) if n_tried else 0.0)


def quality_score(sharp, px, ent, colourful, dark, blown, is_screenshot=0.0):
    """Weighted photo quality used for ranking only (not comparable across sets).

    Components are z-scored by the caller over the whole candidate pool:
      sharp      Laplacian variance          weight +0.35
      px         pixel count (log10)         weight +0.20
      ent        Shannon entropy of grey     weight +0.15
      colourful  Hasler-Susstrunk index      weight +0.15
      dark       ratio of very dark pixels   weight -0.075
      blown      ratio of blown-out pixels   weight -0.075
      is_screenshot  0/1 cue                 weight -0.10
    """
    return (0.35 * sharp + 0.20 * px + 0.15 * ent + 0.15 * colourful
            - 0.075 * dark - 0.075 * blown - 0.10 * is_screenshot)


def chunked_pool(func, items, chunk=50, workers=8):
    """Run `func` over `items` with a short-lived Pool per chunk.

    Windows multiprocessing dies silently on long runs; a crash then costs
    one chunk instead of the whole job, and the chunk falls back to serial.
    """
    out = []
    for s in range(0, len(items), chunk):
        part = items[s:s + chunk]
        try:
            import multiprocessing as mp
            with mp.Pool(workers) as pool:
                out.extend(pool.imap_unordered(func, part, chunksize=4))
        except Exception:
            out.extend(map(func, part))
    return out
