# -*- coding: utf-8 -*-
"""单独渲染两个照片相册（展开状态），验证网格与懒加载标记。"""
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
CH = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'

html = io.open(os.path.join(OUT, 'index.html'), encoding='utf-8').read()
head = io.open(os.path.join(HERE, 'head.html'), encoding='utf-8').read()
gals = re.findall(r'<details class="gal">[\s\S]*?</details>', html)
print('找到相册 %d 个' % len(gals))
gals = [g.replace('<details class="gal">', '<details class="gal" open>', 1) for g in gals]
tmp = os.path.join(OUT, '_qa_gal.html')
with io.open(tmp, 'w', encoding='utf-8') as f:
    f.write('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            + head + '</head><body><div class="wrap">' + '\n'.join(gals)
            + '</div></body></html>')
png = os.path.join(HERE, 'shots', 'qa_gallery.png')
cmd = [CH, '--headless=new', '--disable-gpu', '--hide-scrollbars',
       '--virtual-time-budget=20000', '--window-size=1440,2600',
       '--screenshot=%s' % png, '--no-sandbox', '--allow-file-access-from-files',
       'file:///' + tmp.replace('\\', '/')]
subprocess.run(cmd, capture_output=True, timeout=240)
print('截图 %.0f KB' % (os.path.getsize(png) / 1024))
os.remove(tmp)
