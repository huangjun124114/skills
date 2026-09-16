// 无浏览器环境下验证报告 JS：桩化 DOM + Chart，检查每张图表是否被正确构建、数据是否完整
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

const els = {};
function mkEl(id) {
  return {
    id, _html: '', _rows: 0, _text: '',
    set textContent(v) { this._text = String(v); },
    get textContent() { return this._text; },
    set innerHTML(v) { this._html = String(v); },
    get innerHTML() { return this._html; },
    insertAdjacentHTML(pos, h) { this._html += h; },
    set outerHTML(v) { this._html = String(v); },
    get parentNode() { return { insertAdjacentHTML() {} }; }
  };
}
global.document = { getElementById(id) { if (!els[id]) els[id] = mkEl(id); return els[id]; } };

const defaults = { font: {}, plugins: { legend: { labels: {} }, tooltip: {} } };
const charts = [];
function Chart(el, cfg) { charts.push({ id: el && el.id, cfg }); }
Chart.defaults = defaults;
global.Chart = Chart;
global.window = { Chart: Chart };

let runtimeError = null;
try { eval(src); } catch (e) { runtimeError = e; }

console.log('运行期异常 :', runtimeError ? (runtimeError.message + '\n' + runtimeError.stack.split('\n')[1]) : '无');
console.log('图表构建数 :', charts.length, '/ 16');
console.log('缺失图表   :', ['c_year','c_yoy','c_seg','c_ship','c_month','c_season','c_cat','c_sub','c_pareto','c_region','c_state','c_cust','c_disc','c_ladder','c_lossattr','c_lossattr2'].filter(x => !charts.some(c => c.id === x)).join(', ') || '无');

let bad = 0;
charts.forEach(function (c) {
  const ds = (c.cfg.data && c.cfg.data.datasets) || [];
  const isBubble = c.cfg.type === 'bubble' || ds.some(d => d.type === 'bubble');
  const issues = [];
  if (!ds.length) issues.push('无数据集');
  ds.forEach(function (d, i) {
    const arr = d.data || [];
    if (!arr.length) { issues.push('ds' + i + ' 空数据'); return; }
    if (isBubble) return;
    const nan = arr.filter(x => x === null || x === undefined || (typeof x === 'number' && Number.isNaN(x))).length;
    const undef = arr.filter(x => x === undefined).length;
    if (nan) issues.push('ds' + i + '(' + (d.label || i) + ') 含异常值 ' + nan + '/' + arr.length);
    if (undef) issues.push('ds' + i + ' 含 undefined ' + undef);
  });
  const ix = c.cfg.options && c.cfg.options.indexAxis;
  const scaleNames = c.cfg.options && c.cfg.options.scales ? Object.keys(c.cfg.options.scales) : [];
  if (scaleNames.indexOf('indexAxis') >= 0) issues.push('indexAxis 误入 scales');
  console.log(
    '  ' + c.id.padEnd(13) +
    ' 轴=' + (ix === 'y' ? '横向' : '纵向').padEnd(4) +
    ' 数据集=' + ds.length +
    ' 点数=' + ds.map(d => (d.data || []).length).join('/') +
    (issues.length ? '   <<< ' + issues.join('; ') : '   OK')
  );
  if (issues.length) bad++;
});
console.log('异常图表数 :', bad);

const tbls = ['t_year','t_sub','t_topsku','t_botsku','t_disc','t_region','t_topcust','t_worstcust','t_worstorder'];
console.log('--- 表格填充 ---');
tbls.forEach(function (k) {
  const n = (els[k] && (els[k]._html.match(/<tr>/g) || []).length) || 0;
  console.log('  ' + k.padEnd(14) + ' 行数 ' + n + (n === 0 ? '   <<< 未填充' : ''));
});

// 精确 dump 指定表格内容（验证数值正确性）
function cells(rowHtml) {
  return (rowHtml.match(/<td[^>]*>([\s\S]*?)<\/td>/g) || [])
    .map(function (t) { return t.replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&amp;/g, '&'); });
}
function dumpTable(id, limit, label) {
  console.log('--- ' + label + ' (' + id + ') 前 ' + limit + ' 行 ---');
  const rows = ((els[id] && els[id]._html) || '').match(/<tr>[\s\S]*?<\/tr>/g) || [];
  rows.slice(0, limit).forEach(function (r) { console.log('  ' + cells(r).join(' | ')); });
}
dumpTable('t_year', 4, '年度明细');
dumpTable('t_sub', 5, '子类体检');
dumpTable('t_disc', 12, '折扣档位');
dumpTable('t_worstorder', 3, '最差订单');
dumpTable('t_topcust', 3, 'TOP客户');

console.log('--- KPI 文本抽样 ---');
['k_sales','k_profit','k_margin','k_loss','k_lossamt','f_cagr','f_y17s','f_hd','n_growth','n_p1']
  .forEach(function (k) { console.log('  ' + k.padEnd(12) + ' = ' + (els[k] ? els[k]._text : '(缺)')); });
