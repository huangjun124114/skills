# -*- coding: utf-8 -*-
"""
侧栏高亮配色的视觉验证（三种分组：A 蓝 / B 金 / 中性）。
无头环境截不到「非零滚动位置」，而侧栏是 fixed 的——直接把高亮态摆出来截图即可，
滚动跟随的正确性已由 qa_nav_spy.py 的 17/17 走查覆盖。
"""
import io
import os
import subprocess

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
HERE = CFG.work
OUTDIR = CFG.report_dir
SRC = os.path.join(OUTDIR, os.path.basename(CFG.sidenav_name()))
SHOTS = os.path.join(HERE, 'shots')
os.makedirs(SHOTS, exist_ok=True)

CHROME = (r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
          if os.path.exists(r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe')
          else r'C:\Program Files\Google\Chrome\Application\chrome.exe')


def inject(target, prog):
    return ("<script>setTimeout(function(){"
            "document.querySelectorAll('a.snav.on').forEach(function(a){"
            "a.classList.remove('on');a.removeAttribute('aria-current');});"
            "var t=document.querySelector('a.snav[href=\"#%s\"]');"
            "if(t){t.classList.add('on');t.setAttribute('aria-current','true');"
            "t.scrollIntoView({block:'center'});}"
            "var b=document.querySelector('.side-prog i');if(b)b.style.width='%s';"
            "},260);</script>" % (target, prog))


CASES = [
    # 名, 目标锚点, 进度, 宽, 高
    ('nav_hl_A_blue', 's5', '22%', 1440, 1000),      # 上半场 A4 → 蓝色高亮
    ('nav_hl_B_gold', 's11', '58%', 1440, 1000),     # 下半场 B3 → 金色高亮
    ('nav_hl_misc', 's15', '82%', 1440, 1000),       # 工具箱 → 中性高亮
    ('nav_wide_1920', 's4', '35%', 1920, 1080),      # 宽屏布局
]


def main():
    html = io.open(SRC, encoding='utf-8').read()
    for name, target, prog, w, h in CASES:
        tmp = os.path.join(OUTDIR, '_qa_hl.html')
        k = html.rfind('</body>')
        io.open(tmp, 'w', encoding='utf-8').write(
            html[:k] + inject(target, prog) + html[k:])
        png = os.path.join(SHOTS, name + '.png')
        cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
               '--allow-file-access-from-files', '--hide-scrollbars',
               '--window-size=%d,%d' % (w, h),
               '--virtual-time-budget=20000', '--screenshot=' + png,
               'file:///' + tmp.replace('\\', '/')]
        subprocess.run(cmd, capture_output=True, timeout=240)
        sz = os.path.getsize(png) // 1024 if os.path.exists(png) else 0
        print('%-20s %s -> %5d KB' % (name, target, sz))
        os.remove(tmp)


if __name__ == '__main__':
    main()
