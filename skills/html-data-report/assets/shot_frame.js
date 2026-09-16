// 以真实手机宽度渲染报告并分段截图（iframe 规避 Chrome 500px 最小窗口限制）
const fs = require('fs');
const cp = require('child_process');
const path = require('path');

const ROOT = 'D:/Data/workspace/workdoc/混沌训练营';
const SRC = ROOT + '/发布/index.html';
const WORK = ROOT + '/中间产物/mobile';
const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';

const W = parseInt(process.argv[2] || '390', 10);
const Y = parseInt(process.argv[3] || '0', 10);
const OUT = process.argv[4] || 'mv.png';
const H = 860;

fs.mkdirSync(WORK, { recursive: true });
const target = 'file:///' + SRC.replace(/\\/g, '/');
const page = path.join(WORK, 'shot_' + W + '_' + Y + '.html');

const html = '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
  + 'html,body{margin:0;background:#0c0e12}'
  + 'iframe{width:' + W + 'px;height:' + H + 'px;border:0;display:block}'
  + '</style></head><body>'
  + '<iframe id="f" src="' + target + '"></iframe>'
  + '<scr' + 'ipt>window.addEventListener("load",function(){'
  + 'var f=document.getElementById("f");'
  + 'f.contentWindow.scrollTo(0,' + Y + ');'
  + '});</scr' + 'ipt></body></html>';

fs.writeFileSync(page, html, 'utf8');

const outPath = path.join(WORK, OUT);
cp.execFileSync(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
  '--allow-file-access-from-files', '--hide-scrollbars',
  '--user-data-dir=' + path.join(WORK, 'profile'),
  '--window-size=' + Math.max(W + 20, 600) + ',' + (H + 40),
  '--virtual-time-budget=15000',
  '--screenshot=' + outPath,
  'file:///' + page.replace(/\\/g, '/'),
], { stdio: ['ignore', 'ignore', 'ignore'] });

if (fs.existsSync(outPath)) {
  const b = fs.readFileSync(outPath);
  console.log(OUT + ' -> ' + b.readUInt32BE(16) + 'x' + b.readUInt32BE(20) + '  ' + (b.length / 1024).toFixed(0) + 'KB');
} else {
  console.log(OUT + ' FAILED');
}
