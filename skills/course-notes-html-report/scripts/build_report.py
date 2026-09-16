# -*- coding: utf-8 -*-
"""课程要点报告构建脚本（分片拼接 + 相册注入 + 内联图表 + 交互脚本）。

- 拼接 head.html + p1..pN.html（按文件名数字排序）
- 替换相册占位符 <!--GALLERY:shots--> / <!--GALLERY:manual-->（读 image_map.json 现场生成）
- 内联 Chart.js（仅当片段中出现 canvas 且文件存在）
- 注入交互脚本（Prompt 复制按钮 + 照片灯箱 + 折叠相册懒加载）
- 标签配平自检 + 内容统计
- 输出 目录式交付：<报告目录>/index.html

用法：
  python build_report.py --root <项目根> --task <任务名> --report <报告目录名>
  python build_report.py --frag 3          # 只构建到第 3 片（调试）
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

HERE = CFG.work
ROOT = CFG.root
OUTDIR = CFG.report_dir
CHARTJS = CFG.chartjs

# ============================================================
#  场次信息（每场只改这一段）
# ============================================================
# 覆盖相册摘要行；留空 {} 则自动生成（照片用时间范围，手册用「按手册步骤顺序排列」）
# 例：GALLERY_TIPS = {'manual': ('操作手册截图 · 27 张', '《XX 操作手册》｜ 按手册步骤顺序排列')}
GALLERY_TIPS = {}

TAIL_JS = """
<script>
(function(){
  /* ---------- Prompt 复制 ---------- */
  function copyText(t){
    if (navigator.clipboard && navigator.clipboard.writeText){
      return navigator.clipboard.writeText(t);
    }
    return new Promise(function(res, rej){
      try{
        var ta = document.createElement('textarea');
        ta.value = t; ta.style.position='fixed'; ta.style.opacity='0';
        document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta); res();
      }catch(e){ rej(e); }
    });
  }
  document.querySelectorAll('[data-copy]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var box = btn.closest('.pbox');
      var pre = box ? box.querySelector('pre') : null;
      if (!pre) return;
      copyText(pre.innerText).then(function(){
        var old = btn.getAttribute('data-old') || '复制';
        btn.setAttribute('data-old', old);
        btn.textContent = '已复制'; btn.classList.add('ok');
        setTimeout(function(){ btn.textContent = old; btn.classList.remove('ok'); }, 1600);
      }).catch(function(){ btn.textContent = '请手动选择'; });
    });
  });

  /* ---------- 照片灯箱 ---------- */
  var z = document.getElementById('zoom');
  if (z){
    var zi = z.querySelector('img'), zc = z.querySelector('.zc');
    function closeZoom(){
      z.classList.remove('on'); zi.removeAttribute('src');
      document.documentElement.style.overflow = '';
    }
    document.addEventListener('click', function(e){
      var a = e.target && e.target.closest ? e.target.closest('a[data-zoom]') : null;
      if (a){
        e.preventDefault();
        zi.src = a.getAttribute('href');
        zc.innerHTML = a.getAttribute('data-cap') || '';
        z.classList.add('on');
        document.documentElement.style.overflow = 'hidden';
        return;
      }
      if (e.target === z || (e.target.closest && e.target.closest('.zx'))) closeZoom();
    });
    document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeZoom(); });
  }

  /* ---------- 折叠相册：展开后再懒加载，避免首屏拉全部图 ---------- */
  document.querySelectorAll('details.gal').forEach(function(d){
    d.addEventListener('toggle', function(){
      if (d.open){
        d.querySelectorAll('img[data-src]').forEach(function(im){
          im.src = im.getAttribute('data-src'); im.removeAttribute('data-src');
        });
      }
    });
  });
})();
</script>
"""

PAIRS = ['div', 'section', 'table', 'ol', 'ul', 'dl', 'figure', 'header', 'footer',
         'details', 'aside', 'nav', 'article', 'main', 'span', 'a', 'p', 'h1', 'h2',
         'h3', 'h4', 'h5', 'pre', 'code', 'button', 'summary', 'b', 'strong', 'em', 'dt', 'dd']


# ============================================================
#  照片总览相册：由 image_map.json 自动生成，保证与素材目录同步
# ============================================================

def _strip(s):
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def photo_sections(fs):
    """扫描片段，返回 {code: (no, title)} —— 每张照片第一次被引用的章节。"""
    own = {}
    for f in fs:
        t = read(os.path.join(HERE, f))
        no = title = None
        for m in re.finditer(r'<section id="(s\d+)"|class="no">([^<]+)<|<h2>([\s\S]*?)</h2>'
                             r'|images/t/([pm]\d+)\.jpg', t):
            if m.group(1):
                no, title = None, None
            elif m.group(2):
                no = m.group(2).strip()
            elif m.group(3):
                title = _strip(m.group(3))
            else:
                code = m.group(4)
                if code not in own and no:
                    own[code] = (no, title or '')
    return own


def _thumb_size(w, h):
    tw = 560 if w > 560 else w
    return tw, max(1, round(h * tw / float(w)))


def _shot_item(code, sec, meta, kind):
    """单张照片的相册卡片。"""
    if kind == 'shots':
        tm = meta.get('time', '')
        cap = '%s ｜ %s · %s' % (sec, code, tm)
        sub = '<span class="src tm">%s</span>' % tm
        alt = '%s 课件照片 %s' % (code, tm)
    else:
        lb = meta.get('label', '')
        cap = '%s ｜ %s' % (code, lb)
        sub = '<span class="src tm">%s</span>' % lb
        alt = '%s %s' % (code, lb)
    tw, th = _thumb_size(meta.get('w', 560), meta.get('h', 560))
    return ('<div class="shot">'
            '<a href="images/%s.jpg" data-zoom data-cap="%s">'
            '<img src="images/t/%s.jpg" data-src="images/t/%s.jpg" alt="%s" '
            'loading="lazy" width="%d" height="%d"></a>'
            '<div class="cap"><b>%s</b>%s</div></div>'
            % (code, cap, code, code, alt, tw, th, code, sub))


def gallery(kind, fs, mp, tips=None):
    """生成一个折叠相册（shots 按章节分组 / manual 按编号顺序）。

    tips: {'shots': (前缀, 提示行), 'manual': (前缀, 提示行)}，不传则自动生成。
    """
    tips = tips or {}
    items = mp[kind]
    own = photo_sections(fs) if kind == 'shots' else {}
    out = []
    if kind == 'shots':
        groups = []
        order = []
        for it in items:
            sec = own.get(it['code'])
            key = ('%s · %s' % sec) if sec else '未在正文单独引用（相似页／重复拍摄）'
            if key not in groups:
                groups.append(key)
                order.append(key)
        grouped = dict((k, []) for k in order)
        for it in items:
            sec = own.get(it['code'])
            key = ('%s · %s' % sec) if sec else '未在正文单独引用（相似页／重复拍摄）'
            grouped[key].append(it)
        ts = [it.get('time', '') for it in items if it.get('time')]
        tmin, tmax = (min(ts), max(ts)) if ts else ('', '')
        pre = '现场课件照片 · %d 张' % len(items)
        tip = ('%s—%s ｜ 按章节分组，展开后才开始加载图片' % (tmin, tmax)) if ts \
            else '按章节分组，展开后才开始加载图片'
        pre, tip = tips.get('shots') or (pre, tip)
        for key in order:
            out.append('<h4 class="sub2">%s <span class="src">（%d 张）</span></h4>'
                       % (key, len(grouped[key])))
            out.append('<div class="shots three">')
            out.extend(_shot_item(it['code'], key, it, kind)
                       for it in grouped[key])
            out.append('</div>')
    else:
        pre = '操作手册截图 · %d 张' % len(items)
        tip = '按手册步骤顺序排列'
        pre, tip = tips.get('manual') or (pre, tip)
        out.append('<div class="shots three">')
        out.extend(_shot_item(it['code'], '手册', it, kind) for it in items)
        out.append('</div>')
    return ('<details class="gal"><summary>%s <em>｜ %s</em></summary>'
            '<div class="gb">%s</div></details>' % (pre, tip, '\n'.join(out)))


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def fragments():
    fs = [f for f in os.listdir(HERE) if re.match(r'^p\d+\.html$', f)]
    fs.sort(key=lambda x: int(re.findall(r'\d+', x)[0]))
    limit = None
    if '--frag' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--frag') + 1])
    return fs[:limit] if limit else fs


def balance(html, label):
    """标签配平粗检：返回问题列表（不求完美，抓明显漏闭合）。"""
    bad = []
    for tag in PAIRS:
        op = len(re.findall(r'<%s(?=[\s>])' % tag, html))
        cl = len(re.findall(r'</%s>' % tag, html))
        # 自闭合不计
        selfclose = len(re.findall(r'<%s[^>]*/>' % tag, html))
        if op - selfclose != cl:
            bad.append('%-9s 开 %3d  闭 %3d  差 %+d' % (tag, op - selfclose, cl, (op - selfclose) - cl))
    return bad


def main():
    fs = fragments()
    if not fs:
        print('!! 没有找到任何 pN.html 片段')
        return
    print('片段顺序: %s' % ' '.join(fs))

    head = read(os.path.join(HERE, 'head.html'))
    body = '\n'.join(read(os.path.join(HERE, f)) for f in fs)

    # ---- 照片总览相册（占位符替换）----
    mapfile = os.path.join(HERE, 'image_map.json')
    if '<!--GALLERY:' in body and os.path.exists(mapfile):
        mp = json.load(io.open(mapfile, encoding='utf-8'))
        for kind in ('shots', 'manual'):
            tok = '<!--GALLERY:%s-->' % kind
            if tok in body:
                body = body.replace(tok, gallery(kind, fs, mp, GALLERY_TIPS))
                print('相册注入: %-6s %d 张' % (kind, len(mp[kind])))

    has_canvas = '<canvas' in body
    chart_js = ''
    if has_canvas and os.path.exists(CHARTJS):
        chart_js = '<script>\n' + read(CHARTJS) + '\n</script>\n'
        print('检测到 canvas → 内联 Chart.js（%.0f KB）' % (os.path.getsize(CHARTJS) / 1024))
    elif has_canvas:
        print('!! 检测到 canvas 但缺少 chart.umd.min.js')

    zoom_dom = ('<div class="zoom" id="zoom" role="dialog" aria-modal="true">'
                '<button class="zx" aria-label="关闭">×</button>'
                '<img alt="课件大图"><div class="zc"></div></div>')

    html = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            + head + '\n</head>\n<body>\n'
            + zoom_dom + '\n'
            + body + '\n'
            + chart_js + TAIL_JS + '</body>\n</html>\n')

    # ---- 自检 ----
    print('\n== 标签配平自检 ==')
    problems = balance(html, 'full')
    if problems:
        for b in problems:
            print('   ' + b)
    else:
        print('   全部配平')

    # ---- 输出 ----
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, 'index.html')
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    print('\n== 输出 ==')
    print('   %s  %.0f KB' % (out, os.path.getsize(out) / 1024))
    img = os.path.join(OUTDIR, 'images')
    if os.path.isdir(img):
        n = len([x for x in os.listdir(img) if x.endswith('.jpg')])
        n2 = len(os.listdir(os.path.join(img, 't'))) if os.path.isdir(os.path.join(img, 't')) else 0
        print('   images/  %d 张大图 + %d 张缩略图' % (n, n2))

    # ---- 内容统计 ----
    print('\n== 内容统计 ==')
    for label, pat in [('章节 section', r'<section id="s\d+"'),
                       ('老师原话 .quote', r'<div class="quote">'),
                       ('课堂数据 .quote.d', r'<div class="quote d">'),
                       ('我的总结 .mine', r'<div class="mine">'),
                       ('可复用资产 .asset', r'<div class="asset">'),
                       ('高亮块 .hl', r'<div class="hl'),
                       ('Prompt 块', r'<pre class="prompt">'),
                       ('复制按钮', r'data-copy'),
                       ('课件照片 <img>', r'<img '),
                       ('灯箱链接', r'data-zoom'),
                       ('框架重建 .kfig', r'<div class="kfig">'),
                       ('表格 <table>', r'<table'),
                       ('折叠相册', r'<details class="gal"')]:
        c = len(re.findall(pat, html))
        print('   %-16s %d' % (label, c))
    plain = re.sub(r'<(script|style)[\s\S]*?</\1>', '', html)
    plain = re.sub(r'<[^>]+>', '', plain)
    print('   正文净字数      %d' % len(re.sub(r'\s+', '', plain)))


if __name__ == '__main__':
    main()
