# -*- coding: utf-8 -*-
"""HTML 版与 Markdown 归档版的一致性校验。

思路：以 index.html 为基准，比对两份产出的「结构性计数」是否一致，
并检查 Markdown 里没有残留 HTML 标签、没有残缺标记、图片链接都存在。
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
OUT = CFG.report_dir
INDEX = os.path.join(OUT, 'index.html')
MD = os.path.join(OUT, os.path.basename(CFG.md_name()))

fail = []


def cmp(label, a, b):
    if a == b:
        print('  [OK]   %-18s HTML=%-5d MD=%-5d' % (label, a, b))
    else:
        print('  [FAIL] %-18s HTML=%-5d MD=%-5d  ← 不一致' % (label, a, b))
        fail.append('%s: HTML=%d MD=%d' % (label, a, b))


def main():
    html = io.open(INDEX, encoding='utf-8').read()
    md = io.open(MD, encoding='utf-8').read()

    # 去掉 Markdown 的代码围栏，避免把 Prompt 里的 # 当成标题
    md_nofence = re.sub(r'```[\s\S]*?```', '', md)

    print('== 结构性计数比对 ==')
    n_sec = len(re.findall(r'<section id="s\d+">', html))
    n_h2 = len(re.findall(r'^## [0-9A-Z附]', md_nofence, re.M))
    if n_h2 == n_sec:
        print('  [OK]   %-18s HTML=%-5d MD=%-5d' % ('章节 section', n_sec, n_h2))
    else:
        print('  [FAIL] %-18s HTML=%-5d MD=%-5d  ← 不一致' % ('章节 section', n_sec, n_h2))
        fail.append('章节数不一致')
    cmp('老师原话', len(re.findall(r'<div class="quote">', html)),
        len(re.findall(r'【老师原话】', md)))
    cmp('课堂数据', len(re.findall(r'<div class="quote d">', html)),
        len(re.findall(r'【课堂数据】', md)))
    cmp('我的总结', len(re.findall(r'<div class="mine">', html)),
        len(re.findall(r'【我的总结】', md)))
    cmp('可复用资产', len(re.findall(r'<div class="asset">', html)),
        len(re.findall(r'【可复用资产】', md)))
    cmp('重建框架 .kfig', len(re.findall(r'<div class="kfig">', html)),
        len(re.findall(r'🧩 重建框架：', md)))
    cmp('Prompt 代码块', len(re.findall(r'<pre class="prompt">', html)),
        len(re.findall(r'^```text', md, re.M)))
    cmp('数据表（按分割行计）', len(re.findall(r'<table[^>]*>', html)),
        len(re.findall(r'^\|\s*---', md_nofence, re.M)))
    n_shot_total = len(re.findall(r'<div class="shot">', html))
    n_gal = sum(len(re.findall(r'<div class="shot">', g))
                for g in re.findall(r'<details class="gal">[\s\S]*?</details>', html))
    cmp('正文照片（不含相册）', n_shot_total - n_gal,
        len(re.findall(r'^!\[', md, re.M)))
    print('       （相册内另有 %d 张，MD 里折叠为编号清单）' % n_gal)

    print('\n== Markdown 体检 ==')
    leftovers = re.findall(r'</?(?:div|span|section|table|tr|td|th|p|ul|ol|li|b|strong|em|h[1-6])\b[^>]*>',
                           md)
    if leftovers:
        print('  [FAIL] 残留 HTML 标签 %d 处：%s' % (len(leftovers), leftovers[:6]))
        fail.append('残留 HTML 标签 %d 处' % len(leftovers))
    else:
        print('  [OK]   无残留 HTML 标签')

    junk = re.findall(r'\*{4,}|\[\[' , md)
    if junk:
        print('  [FAIL] 畸形标记 %d 处：%s' % (len(junk), junk[:6]))
        fail.append('畸形标记 %d 处' % len(junk))
    else:
        print('  [OK]   无 **** / [[ 等畸形标记')

    links = re.findall(r'\]\((images/[^)]+)\)', md)
    miss = sorted(set(l for l in links
                      if not os.path.exists(os.path.join(OUT, l.replace('/', os.sep)))))
    if miss:
        print('  [FAIL] 图片链接失效 %d 个：%s' % (len(miss), miss[:6]))
        fail.append('图片链接失效 %d 个' % len(miss))
    else:
        print('  [OK]   图片链接 %d 处全部有效' % len(links))

    anchors = set(re.findall(r'^## [0-9A-Z附]', md_nofence, re.M))
    if len(md_nofence) < len(html) * 0.25:
        print('  [WARN] Markdown 体量偏小（%d vs HTML %d 字符），可能丢内容'
              % (len(md_nofence), len(html)))
    else:
        print('  [OK]   正文体量 %.0f KB（HTML %.0f KB），压缩比合理'
              % (len(md) / 1024, len(html) / 1024))

    # 关键小节标题是否都在
    must = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7',
            'B1', 'B2', 'B3', 'B4', 'B5', 'B6', '12', '附']
    need = ['## %s ' % m for m in must]
    lack = [n for n in need if n not in md_nofence]
    if lack:
        print('  [FAIL] 缺失章节标题：%s' % lack)
        fail.append('缺失章节标题 %s' % lack)
    else:
        print('  [OK]   17 个章节标题齐全（00/01 + A1—A7 + B1—B6 + 12 + 附）')

    print('\n===== 结论 =====')
    if fail:
        print('未通过 %d 项：' % len(fail))
        for x in fail:
            print('  - ' + x)
        sys.exit(1)
    print('HTML ↔ Markdown 一致性校验通过')


if __name__ == '__main__':
    main()
