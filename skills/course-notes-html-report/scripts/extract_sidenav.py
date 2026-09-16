# -*- coding: utf-8 -*-
"""
从 Day1「左侧导航版」HTML 中抽取三段可复用模板：
  1) sidenav_css.html  —— v2 追加样式（左侧常驻导航栏）
  2) sidenav_nav.html  —— 侧栏 DOM 结构（<aside> + 抽屉按钮 + 遮罩）
  3) sidenav_js.html   —— 侧栏交互脚本（scroll spy / 进度条 / 抽屉 / 平滑定位）

抽取是纯文本切分，不修改 Day1 产物本身（只读）。
"""
import io
import os

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

HERE = CFG.work
# 来源：上一场的导航版成品。默认按当前报告名推导；换场次时用环境变量覆盖：
#   CR_SIDENAV_SRC="D:/.../上一场_左侧导航版.html" python extract_sidenav.py
SRC = os.environ.get('CR_SIDENAV_SRC', '') or CFG.sidenav_name()
DST = os.path.join(HERE, 'sidenav')
os.makedirs(DST, exist_ok=True)


def write(name, text):
    p = os.path.join(DST, name)
    io.open(p, 'w', encoding='utf-8').write(text)
    print('%-22s %6d chars' % (name, len(text)))


def main():
    src = io.open(SRC, encoding='utf-8').read()

    # ---------- 1. CSS ----------
    mark = '/* ===========================================================\n   v2 追加样式：左侧常驻导航栏'
    i = src.find(mark)
    assert i > 0, 'CSS 起点未找到'
    j = src.find('</style>', i)
    assert j > i, 'CSS 终点未找到'
    write('sidenav_css.html', src[i:j].rstrip() + '\n')

    # ---------- 2. 侧栏 DOM ----------
    i = src.find('<body class="has-side"')
    assert i > 0, 'body 标签未找到'
    i = src.find('>', i) + 1
    j = src.find('<div class="wrap">', i)
    assert j > i, 'wrap 起点未找到'
    write('sidenav_nav.html', src[i:j].strip() + '\n')

    # ---------- 3. JS ----------
    mark2 = 'v2：左侧常驻导航交互'
    k = src.find(mark2)
    assert k > 0, 'JS 标记未找到'
    i = src.rfind('<script>', 0, k)
    j = src.find('</script>', k) + len('</script>')
    write('sidenav_js.html', src[i:j] + '\n')


if __name__ == '__main__':
    main()
