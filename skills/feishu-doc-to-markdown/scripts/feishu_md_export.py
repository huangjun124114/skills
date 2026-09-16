#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书云文档 -> 本地可独立分发的 markdown。

处理内容：
  - <title> 元数据移除（文档标题体现在文件名 / 由调用方决定）
  - feishu.cn/file 图片   -> 下载到 images/，改为相对路径，按文件头补全扩展名
  - <figure><source/> 附件 -> 下载到 attachments/，改成本地链接
  - <grid>/<column> 分栏   -> 退化为顺序内容（不粘连）
  - <cite> 跨文档引用       -> 普通 https 链接
  - 原生 HTML <table>      -> markdown 表格（还原 rowspan/colspan）

用法：
  python feishu_md_export.py <文档URL或token> --outdir <输出目录> [--name <文件名前缀>]
"""
import argparse
import bisect
import json
import os
import re
import subprocess
import pathlib
import sys


# ----------------------------------------------------------- lark-cli 调用
def lark_prefix():
    """返回调用 lark-cli 的命令前缀。

    Windows 上 lark-cli 是 .cmd，subprocess 不能直接执行，
    因此优先用「node + run.js」的方式调用。
    """
    base = pathlib.Path.home() / ".workbuddy" / "binaries" / "node"
    run_js = (base / "cli-connector-packages" / "node_modules"
              / "@larksuite" / "cli" / "scripts" / "run.js")
    if run_js.exists():
        exe = "node.exe" if os.name == "nt" else "bin/node"
        vdir = base / "versions"
        if vdir.is_dir():
            for d in sorted(vdir.iterdir(), reverse=True):
                cand = d / ("node.exe" if os.name == "nt" else "bin/node")
                if cand.exists():
                    return [str(cand), str(run_js)]
    return ["lark-cli"]


def run_cli(args, timeout=900):
    cmd = lark_prefix() + args
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def fetch_doc(doc, fmt="markdown"):
    r = run_cli(["docs", "+fetch", "--doc", doc, "--doc-format", fmt, "--as", "user"], timeout=300)
    try:
        d = json.loads(r.stdout)
    except Exception:
        raise SystemExit(f"fetch 返回非 JSON：\n{r.stdout[:800]}\n{r.stderr[:400]}")
    if not d.get("ok"):
        raise SystemExit(f"fetch 失败：{json.dumps(d.get('error'), ensure_ascii=False)}")
    return d["data"]["document"]


def download(token, outpath, kind=None):
    outpath = pathlib.Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    args = ["docs", "+media-download", "--token", token,
            "--output", str(outpath), "--as", "user"]
    if kind:
        args += ["--type", kind]
    return run_cli(args)


# ----------------------------------------------------------- 文件辅助
IMG_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"BM", ".bmp"),
]
KNOWN_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def resolve(outpath):
    """下载后按实际落盘文件名返回（工具可能自动补扩展名）"""
    outpath = pathlib.Path(outpath)
    if outpath.is_file():
        return outpath
    hits = sorted(p for p in outpath.parent.glob(outpath.name + ".*") if p.is_file())
    return hits[0] if hits else None


def ensure_ext(path):
    """文件名本身带 '.' 时下载工具会误判为已有扩展名，需按文件头补全"""
    p = pathlib.Path(path)
    if p.suffix.lower() in KNOWN_EXT:
        return p
    with open(p, "rb") as fh:
        head = fh.read(16)
    ext = None
    for magic, e in IMG_MAGIC:
        if head.startswith(magic):
            ext = e
            break
    if ext is None and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        ext = ".webp"
    if ext is None:
        return p
    new = p.with_name(p.name + ext)
    p.rename(new)
    return new


TRAIL = "：:，,。.、；;！!？?）)】]」』\"'”’…·-— "
LEAD = "（(【[「『\"'“’·-— "


def slugify(s, maxlen=26):
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"www\.\S+", "", s)
    s = re.sub(r"[`*_>#]", "", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"[\\/:*?\"<>|]", "", s)
    s = re.sub(r"[\s\u3000]+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s)
    if len(s) > maxlen:
        s = s[:maxlen]
        idx = max([s.rfind(c) for c in "、，,。；;）)"] + [-1])
        if idx >= 8:
            s = s[:idx]
    s = s.strip(LEAD + "-").strip(TRAIL + "-")
    return s or "image"


def build_index(content):
    """(行列表, 行首偏移, 有意义行[(行号, 文本)])；跳过代码块与纯标记行"""
    lines = content.splitlines()
    starts, acc = [], 0
    for ln in lines:
        starts.append(acc)
        acc += len(ln) + 1
    skip = re.compile(r"^(<|>|\||-{3,}|!\[|```|https?://)")
    items, in_code = [], False
    for i, ln in enumerate(lines):
        t = ln.strip()
        if t.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not t or skip.match(t):
            continue
        t = re.sub(r"<[^>]+>", "", t).strip()
        if not t or re.match(r"^https?://", t):
            continue
        if t.startswith(("（", "(")) and len(t) > 20:
            continue
        if len(t) > 40:
            continue
        items.append((i, t))
    return lines, starts, items


def nearest_context(items, line_idx):
    for i, t in reversed(items):
        if i < line_idx:
            return t
    return "image"


def html_table_to_md(html):
    occupied = {}
    for ri, rh in enumerate(re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)):
        ci = 0
        for attrs, inner in re.findall(r"<t[dh]([^>]*)>(.*?)</t[dh]>", rh, re.S):
            while (ri, ci) in occupied:
                ci += 1
            text = re.sub(r"<br\s*/?>", " ", inner)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip().replace("|", "\\|")
            rs = re.search(r'rowspan="(\d+)"', attrs)
            cs = re.search(r'colspan="(\d+)"', attrs)
            rs = int(rs.group(1)) if rs else 1
            cs = int(cs.group(1)) if cs else 1
            for dr in range(rs):
                for dc in range(cs):
                    occupied[(ri + dr, ci + dc)] = text
            ci += cs
    if not occupied:
        return ""
    nrow = max(r for r, _ in occupied) + 1
    ncol = max(c for _, c in occupied) + 1
    grid = [[occupied.get((r, c), "") for c in range(ncol)] for r in range(nrow)]
    out = ["| " + " | ".join(grid[0]) + " |", "|" + "-|" * ncol]
    out += ["| " + " | ".join(r) + " |" for r in grid[1:]]
    return "\n".join(out)


IMG_RE = re.compile(r"!\[[^\]]*\]\((https://feishu\.cn/file/([A-Za-z0-9]+))\)")


def export(doc, outdir, name=None):
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    imgdir, attdir = outdir / "images", outdir / "attachments"

    docdata = fetch_doc(doc)
    content = docdata["content"]

    if not name:
        m = re.search(r"<title>(.*?)</title>", content, re.S)
        name = slugify(m.group(1)) if m else "document"

    # ---- 图片
    lines, starts, items = build_index(content)
    url2local = {}
    for i, m in enumerate(IMG_RE.finditer(content), 1):
        url, token = m.group(1), m.group(2)
        line_idx = bisect.bisect_right(starts, m.start()) - 1
        base = f"{i:02d}_{slugify(nearest_context(items, line_idx))}"
        r = download(token, imgdir / base)
        actual = resolve(imgdir / base)
        if actual is None:
            print(f"  !! 图片{i} 下载失败 {token} :: {r.stdout.strip()[:150]}", file=sys.stderr)
            continue
        actual = ensure_ext(actual)
        url2local[url] = f"images/{actual.name}"
        print(f"  img {i:>2} -> {actual.name}")

    # ---- 文件附件
    src_re = re.compile(r'<source\s+name="([^"]+)"[^>]*?\btoken="([A-Za-z0-9]+)"[^>]*/>')
    tok2local = {}
    for m in src_re.finditer(content):
        fname, token = m.group(1), m.group(2)
        safe = re.sub(r'[\\/:*?"<>|]', "_", fname)
        r = download(token, attdir / safe)
        actual = resolve(attdir / safe)
        if actual is None:
            print(f"  !! 附件下载失败 {fname} :: {r.stdout.strip()[:150]}", file=sys.stderr)
            continue
        tok2local[token] = f"attachments/{actual.name}"
        print(f"  file  -> {actual.name}  ({actual.stat().st_size/1048576:.1f} MB)")

    # ---- 结构转换
    md = content
    md = re.sub(r"<title>.*?</title>[ \t]*\r?\n?", "", md, count=1, flags=re.S)
    md = re.sub(
        r'<figure[^>]*>\s*<source\s+name="([^"]+)"[^>]*?\btoken="([A-Za-z0-9]+)"[^>]*/>\s*</figure>',
        lambda m: f"[{m.group(1)}]({tok2local.get(m.group(2), 'attachments/' + m.group(1))})", md)
    md = IMG_RE.sub(lambda m: f"![]({url2local.get(m.group(1), m.group(1))})", md)
    md = re.sub(
        r'<cite[^>]*doc-id="([^"]+)"[^>]*file-type="wiki"[^>]*title="([^"]+)"[^>]*>\s*</cite>',
        lambda m: f"[{m.group(2)}](https://my.feishu.cn/wiki/{m.group(1)})", md)
    md = re.sub(r"<p>\s*</p>", "", md)
    for tag in ("grid", "column"):          # 分栏 -> 换行，避免同一行内容粘连
        md = re.sub(rf"<{tag}[^>]*>", "\n\n", md)
        md = re.sub(rf"</{tag}>", "\n\n", md)
    md = re.sub(r"</?p[^>]*>", "", md)
    md = re.sub(r"</?blockquote[^>]*>", "", md)
    md = re.sub(r"</?figure[^>]*>", "", md)
    md = re.sub(r"<table>.*?</table>", lambda m: html_table_to_md(m.group(0)), md, flags=re.S)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"

    out = outdir / f"{name}.md"
    out.write_text(md, encoding="utf-8", newline="\n")

    # ---- 自检
    left = re.findall(r"feishu\.cn/file/\S+|</?(?:title|source|figure|grid|column|cite|table)\b", md)
    print(f"  => {out}")
    print(f"  图片 {len(url2local)} / 附件 {len(tok2local)} / 残留标记 {len(left)}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc", help="飞书文档 URL 或 token")
    ap.add_argument("--outdir", required=True, help="输出目录")
    ap.add_argument("--name", help="输出文件名前缀（默认取文档标题）")
    a = ap.parse_args()
    export(a.doc, a.outdir, a.name)


if __name__ == "__main__":
    main()
