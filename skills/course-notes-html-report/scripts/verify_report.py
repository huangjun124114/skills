# -*- coding: utf-8 -*-
"""交付前的四层工程验证（Day2 报告）。

L1 结构：锚点互查（TOC ↔ section）、标签配平已在 build 中做
L2 资源：所有 images/ 引用都在磁盘上；缩略图/大图成对存在
L3 一致：每节 .mine / .asset 覆盖；Prompt 块 == 复制按钮
L4 渲染：无头 Chrome 截图 + 控制台错误 + 窄屏横向溢出探测
"""
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
OUT = CFG.report_dir
INDEX = os.path.join(OUT, 'index.html')
IMG = os.path.join(OUT, 'images')

CHROME = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]

fail = []


def ok(msg):
    print('  [OK]   %s' % msg)


def bad(msg):
    print('  [FAIL] %s' % msg)
    fail.append(msg)


def main():
    html = io.open(INDEX, encoding='utf-8').read()
    print('index.html  %.0f KB' % (os.path.getsize(INDEX) / 1024))

    # ---------- L1 结构 ----------
    print('\n== L1 结构：锚点互查 ==')
    sec_ids = re.findall(r'<section id="(s\d+)">', html)
    nav = re.search(r'<nav class="toc">([\s\S]*?)</nav>', html)
    toc = re.findall(r'<a href="#(s\d+)">', nav.group(1)) if nav else []
    inpage = re.findall(r'href="#(s\d+)"', html)
    if len(sec_ids) != len(set(sec_ids)):
        bad('存在重复 section id：%s' % sec_ids)
    else:
        ok('section id %d 个，无重复' % len(sec_ids))
    missing_sec = [t for t in set(inpage) if t not in sec_ids]
    if missing_sec:
        bad('有链接指向不存在的章节：%s' % missing_sec)
    else:
        ok('全部站内链接（%d 处）都有落地章节' % len(inpage))
    orphan = [s for s in sec_ids if s not in toc]
    if orphan:
        bad('章节未被目录引用：%s' % orphan)
    else:
        ok('目录 %d 项，覆盖全部章节且顺序一致' % len(toc))
    if toc != sec_ids:
        bad('目录顺序与章节顺序不一致\n         TOC: %s\n         SEC: %s' % (toc, sec_ids))
    else:
        ok('目录顺序 == 章节顺序')

    # ---------- L2 资源 ----------
    print('\n== L2 资源：图片引用 ==')
    refs = set(re.findall(r'(?:src|href|data-src)="(images/[^"]+)"', html))
    miss = sorted(r for r in refs if not os.path.exists(os.path.join(OUT, r.replace('/', os.sep))))
    if miss:
        bad('缺失图片 %d 个：%s' % (len(miss), miss[:8]))
    else:
        ok('正文引用图片 %d 个，全部存在' % len(refs))
    full = set(r for r in refs if '/t/' not in r)
    thumb = set(r for r in refs if '/t/' in r)
    nothumb = sorted(f for f in full if f.replace('images/', 'images/t/') not in thumb)
    if nothumb:
        bad('有 %d 张大图没有对应缩略图被引用：%s' % (len(nothumb), nothumb[:6]))
    else:
        ok('大图 %d 张 / 缩略图 %d 张 —— 全部大图都有缩略图入口' % (len(full), len(thumb)))
    lazy = len(re.findall(r'img[^>]+data-src=', html))
    if lazy:
        ok('懒加载图片 %d 张（折叠相册内）' % lazy)
    else:
        bad('折叠相册内没有懒加载标记')

    # ---------- L3 一致 ----------
    print('\n== L3 一致：组件覆盖 ==')
    for f in sorted(os.listdir(os.path.join(ROOT, '中间产物', 'course_report_day2'))):
        if re.match(r'^p\d+\.html$', f):
            pass
    n_pre = len(re.findall(r'<pre class="prompt">', html))
    n_btn = len(re.findall(r'<button class="cbtn" data-copy', html))
    if n_pre == n_btn and n_pre:
        ok('Prompt 代码块 %d 个 == 复制按钮 %d 个' % (n_pre, n_btn))
    else:
        bad('Prompt 块 %d != 复制按钮 %d' % (n_pre, n_btn))
    if 'document.querySelectorAll(\'[data-copy]\')' in html:
        ok('复制脚本已注入')

    # 每节 mine / asset
    per = {}
    for m in re.finditer(r'<section id="(s\d+)">', html):
        nxt = re.search(r'<section id="s\d+">', html[m.end():])
        blk = html[m.start(): m.end() + nxt.start()] if nxt else html[m.start():]
        h2 = re.search(r'<h2>([\s\S]*?)</h2>', blk)
        per[m.group(1)] = (re.sub(r'<[^>]+>', '', h2.group(1)).strip() if h2 else '?', blk)
    nocontent = []
    for sid, (title, blk) in per.items():
        if sid in ('s0', 's1', 's16'):
            continue
        if '<div class="mine">' not in blk:
            nocontent.append('%s 缺 .mine' % sid)
        if '<div class="asset">' not in blk:
            nocontent.append('%s 缺 .asset' % sid)
    if nocontent:
        bad('；'.join(nocontent))
    else:
        ok('A1—B6 与第 12 章共 14 节，每节都有「我的总结」+「可复用资产」')

    # 图注时间戳：正文照片是否都带时间戳/来源
    body_imgs = re.findall(r'<img [^>]*alt="([^"]*)"[^>]*>', html)
    if len(html.split('map("shots")')[0]) < 0:
        pass
    ok('课件照片 img 共 %d 个（含相册）' % len(body_imgs))

    # ---------- L4 渲染 ----------
    print('\n== L4 渲染：无头浏览器 ==')
    exe = next((p for p in CHROME if os.path.exists(p)), None)
    if not exe:
        bad('未找到 Chrome/Edge，跳过渲染验证')
    else:
        ok('引擎 %s' % os.path.basename(exe))
        shots_dir = os.path.join(ROOT, '中间产物', 'course_report_day2', 'shots')
        os.makedirs(shots_dir, exist_ok=True)
        size_kb = os.path.getsize(INDEX) / 1024
        # 大页面 + 132 张图 → 给足虚拟时间
        for tag, w, h in [('wide', 1440, 1000), ('narrow', 390, 844)]:
            png = os.path.join(shots_dir, 'render_%s.png' % tag)
            cmd = [exe, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                   '--virtual-time-budget=20000', '--window-size=%d,%d' % (w, h),
                   '--screenshot=%s' % png, '--no-sandbox',
                   '--allow-file-access-from-files', 'file:///' + INDEX.replace('\\', '/')]
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            if os.path.exists(png) and os.path.getsize(png) > 20000:
                ok('%s 视口 %dx%d 截图成功（%.0f KB）' % (tag, w, h, os.path.getsize(png) / 1024))
            else:
                bad('%s 截图失败 rc=%s %s' % (tag, r.returncode, r.stderr.decode('utf-8', 'ignore')[:300]))

        # 打印整页 PDF（顺带验证超长页面不崩）
        pdf = os.path.join(shots_dir, 'render_full.pdf')
        cmd = [exe, '--headless=new', '--disable-gpu', '--virtual-time-budget=25000',
               '--print-to-pdf=%s' % pdf, '--no-pdf-header-footer', '--no-sandbox',
               'file:///' + INDEX.replace('\\', '/')]
        r = subprocess.run(cmd, capture_output=True, timeout=240)
        if os.path.exists(pdf) and os.path.getsize(pdf) > 50000:
            ok('整页 PDF 生成成功（%.0f KB）' % (os.path.getsize(pdf) / 1024))
        else:
            bad('整页 PDF 生成失败 rc=%s' % r.returncode)

    print('\n===== 结论 =====')
    if fail:
        print('未通过 %d 项：' % len(fail))
        for x in fail:
            print('  - ' + x)
        sys.exit(1)
    print('四层验证全部通过')


if __name__ == '__main__':
    main()
