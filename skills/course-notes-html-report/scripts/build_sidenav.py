# -*- coding: utf-8 -*-
"""
构建「左侧常驻导航版」—— 由已构建好的主报告派生，不修改主报告。

输入：输出/WorkBuddy实战落地营_完整课程要点_0915/index.html   （主报告，只读）
输出：输出/WorkBuddy实战落地营_完整课程要点_0915/index_左侧导航版_0915.html

做四件事（正文 DOM 一字不改，只做三处结构性追加 + body 加一个 class）：
  1) </style> 前追加侧栏样式块
  2) <div class="wrap"> 前插入 <aside class="side"> + 抽屉按钮 + 遮罩
  3) </body> 前追加侧栏交互脚本（scroll spy / 进度条 / 抽屉 / 平滑定位）
  4) <body> → <body class="has-side" id="top">

导航项直接从主报告的 <nav class="toc"> 里解析，保证与目录零偏差。
纯原生 JS + CSS，无任何外部依赖，file:// 直接双击可开。
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
HERE = CFG.work
OUTDIR = CFG.report_dir
SRC = os.path.join(OUTDIR, 'index.html')
DST = os.path.join(OUTDIR, os.path.basename(CFG.sidenav_name()))

# ============================================================
#  场次信息（每场只改这一段）
# ============================================================
BRAND = {
    'k': '混沌 · 大湾区 AI 先锋计划',                        # 侧栏小字 kicker
    't': 'WorkBuddy AI 实战落地营<br>完整课程要点',            # 侧栏主标题（可含 <br>）
    's': '深圳场 Day 2 · 09/15 上午场',                       # 侧栏副题
}
FOOT_STATS = None          # 侧栏页脚统计行；None = 从主报告自动统计
MIN_ITEMS = 8              # 目录解析项数下界（低于此值视为解析失败，直接退出）

# 分组副标题：写清模块名 / 讲者 / 时段，便于学员对上号
SUB_AM = '模块一《AI + 整合营销》· 李鸿毅 · 09:35—11:10'
SUB_PM = '模块二《AI 驱动爆款视频复刻与营销策略》· 李鸿毅 · 11:10—12:07'

# ---------- 侧栏分组定义：(组标题, 组副标题, 组 class, 命中条件) ----------
# 命中条件按 TOC 项的 <b> 序号判断；返回 True 即归入该组
GROUPS = [
    ('速览', '', '', lambda k: k in ('00', '01')),
    ('上半场 · 认知与战略层', SUB_AM, 'mg', lambda k: k.startswith('A')),
    ('下半场 · 内容工程与实操层', SUB_PM, 'pg', lambda k: k.startswith('B')),
    ('工具与参考', '', '', lambda k: True),          # 兜底
]


def auto_stats(html):
    """从主报告自动统计侧栏页脚数据（节数 / Prompt / 图片）。"""
    n_sec = len(re.findall(r'<section id="s\d+"', html))
    n_prompt = len(re.findall(r'<pre class="prompt">', html))
    n_img = len(set(re.findall(r'images/[pm]\d+\.jpg', html)))
    return '%d 节 · %d Prompt · %d 张图' % (n_sec, n_prompt, n_img)


def read(p):
    return io.open(p, encoding='utf-8').read()


def parse_toc(html):
    """从 <nav class="toc"> 解析出 [(序号, 锚点, 标题, 类别 class)]"""
    i = html.find('<nav class="toc">')
    j = html.find('</nav>', i)
    toc = html[i:j]
    items = []
    for m in re.finditer(
            r'<div(?:\s+class="(am|pm)")?>\s*<b>([^<]+)</b>\s*<a href="#(s\d+)">([^<]+)</a>',
            toc):
        cls, key, sid, title = m.group(1) or '', m.group(2).strip(), m.group(3), m.group(4).strip()
        items.append((key, sid, title, cls))
    return items


def build_nav_html(items, tpl):
    """按分组生成侧栏列表，替换模板中的 side-scroll 内容"""
    used = set()
    buf = []
    for gtitle, gsub, gcls, hit in GROUPS:
        picked = [it for it in items if it[0] not in used and hit(it[0])]
        if not picked:
            continue
        for it in picked:
            used.add(it[0])
        gcls_attr = (' ' + gcls) if gcls else ''
        sub = ('<small>%s</small>' % gsub) if gsub else ''
        buf.append('    <div class="snav-g%s">%s%s</div>' % (gcls_attr, gtitle, sub))
        for key, sid, title, cls in picked:
            acls = ('snav ' + cls) if cls else 'snav'
            buf.append('    <a class="%s" href="#%s" title="%s"><em>%s</em>'
                       '<span class="tx">%s</span></a>' % (acls, sid, title, key, title))
        buf.append('')
    inner = '\n'.join(buf).rstrip()

    # 用 .side-foot 作右锚点，整块替换（非贪婪 + </div> 只会吃掉第一个内层 div）
    pat = r'<div class="side-scroll">[\s\S]*?(?=\s*<div class="side-foot">)'
    assert re.search(pat, tpl), '未定位到 side-scroll 区块'
    return re.sub(pat, '<div class="side-scroll">\n' + inner + '\n  </div>\n\n  ',
                  tpl, count=1)


def main():
    html = read(SRC)
    css = read(os.path.join(HERE, 'sidenav', 'sidenav_css.html'))
    nav = read(os.path.join(HERE, 'sidenav', 'sidenav_nav.html'))
    js = read(os.path.join(HERE, 'sidenav', 'sidenav_js.html'))

    items = parse_toc(html)
    if len(items) < MIN_ITEMS:
        print('[FAIL] 目录只解析到 %d 项（下界 %d）—— 检查主报告的 <nav class="toc"> 结构'
              % (len(items), MIN_ITEMS))
        sys.exit(1)
    print('目录解析：%d 项' % len(items))

    # ---- 侧栏品牌区与页脚文案（按场次改 BRAND）----
    nav = re.sub(r'<span class="sb-k">[^<]*</span>',
                 '<span class="sb-k">%s</span>' % BRAND['k'], nav, count=1)
    nav = re.sub(r'<span class="sb-t">[^<]*</span>',
                 '<span class="sb-t">%s</span>' % BRAND['t'], nav, count=1)
    nav = re.sub(r'<span class="sb-s">[^<]*</span>',
                 '<span class="sb-s">%s</span>' % BRAND['s'], nav, count=1)
    nav = re.sub(r'<span>\d+ 节[^<]*</span>',
                 '<span>%s</span>' % (FOOT_STATS or auto_stats(html)), nav, count=1)

    # ---- 用主报告的目录项重建侧栏列表（导航项永不与正文脱节）----
    nav = build_nav_html(items, nav)

    # ---- 1) 注入 CSS ----
    assert html.count('</style>') >= 1
    k = html.find('</style>')
    html = html[:k] + '\n' + css + '\n' + html[k:]

    # ---- 2) 注入侧栏 DOM ----
    k = html.find('<div class="wrap">')
    assert k > 0
    html = html[:k] + nav + '\n' + html[k:]

    # ---- 3) 注入 JS ----
    k = html.rfind('</body>')
    html = html[:k] + js + '\n' + html[k:]

    # ---- 4) body 标签 ----
    html = html.replace('<body>', '<body class="has-side" id="top">', 1)

    io.open(DST, 'w', encoding='utf-8').write(html)
    print('输出：%s  (%d chars, %.1f KB)' % (os.path.basename(DST), len(html), len(html) / 1024))

    # ---- 快速自检 ----
    ok = True
    # 外部「资源加载」才是离线隐患；正文里的 <a href="http..."> 是课件给的链接，不算依赖
    ext_res = (re.findall(r'<script[^>]*\bsrc\s*=\s*["\']https?://', html)
               + re.findall(r'<link[^>]*\bhref\s*=\s*["\']https?://', html)
               + re.findall(r'@import\s+(?:url\()?["\']?https?://', html)
               + re.findall(r'\bsrc\s*=\s*["\']https?://', html))
    checks = [
        ('侧栏 aside', html.count('<aside class="side"'), 1),
        ('侧栏导航项', len(re.findall(r'<a class="snav[^"]*" href="#s\d+"', html)), 17),
        ('body class', html.count('<body class="has-side" id="top">'), 1),
        ('侧栏样式块', html.count('v2 追加样式：左侧常驻导航栏'), 1),
        ('侧栏脚本块', html.count('v2：左侧常驻导航交互'), 1),
        ('section 总数', len(re.findall(r'<section id="s\d+"', html)), 17),
        ('Prompt 数', len(re.findall(r'<pre class="prompt">', html)), 12),
        ('外部资源加载', len(ext_res), 0),
        ('fetch/XHR', len(re.findall(r'fetch\(|XMLHttpRequest', html)), 0),
        ('历史遗留锚点', len(re.findall(r'href="#s(?:17|18|19|[2-9]\d)"', html)), 0),
    ]
    for name, got, want in checks:
        flag = 'OK  ' if got == want else 'FAIL'
        if got != want:
            ok = False
        print('  [%s] %-16s %s（期望 %s）' % (flag, name, got, want))

    print('\n结果：%s' % ('全部通过' if ok else '存在失败项'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
