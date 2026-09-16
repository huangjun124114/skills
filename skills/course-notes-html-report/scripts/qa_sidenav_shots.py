# -*- coding: utf-8 -*-
"""
左侧导航版的视觉验证截图。
无头 Chrome「滚动后截图」会截到空白页——这里用页面内自注入脚本先完成定位，
再让 Chrome 在虚拟时间推进后截图，绕开该问题。
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

# (输出名, 宽, 高, 注入脚本)
CASES = [
    ('nav_01_wide_top', 1440, 1000,
     "document.documentElement.style.scrollBehavior='auto';"),

    ('nav_02_wide_mid', 1440, 1000,
     "document.documentElement.style.scrollBehavior='auto';"
     "var e=document.getElementById('s11');"
     "window.scrollTo(0, e.getBoundingClientRect().top+(window.pageYOffset||0)+40);"
     "window.dispatchEvent(new Event('scroll'));"),

    ('nav_03_wide_end', 1440, 1000,
     "document.documentElement.style.scrollBehavior='auto';"
     "window.scrollTo(0, 9e7); window.dispatchEvent(new Event('scroll'));"),

    # 窄屏：抽屉默认收起，只应看到竖向「目录」把手
    ('nav_04_narrow_closed', 390, 844,
     "document.documentElement.style.scrollBehavior='auto';"),

    # 窄屏：抽屉展开
    ('nav_05_narrow_open', 390, 844,
     "document.documentElement.style.scrollBehavior='auto';"
     "document.body.classList.add('nav-open');"),
]


def main():
    html = io.open(SRC, encoding='utf-8').read()
    for name, w, h, js in CASES:
        tmp = os.path.join(OUTDIR, '_qa_shot.html')
        inject = ("<script>setTimeout(function(){try{%s}catch(e){"
                  "document.title='ERR '+e.message;}},250);</script>" % js)
        k = html.rfind('</body>')
        io.open(tmp, 'w', encoding='utf-8').write(html[:k] + inject + html[k:])
        png = os.path.join(SHOTS, name + '.png')
        cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
               '--allow-file-access-from-files', '--hide-scrollbars',
               '--window-size=%d,%d' % (w, h),
               '--virtual-time-budget=20000',
               '--screenshot=' + png,
               'file:///' + tmp.replace('\\', '/')]
        subprocess.run(cmd, capture_output=True, timeout=240)
        sz = os.path.getsize(png) // 1024 if os.path.exists(png) else 0
        print('%-22s %4dx%-5d %5d KB' % (name, w, h, sz))
        os.remove(tmp)


if __name__ == '__main__':
    main()
