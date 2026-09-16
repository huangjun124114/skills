# -*- coding: utf-8 -*-
"""横向溢出探针：在多个视口宽度下测量 documentElement.scrollWidth，
并定位真正撑破视口的元素（跳过 .tw / pre 等自带滚动容器的内部元素）。
用 --dump-dom 读回结果。
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
WIDTHS = [1440, 1024, 768, 480, 390, 360]

PROBE = u"""
<script>
window.addEventListener('load', function(){
  setTimeout(function(){
    var de = document.documentElement, W = de.clientWidth, bad = [];
    function scrollableAncestor(el){
      for (var p = el.parentElement; p; p = p.parentElement){
        var ov = getComputedStyle(p).overflowX;
        if (ov === 'auto' || ov === 'scroll' || ov === 'hidden') return true;
      }
      return false;
    }
    Array.prototype.forEach.call(document.querySelectorAll('body *'), function(el){
      var r = el.getBoundingClientRect();
      if (r.width <= 1 || r.height <= 1) return;
      if (r.right <= W + 1 && r.left >= -1) return;
      if (scrollableAncestor(el)) return;
      var cls = (typeof el.className === 'string' ? el.className : '').trim().split(/\\s+/)[0];
      bad.push(el.tagName.toLowerCase() + (cls ? '.' + cls : '')
               + '[' + Math.round(r.left) + ',' + Math.round(r.right) + ']');
    });
    document.title = 'PROBE|SW=' + de.scrollWidth + '|CW=' + W
                     + '|N=' + bad.length + '|' + bad.slice(0, 10).join(' ');
  }, 1200);
});
</script>
"""


def main():
    html = io.open(INDEX, encoding='utf-8').read()
    tmps = []
    try:
        for w in WIDTHS:
            tmp = os.path.join(OUT, '_probe_%d.html' % w)
            with io.open(tmp, 'w', encoding='utf-8') as f:
                f.write(html.replace('</body>', PROBE + '</body>'))
            tmps.append(tmp)
            cmd = [CH, '--headless=new', '--disable-gpu', '--virtual-time-budget=9000',
                   '--window-size=%d,900' % w, '--dump-dom', '--no-sandbox',
                   '--allow-file-access-from-files', 'file:///' + tmp.replace('\\', '/')]
            r = subprocess.run(cmd, capture_output=True, timeout=200)
            dom = r.stdout.decode('utf-8', 'ignore')
            m = re.search(r'<title>PROBE\|([^<]*)</title>', dom)
            if not m:
                print('  %4dpx  未取到探针结果' % w)
                continue
            parts = m.group(1).split('|')
            sw = int(parts[0].split('=')[1])
            cw = int(parts[1].split('=')[1])
            n = int(parts[2].split('=')[1])
            detail = parts[3] if len(parts) > 3 else ''
            flag = 'OK  ' if sw <= cw + 1 else '溢出'
            print('  %4dpx  scrollWidth=%-6d clientWidth=%-6d 越界元素=%-3d %s %s'
                  % (w, sw, cw, n, flag, detail[:150]))
    finally:
        for t in tmps:
            try:
                os.remove(t)
            except OSError:
                pass


if __name__ == '__main__':
    main()
