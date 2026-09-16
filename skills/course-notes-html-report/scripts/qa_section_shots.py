# -*- coding: utf-8 -*-
"""关键章节截图（视觉 QA）。

无头 Chrome 在「滚动后的视口」上常常截到空白，因此改为：
把目标 <section> 抽出来，配上同一套 CSS 单独成页（滚动位置=0），再截图。
临时页面写在交付目录内，保证 images/ 相对路径可用；用完即删。
"""
import io
import os
import re
import subprocess

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
HERE = CFG.work
OUT = CFG.report_dir
INDEX = os.path.join(OUT, 'index.html')
SHOTS = os.path.join(HERE, 'shots')
CH = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'

TARGETS = [
    ('A_s0_kmap', 's0', 1440), ('A_s2_A1', 's2', 1440), ('A_s4_A3', 's4', 1440),
    ('A_s7_A6', 's7', 1440), ('A_s8_A7', 's8', 1440), ('B_s9_B1', 's9', 1440),
    ('B_s10_B2', 's10', 1440), ('B_s12_B4', 's12', 1440), ('B_s13_B5', 's13', 1440),
    ('C_s15_toolbox', 's15', 1440), ('C_s16_appendix', 's16', 1440),
    ('N_s0_narrow', 's0', 390), ('N_s8_narrow', 's8', 390),
]


def sections(html):
    out = {}
    ms = list(re.finditer(r'<section id="(s\d+)">', html))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else html.find('</section>', m.start())
        if i + 1 < len(ms):
            out[m.group(1)] = html[m.start():end]
        else:
            e = html.find('</section>', m.start())
            out[m.group(1)] = html[m.start():e + 10]
    return out


def main():
    os.makedirs(SHOTS, exist_ok=True)
    html = io.open(INDEX, encoding='utf-8').read()
    head = io.open(os.path.join(HERE, 'head.html'), encoding='utf-8').read()
    secs = sections(html)
    print('抽出章节: %s' % ' '.join(sorted(secs)))
    tmps = []
    try:
        for tag, anchor, w in TARGETS:
            body = secs.get(anchor)
            if not body:
                print('%-16s 章节缺失' % tag)
                continue
            tmp = os.path.join(OUT, '_qa_%s.html' % tag)
            with io.open(tmp, 'w', encoding='utf-8') as f:
                f.write('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
                        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
                        + head + '\n<style>header.hero,nav.toc{display:none!important}'
                        'body{padding-top:14px}</style></head><body>\n'
                        '<div class="wrap">\n' + body + '\n</div></body></html>')
            tmps.append(tmp)
            png = os.path.join(SHOTS, 'qa_%s.png' % tag)
            # 先量高度：用一个超高视口截一次全量，再按内容裁剪
            tall = min(9000, 2400)
            cmd = [CH, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                   '--virtual-time-budget=15000', '--window-size=%d,%d' % (w, tall),
                   '--screenshot=%s' % png, '--no-sandbox',
                   '--allow-file-access-from-files', 'file:///' + tmp.replace('\\', '/')]
            try:
                subprocess.run(cmd, capture_output=True, timeout=200)
            except Exception as e:
                print('%-16s ERR %s' % (tag, e))
                continue
            print('%-16s %-5s %4dw  %s' % (tag, '#' + anchor, w,
                                           ('%.0f KB' % (os.path.getsize(png) / 1024))
                                           if os.path.exists(png) else 'FAILED'))
    finally:
        for t in tmps:
            try:
                os.remove(t)
            except OSError:
                pass
        print('临时文件已清理')


if __name__ == '__main__':
    main()
