# -*- coding: utf-8 -*-
"""由构建好的 index.html 反向生成 Markdown 归档版。

用途：把 HTML 报告转成可投喂知识库 / 可进 Word 的纯文本结构版。
原则：正文逐字保留，只做标记转换；照片以图片链接 + 图注形式保留。
输出：输出/WorkBuddy实战落地营_完整课程要点_0915/课程要点_0915.md
"""
import io
import os
import re
from html.parser import HTMLParser

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
OUT = CFG.report_dir
INDEX = os.path.join(OUT, 'index.html')
MD = os.path.join(OUT, os.path.basename(CFG.md_name()))

VOID = {'br', 'img', 'meta', 'link', 'input', 'hr', 'col', 'source'}


class Node(object):
    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.kids = []
        self.text = None

    def cls(self):
        return self.attrs.get('class', '')

    def find_all(self, tag=None, cls=None):
        out = []
        for k in self.kids:
            if k.text is not None:
                continue
            if (tag is None or k.tag == tag) and (cls is None or cls in k.cls().split()):
                out.append(k)
            out.extend(k.find_all(tag, cls))
        return out

    def first(self, tag=None, cls=None):
        r = self.find_all(tag, cls)
        return r[0] if r else None


class Builder(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].kids.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        t = Node('#text')
        t.text = data
        self.stack[-1].kids.append(t)


# ---------------------------------------------------------------- 内联渲染

def inline(n):
    """把节点渲染成单行 markdown 文本。"""
    if n.text is not None:
        return re.sub(r'\s+', ' ', n.text)
    cls = n.cls()
    if n.tag == 'span' and 'lb' in cls.split():
        return ''
    inner = ''.join(inline(k) for k in n.kids)
    inner = re.sub(r'\s+', ' ', inner).strip()
    if n.tag == 'br':
        return ' '
    if n.tag == 'img':
        src = n.attrs.get('src') or n.attrs.get('data-src') or ''
        return '![](%s)' % src
    if n.tag in ('b', 'strong'):
        return '**%s**' % inner if inner else ''
    if n.tag == 'em':
        return '*%s*' % inner if inner else ''
    if n.tag == 'code':
        return '`%s`' % inner if inner else ''
    if n.tag == 'a':
        href = n.attrs.get('href', '')
        return '[%s](%s)' % (inner, href) if href.startswith('#') and inner else inner
    if n.tag == 'u':
        return inner
    return inner


def li_text(node):
    return re.sub(r'\s+', ' ', inline(node)).strip()


def plain(n, skip_badge=False):
    """纯文本（不带任何 markdown 标记）；可选跳过 .badge 标签。"""
    if n is None:
        return ''
    if n.text is not None:
        return re.sub(r'\s+', ' ', n.text)
    if skip_badge and n.tag == 'span' and 'badge' in n.cls().split():
        return ''
    return ''.join(plain(k, skip_badge) for k in n.kids).strip()


# ---------------------------------------------------------------- 块级渲染

def table_md(tbl):
    rows = []
    for tr in tbl.find_all('tr'):
        cells = []
        for c in tr.kids:
            if c.text is not None or c.tag not in ('td', 'th'):
                continue
            cells.append(re.sub(r'\s+', ' ', inline(c)).strip().replace('|', '\\|') or ' ')
        if cells:
            rows.append(cells)
    if not rows:
        return ''
    ncol = max(len(r) for r in rows)
    rows = [r + [' '] * (ncol - len(r)) for r in rows]
    out = ['| ' + ' | '.join(rows[0]) + ' |',
           '|' + '|'.join([' --- '] * ncol) + '|']
    out += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
    return '\n'.join(out)


def render(node, depth=0):
    """返回 markdown 文本（块级）。"""
    if node.text is not None:
        t = re.sub(r'\s+', ' ', node.text).strip()
        return t
    tag, cls = node.tag, node.cls().split()

    if tag in ('style', 'script', 'canvas', 'head', 'title', 'meta', 'link'):
        return ''

    # ---------- 容器 ----------
    if tag == 'div' and 'zoom' in cls:
        return ''
    if tag == 'div' and 'wrap' in cls:
        return render_kids(node)

    # ---------- Hero ----------
    if tag == 'header' and 'hero' in cls:
        ey = node.first('div', 'eyebrow')
        h1 = node.first('h1')
        sub = node.first('p', 'hero-sub')
        meta = node.first('div', 'meta')
        out = ['# %s' % plain(h1) if h1 else '', '']
        if ey:
            out.append('> %s' % plain(ey))
        if sub:
            out.append('')
            out.append(inline(sub))
        if meta:
            items = []
            for s in meta.find_all('span'):
                lab = s.first('i')
                val = inline(s).replace(plain(lab), '', 1).strip() if lab else inline(s).strip()
                items.append('**%s**：%s' % (plain(lab), val) if lab else val)
            out += ['', ' ｜ '.join(items)]
        out.append('')
        return '\n'.join(out)

    # ---------- 目录 ----------
    if tag == 'nav' and 'toc' in cls:
        h2 = node.first('h2')
        out = ['## 目录', '', '*%s*' % inline(h2) if h2 else '', '']
        grid = node.first('div', 'toc-grid') or node
        for d in [k for k in grid.kids if k.tag == 'div' and k.text is None]:
            b = d.first('b')
            a = d.first('a')
            if a and b:
                out.append('- **%s** [%s](#%s)' % (plain(b), plain(a),
                                                  a.attrs.get('href', '#')[1:]))
        out.append('')
        return '\n'.join(out)

    # ---------- 章节 ----------
    if tag == 'section':
        no = None
        h2 = None
        st = None
        for k in node.kids:
            if k.text is not None:
                continue
            if 'sec-h' in k.cls():
                d = k.first('div', 'no')
                no = inline(d) if d else ''
                h2 = k.first('h2')
                s = k.first('div', 'st')
                st = plain(s) if s else ''
        out = ['', '---', '', '## %s %s' % (no, inline(h2) if h2 else ''), '']
        if st:
            out += ['*%s*' % st, '']
        # 正文（跳过 sec-h 自身）
        for k in node.kids:
            if k.text is not None:
                continue
            if 'sec-h' in k.cls():
                continue
            out.append(render(k, depth))
        return '\n'.join(out)

    # ---------- 标题 ----------
    if tag == 'h3':
        return '\n### %s\n' % inline(node)
    if tag == 'h4':
        return '\n#### %s\n' % inline(node)
    if tag == 'h5':
        return '\n**%s**\n' % plain(node, True)

    if tag == 'p':
        t = re.sub(r'\s+', ' ', inline(node)).strip()
        return ('\n%s\n' % t) if t else ''

    # ---------- 引用 / 总结 / 资产 / 提示 ----------
    if tag == 'div' and 'quote' in cls:
        label = '课堂数据' if 'd' in cls else '老师原话'
        body = '\n'.join(render(k, depth) for k in node.kids if k.text is None)
        body = body.strip()
        return '\n> **【%s】**\n>\n%s\n' % (
            label, '\n'.join('> ' + l for l in body.splitlines() if l.strip()))
    if tag == 'div' and 'mine' in cls:
        body = '\n'.join(render(k, depth) for k in node.kids if k.text is None).strip()
        return '\n> 🦞 **【我的总结】**\n>\n%s\n' % '\n'.join(
            '> ' + l for l in body.splitlines() if l.strip())
    if tag == 'div' and 'asset' in cls:
        body = '\n'.join(render(k, depth) for k in node.kids if k.text is None).strip()
        return '\n> 📦 **【可复用资产】**\n>\n%s\n' % '\n'.join(
            '> ' + l for l in body.splitlines() if l.strip())
    if tag == 'div' and 'hl' in cls:
        lb = node.first('span', 'lb')
        label = re.sub(r'\s+', ' ', inline(lb)).strip() if lb else '提示'
        rest = [render(k, depth) for k in node.kids
                if k.text is None and 'lb' not in k.cls().split()]
        body = '\n'.join(rest).strip()
        return '\n> ⚠️ **【%s】**\n>\n%s\n' % (
            label, '\n'.join('> ' + l for l in body.splitlines() if l.strip()))

    # ---------- 指标卡 / 小卡 ----------
    if tag == 'div' and 'kv' in cls:
        out = []
        for i in node.find_all('div', 'i'):
            v = i.first('div', 'v')
            k = i.first('div', 'k')
            out.append('- **%s** —— %s' % (inline(v), inline(k)))
        return '\n' + '\n'.join(out) + '\n'

    if tag == 'div' and 'card' in cls:
        h5 = node.first('h5')
        out = []
        if h5:
            out.append('\n**%s**' % inline(h5))
        for k in node.kids:
            if k.text is not None or k.tag == 'h5':
                continue
            out.append(render(k, depth))
        return '\n'.join(out)

    # ---------- 框架重建图 ----------
    if tag == 'div' and 'kfig' in cls:
        h5 = node.first('h5')
        sub = node.first('div', 'sub')
        out = ['', '> **🧩 重建框架：%s**' % (plain(h5, True) if h5 else '')]
        if sub:
            out.append('> *%s*' % plain(sub))
        out.append('')
        for k in node.kids:
            if k.text is not None or k.tag == 'h5' or k.cls() == 'sub':
                continue
            out.append(render(k, depth))
        return '\n'.join(out)

    # ---------- 表格 ----------
    if tag == 'table':
        return '\n' + table_md(node) + '\n'
    if tag == 'div' and 'tw' in cls:
        return render_kids(node)

    # ---------- 照片 ----------
    if tag == 'div' and 'shot' in cls:
        a = node.first('a')
        cap = node.first('div', 'cap')
        href = a.attrs.get('href', '') if a else ''
        capjs = re.sub(r'\s+', ' ', inline(cap)).strip() if cap else ''
        return '\n![%s](%s)\n' % (capjs, href)
    if tag == 'div' and 'shots' in cls:
        return render_kids(node)
    if tag == 'details':
        sm = node.first('summary')
        out = ['', '**📷 相册 · %s**' % (plain(sm) if sm else ''), '']
        # 相册内照片：按分组折叠成"编号"清单，避免 md 过长
        for h in node.find_all('h4'):
            out.append('\n*%s*' % plain(h))
        codes = []
        for a in node.find_all('a'):
            href = a.attrs.get('href', '')
            m = re.search(r'images/([pm]\d+)\.jpg', href)
            if m:
                codes.append(m.group(1))
        if codes:
            out.append('\n' + '、'.join(codes))
        return '\n'.join(out) + '\n'

    # ---------- 流程 / 步骤 / 列表 ----------
    if tag == 'div' and 'flow' in cls:
        out = []
        for i, st in enumerate([x for x in node.find_all('div') if 'st' in x.cls().split()], 1):
            n = st.first('div', 'n')
            t = st.first('div', 't')
            d = st.first('div', 'd')
            out.append('%d. **%s**（%s）：%s' % (i, inline(t), inline(n), inline(d)))
        return '\n' + '\n'.join(out) + '\n'
    if tag == 'ol':
        out = []
        for i, li in enumerate([x for x in node.kids if x.tag == 'li'], 1):
            out.append('%d. %s' % (i, li_text(li)))
        return '\n' + '\n'.join(out) + '\n'
    if tag == 'ul':
        out = []
        for li in [x for x in node.kids if x.tag == 'li']:
            t = li_text(li)
            out.append('- %s' % t)
        return '\n' + '\n'.join(out) + '\n'

    # ---------- 定义列表 ----------
    if tag == 'div' and 'dl' in cls:
        out = []
        for d in [x for x in node.kids if 'd' in x.cls().split()]:
            dt = d.first('dt')
            dd = d.first('dd')
            out.append('- **%s**：%s' % (inline(dt), inline(dd)))
        return '\n' + '\n'.join(out) + '\n'

    # ---------- Prompt ----------
    if tag == 'div' and 'pbox' in cls:
        h = node.first('div', 'pbox-h')
        pre = node.first('pre')
        span = h.first('span') if h else None
        title = re.sub(r'\s+', ' ', inline(span)).strip() if span else ''
        body = raw_text(pre) if pre else ''
        return '\n**%s**\n\n```text\n%s\n```\n' % (title, body)
    if tag == 'pre':
        return '\n```text\n%s\n```\n' % raw_text(node)

    if tag == 'footer':
        out = ['', '---', '', '## 标注体系 · 四档忠实度', '']
        for s in node.find_all('span'):
            out.append('- %s' % re.sub(r'\s+', ' ', inline(s)).strip())
        for p in node.find_all('p'):
            t = re.sub(r'\s+', ' ', inline(p)).strip()
            if t:
                out += ['', t]
        return '\n'.join(out) + '\n'

    if tag == 'figure':
        return render_kids(node)
    return render_kids(node)


def render_kids(node):
    parts = []
    for k in node.kids:
        if k.text is not None:
            t = re.sub(r'\s+', ' ', k.text).strip()
            if t:
                parts.append(t)
            continue
        parts.append(render(k))
    return '\n'.join(p for p in parts if p is not None)


def raw_text(node):
    """保留 pre 内的原始换行与缩进。"""
    out = []

    def walk(n):
        if n.text is not None:
            out.append(n.text)
        for k in n.kids:
            walk(k)
    walk(node)
    s = ''.join(out)
    return s.strip('\n')


def main():
    html = io.open(INDEX, encoding='utf-8').read()
    b = Builder()
    b.feed(html)
    md = render_kids(b.root)
    md = re.sub(r'[ \t]+\n', '\n', md)
    md = re.sub(r'\n{4,}', '\n\n\n', md)
    md = md.strip() + '\n'
    with io.open(MD, 'w', encoding='utf-8') as f:
        f.write(md)
    print('Markdown 归档版 → %s  (%.0f KB / %d 字符)'
          % (MD, os.path.getsize(MD) / 1024, len(md)))
    # 快速体检
    for pat, name in [(r'^## ', '二级标题'), (r'^### ', '三级标题'),
                      (r'【老师原话】', '老师原话'), (r'【课堂数据】', '课堂数据'),
                      (r'【我的总结】', '我的总结'), (r'【可复用资产】', '可复用资产'),
                      (r'^```text', 'Prompt 代码块'), (r'^\|', '表格行'),
                      (r'^!\[', '图片引用')]:
        print('   %-14s %d' % (name, len(re.findall(pat, md, re.M))))


if __name__ == '__main__':
    main()
