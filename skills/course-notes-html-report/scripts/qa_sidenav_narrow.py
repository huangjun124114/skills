# -*- coding: utf-8 -*-
"""
窄屏真视口验证：无头 Chrome 窗口最小约 485px，直接 --window-size=390 会按 485 布局再裁图，
结论失真。这里用 iframe 定宽模拟真实视口，测：
  1) 横向溢出（文档级 + 逐元素）
  2) 侧栏是否已收成抽屉（390px 下 aside 应不可见 / 按钮可见）
  3) 抽屉展开后的宽度与遮罩
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
OUTDIR = CFG.report_dir
SRC = os.path.join(OUTDIR, os.path.basename(CFG.sidenav_name()))
SHOTS = os.path.join(HERE, 'shots')
os.makedirs(SHOTS, exist_ok=True)

CHROME = (r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
          if os.path.exists(r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe')
          else r'C:\Program Files\Google\Chrome\Application\chrome.exe')

WIDTHS = [360, 390, 414, 480, 768, 1024]

PROBE = r"""
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;background:#222}
iframe{display:block;border:0;width:%(w)dpx;height:900px;background:#0a0e15}
</style></head><body>
<iframe id="fr" src="%(src)s"></iframe>
<script>
setTimeout(function(){
  var out = [];
  var DUMP = %(dump)s;
  try{
    var d = document.getElementById('fr').contentDocument;
    var W = %(w)d;
    var docW = d.documentElement.scrollWidth;
    out.push('VIEWPORT %(w)d');
    out.push('  document scrollWidth = ' + docW + '  -> ' + (docW <= W + 1 ? 'OK 无横向溢出' : 'FAIL 溢出 ' + (docW - W) + 'px'));
    var bad = [];
    function inScroller(el){
      // 表格等元素本来就在 overflow-x:auto 的容器里（设计如此），不算布局溢出
      for(var p = el.parentElement; p && p !== d.body; p = p.parentElement){
        var ox = getComputedStyle(p).overflowX;
        if(ox === 'auto' || ox === 'scroll') return true;
      }
      return false;
    }
    d.querySelectorAll('.wrap *').forEach(function(el){
      var r = el.getBoundingClientRect();
      if(r.width > 0 && r.right > W + 1.5 && !inScroller(el)){
        bad.push(el.tagName.toLowerCase() + '.' + (el.className||'').toString().split(' ')[0] +
                 ' right=' + Math.round(r.right));
      }
    });
    out.push('  越界元素(排除横滚容器内) ' + bad.length + (bad.length ? ': ' + bad.slice(0,8).join(' | ') : ''));
    // 侧栏 / 抽屉状态
    var side = d.querySelector('aside.side');
    var btn  = d.querySelector('.sidenav-btn');
    var cs   = side ? getComputedStyle(side) : null;
    var bs   = btn ? getComputedStyle(btn) : null;
    out.push('  aside 宽=' + (side ? Math.round(side.getBoundingClientRect().width) : '-') +
             ' transform=' + (cs ? cs.transform : '-'));
    out.push('  抽屉按钮 display=' + (bs ? bs.display : '-'));
    // 展开抽屉
    d.body.classList.add('nav-open');
    var r2 = side.getBoundingClientRect();
    out.push('  展开后 aside left=' + Math.round(r2.left) + ' 宽=' + Math.round(r2.width) +
             ' 遮罩opacity=' + getComputedStyle(d.querySelector('.sidenav-mask')).opacity);
    var mask = d.querySelector('.sidenav-mask');
    out.push('  遮罩 pointer-events=' + getComputedStyle(mask).pointerEvents);
    out.push('VERDICT ' + ((docW <= W + 1 && bad.length === 0) ? 'PASS' : 'FAIL'));
  }catch(e){ out.push('ERROR ' + e.message); out.push('VERDICT FAIL'); }
  if(DUMP){
    var pre = document.createElement('pre');
    pre.id = 'QA'; pre.textContent = '@@QA@@' + out.join('\n') + '@@END@@';
    document.documentElement.replaceChild(pre, document.body);
  }
}, 900);
</script></body></html>
"""


def run(width, dump=True):
    tmp = os.path.join(OUTDIR, '_qa_narrow.html')
    io.open(tmp, 'w', encoding='utf-8').write(
        PROBE % {'w': width, 'src': os.path.basename(CFG.sidenav_name()),
                 'dump': 'true' if dump else 'false'})
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--allow-file-access-from-files', '--hide-scrollbars',
           '--window-size=%d,960' % (width + 120),
           '--virtual-time-budget=25000',
           '--dump-dom' if dump else '--screenshot=' + os.path.join(
               SHOTS, 'nav_narrow_%d.png' % width),
           'file:///' + tmp.replace('\\', '/')]
    p = subprocess.run(cmd, capture_output=True, timeout=240)
    if dump:
        dom = p.stdout.decode('utf-8', 'replace')
        m = re.search(r'@@QA@@([\s\S]*?)@@END@@', dom)
        os.remove(tmp)
        return m.group(1).strip() if m else '(未取回)'
    os.remove(tmp)
    return ''


def main():
    allpass = True
    for w in WIDTHS:
        print(run(w))
        print()
    # 窄屏视觉（iframe 定宽，真 390px 渲染）
    run(390, dump=False)
    print('截图 shots/nav_narrow_390.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
