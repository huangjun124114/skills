# -*- coding: utf-8 -*-
"""
scroll spy 走查：逐节滚动，断言「当前节」与「高亮项」是否一致。

做法：把侧栏版复制成临时文件，注入一段自测脚本（在真实浏览器里同步滚动 + 派发 scroll），
测完把 document 替换成纯结果，再用 --dump-dom 把结果取回来。
不用虚拟时间猜——跑的是页面自己的 scroll spy 代码。
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
TMP = os.path.join(OUTDIR, '_qa_nav_test.html')

CHROME = (r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
          if os.path.exists(r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe')
          else r'C:\Program Files\Google\Chrome\Application\chrome.exe')

TEST_JS = r"""
<script>
(function(){
  'use strict';
  function finish(lines){
    var pre = document.createElement('pre');
    pre.id = 'QA';
    pre.textContent = '@@QA@@\n' + lines.join('\n') + '\n@@END@@';
    var b = document.createElement('body');
    b.appendChild(pre);
    document.documentElement.replaceChild(b, document.body);
    document.documentElement.removeAttribute('class');
    // 清掉 style/script，保证 dump-dom 体积可控
    document.documentElement.querySelectorAll('script,style').forEach(function(n){ n.remove(); });
  }
  function run(){
    var d = document;
    d.documentElement.style.scrollBehavior = 'auto';   // 关掉平滑，保证同步定位
    var anchors = [].slice.call(d.querySelectorAll('a.snav'));
    var ids = anchors.map(function(a){ return a.getAttribute('href').slice(1); });
    var out = [];
    if(!anchors.length){ finish(['FAIL 侧栏无导航项']); return; }
    if(d.querySelectorAll('a.snav.on').length > 1){ out.push('WARN 初始有多项高亮'); }

    var i = 0, hits = 0;
    function step(){
      if(i >= ids.length){
        out.push('');
        out.push('RESULT ' + hits + '/' + ids.length + ' 命中');
        out.push('VERDICT ' + (hits === ids.length ? 'PASS' : 'FAIL'));
        finish(out);
        return;
      }
      var id = ids[i];
      var el = d.getElementById(id);
      if(!el){ out.push('MISS ' + id + ' -> 无此 section'); i++; setTimeout(step, 20); return; }
      var top = el.getBoundingClientRect().top + (window.pageYOffset || 0);
      window.scrollTo(0, top + 40);
      window.dispatchEvent(new Event('scroll'));
      setTimeout(function(){
        var on = d.querySelector('a.snav.on');
        var got = on ? on.getAttribute('href').slice(1) : '(none)';
        var multi = d.querySelectorAll('a.snav.on').length;
        var ok = (got === id) && (multi === 1);
        if(ok) hits++;
        out.push((ok ? 'HIT  ' : 'MISS ') + id.padEnd(4) + ' 期望=' + id.padEnd(4) +
                 ' 实际=' + got.padEnd(5) + ' 高亮数=' + multi);
        i++;
        step();
      }, 150);
    }
    step();
  }
  setTimeout(run, 400);
})();
</script>
"""


def main():
    html = io.open(SRC, encoding='utf-8').read()
    k = html.rfind('</body>')
    io.open(TMP, 'w', encoding='utf-8').write(html[:k] + TEST_JS + html[k:])

    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--allow-file-access-from-files', '--hide-scrollbars',
           '--window-size=1440,900',
           '--virtual-time-budget=60000',
           '--dump-dom',
           'file:///' + TMP.replace('\\', '/')]
    p = subprocess.run(cmd, capture_output=True, timeout=300)
    dom = p.stdout.decode('utf-8', 'replace')

    m = re.search(r'@@QA@@([\s\S]*?)@@END@@', dom)
    if not m:
        print('未取回结果。')
        print('  stdout 长度 : %d' % len(dom))
        print('  含 @@ 次数 : %d' % dom.count('@@'))
        tail = p.stderr.decode('utf-8', 'replace')[-1500:]
        print('  stderr 尾部 : %s' % (tail.strip() or '(空)'))
        if os.path.exists(TMP):
            io.open(os.path.join(HERE, 'shots', '_qa_dom_debug.txt'), 'w',
                    encoding='utf-8').write(dom[:4000])
            print('  已存 DOM 头部到 shots/_qa_dom_debug.txt')
        os.remove(TMP)
        return 1

    lines = [l.rstrip() for l in m.group(1).strip().split('\n')]
    for ln in lines:
        print(ln)

    # 留档
    os.makedirs(os.path.join(HERE, 'shots'), exist_ok=True)
    io.open(os.path.join(HERE, 'shots', 'qa_nav_spy_result.txt'), 'w',
            encoding='utf-8').write('\n'.join(lines) + '\n')

    verdict_pass = any(l.startswith('VERDICT PASS') for l in lines)
    os.remove(TMP)
    print('\n结果已留档 shots/qa_nav_spy_result.txt；临时文件已清理：%s'
          % (not os.path.exists(TMP)))
    return 0 if verdict_pass else 1


if __name__ == '__main__':
    sys.exit(main())
