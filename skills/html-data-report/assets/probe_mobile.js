// 真机宽度探针：在窗口内嵌 iframe，让媒体查询按目标宽度生效
const fs = require('fs');
const cp = require('child_process');
const path = require('path');

const ROOT = 'D:/Data/workspace/workdoc/混沌训练营';
const SRC = process.argv[3] || path.join(ROOT, '发布/index.html');
const WIDTH = parseInt(process.argv[2] || '390', 10);
const WORK = path.join(ROOT, '中间产物/mobile');
const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';

fs.mkdirSync(WORK, { recursive: true });
const page = path.join(WORK, 'frame_' + WIDTH + '.html');
const target = 'file:///' + SRC.replace(/\\/g, '/');

const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;background:#222}
iframe{width:${WIDTH}px;height:900px;border:0;display:block}
</style></head><body>
<iframe id="f" src="${target}"></iframe>
<script>
window.addEventListener('load', function(){
  setTimeout(function(){
    var d = document.getElementById('f').contentDocument;
    var w = d.documentElement;
    var vw = d.defaultView.innerWidth;
    var out = ['viewport=' + vw, 'scrollWidth=' + w.scrollWidth, 'OVERFLOW=' + (w.scrollWidth - vw)];
    var bad = [];
    d.querySelectorAll('body *').forEach(function(e){
      var r = e.getBoundingClientRect();
      if (r.right > vw + 1 && r.width > 0) {
        var c = (typeof e.className === 'string' && e.className) ? e.className : 'no-class';
        bad.push(e.tagName + ' [' + c + '] right=' + Math.round(r.right) + ' w=' + Math.round(r.width));
      }
    });
    out.push('OVF_COUNT=' + bad.length);
    out = out.concat(bad.slice(0, 24));
    var pre = document.createElement('pre');
    pre.id = 'probe';
    pre.textContent = out.join(String.fromCharCode(10));
    document.body.appendChild(pre);
  }, 1200);
});
</scr` + `ipt></body></html>`;

fs.writeFileSync(page, html, 'utf8');

const dom = cp.execFileSync(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
  '--allow-file-access-from-files',
  '--user-data-dir=' + path.join(WORK, 'profile'),
  '--window-size=' + Math.max(WIDTH, 600) + ',1000',
  '--virtual-time-budget=20000',
  '--dump-dom',
  'file:///' + page.replace(/\\/g, '/'),
], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });

fs.writeFileSync(path.join(WORK, 'framedom_' + WIDTH + '.txt'), dom, 'utf8');
const m = dom.match(/<pre id="?probe"?>([\s\S]*?)<\/pre>/);
console.log('=== 真实视口 ' + WIDTH + 'px ===');
console.log(m ? m[1] : 'PROBE_FAIL (len=' + dom.length + ')');
