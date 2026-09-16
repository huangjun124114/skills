# -*- coding: utf-8 -*-
"""窄屏横向溢出探针（真视口版）。

无头 Chrome 的窗口最小宽度约 485px，无法直接模拟手机宽度。
这里用 iframe 承载页面：iframe 宽度即内层文档的真实视口宽度。
父页面读取内层 scrollWidth 并写入自身 title，再用 --dump-dom 取回。
"""
import io
import os
import re
import subprocess

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
OUT = CFG.report_dir
INDEX = os.path.join(OUT, 'index.html')
CH = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
WIDTHS = [360, 390, 414, 480]

PARENT = u"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#111}iframe{border:0;display:block}</style></head>
<body>
<iframe id="f" src="__INNER__" width="__W__" height="900"></iframe>
<script>
function go(){
  var f=document.getElementById('f');
  try{
    var d=f.contentDocument, de=d.documentElement;
    document.title='NP|SW='+de.scrollWidth+'|CW='+de.clientWidth
                   +'|BH='+d.body.scrollHeight;
  }catch(e){ document.title='NP|ERR='+e.message; }
}
setTimeout(function(){ go(); }, 2500);
</script>
</body></html>
"""


def main():
    tmps = []
    inner_name = '_np_inner.html'
    try:
        html = io.open(INDEX, encoding='utf-8').read()
        with io.open(os.path.join(OUT, inner_name), 'w', encoding='utf-8') as f:
            f.write(html)
        tmps.append(os.path.join(OUT, inner_name))
        for w in WIDTHS:
            tmp = os.path.join(OUT, '_np_%d.html' % w)
            with io.open(tmp, 'w', encoding='utf-8') as f:
                f.write(PARENT.replace('__INNER__', inner_name).replace('__W__', str(w)))
            tmps.append(tmp)
            cmd = [CH, '--headless=new', '--disable-gpu', '--virtual-time-budget=12000',
                   '--window-size=%d,900' % max(w + 40, 520), '--dump-dom', '--no-sandbox',
                   '--allow-file-access-from-files', 'file:///' + tmp.replace('\\', '/')]
            r = subprocess.run(cmd, capture_output=True, timeout=200)
            dom = r.stdout.decode('utf-8', 'ignore')
            m = re.search(r'<title>NP\|([^<]*)</title>', dom)
            if not m:
                print('  %4dpx  未取到探针结果' % w)
                continue
            s = m.group(1)
            if s.startswith('ERR'):
                print('  %4dpx  %s' % (w, s))
                continue
            sw = int(re.search(r'SW=(\d+)', s).group(1))
            cw = int(re.search(r'CW=(\d+)', s).group(1))
            bh = int(re.search(r'BH=(\d+)', s).group(1))
            print('  %4dpx  scrollWidth=%-5d clientWidth=%-5d 页面高=%-7d %s'
                  % (w, sw, cw, bh, 'OK' if sw <= cw + 1 else '★ 横向溢出 %dpx' % (sw - cw)))
    finally:
        for t in tmps:
            try:
                os.remove(t)
            except OSError:
                pass


if __name__ == '__main__':
    main()
