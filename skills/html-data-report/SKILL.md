---
name: html-data-report
description: >
  构建并验证自包含的深色主题 HTML 数据分析报告（内联 Chart.js、离线可用），
  并在没有 Playwright/Puppeteer 的环境下用系统 Chrome 无头渲染做视觉验证，
  含窄屏/手机端横向溢出检测（iframe 真实视口）。
  触发词：HTML 报告、数据分析报告、经营分析、可视化报告、图表没显示、图表显示不全、
  报告渲染异常、手机端显示不全、窄屏溢出、响应式、发布分享报告、
  verify html report、inline chart.js report、mobile overflow。
agent_created: true
---

# HTML 数据分析报告：构建 + 验证

用于「把数据变成一份可直接翻阅的 HTML 报告」，并且**必须验证渲染结果**。
本技能的核心价值在第 2 部分——多数报告"看起来生成了"但图表其实没渲染。

---

## 0. 环境前置（Windows / WorkBuddy sandbox）

**这个环境的 bash 没有 coreutils**：`ls` / `mkdir` / `head` / `tail` / `wc` / `cat` 全部 `command not found`。
`PowerShell` 工具可能无回显（本文环境实测无输出）。

→ **所有文件操作走 node 或 Python**：
```bash
node.exe -e "require('fs').mkdirSync('中间产物',{recursive:true}); console.log('ok')"
python.exe -c "import os; os.makedirs('中间产物/shot',exist_ok=True)"
```
- 托管 node：`C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-3/node.exe`
- 托管 python：`C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`

**不要试图装 Playwright/Puppeteer**：`npm install` 会触发 `wsl.exe` 被安全策略拦截。
系统已装 Chrome/Edge，直接用：
`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`

---

## 1. 构建报告

### 1.1 结构约定
- 生成脚本放 `中间产物/build_report.py`，计算脚本放 `中间产物/analyze.py`
- 数据经 `metrics.json` 中转：analyze.py → metrics.json → build_report.py → HTML
- 报告 = 纯 HTML 模板字符串，用 `.replace("__DATA__", json.dumps(...))` 注入数据
  （**不要用 f-string**，CSS 的花括号会炸）
- 交付文件名带日期：`xxx报告_MMDD.html`

### 1.2 Chart.js 内联（离线可用）
先下载到本地，再内联，缺失时回退 CDN：
```python
_cj = os.path.join(BASE, "中间产物", "chart.umd.min.js")
if os.path.exists(_cj):
    _src = open(_cj, encoding="utf-8").read().replace("</script>", "<\\/script>")
    _tag = "<" + "script>" + _src + "</" + "script>"
else:
    _tag = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'
html = html.replace("__CHARTJS__", _tag)
```
```bash
node.exe -e "fetch('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js').then(r=>r.text()).then(t=>require('fs').writeFileSync('中间产物/chart.umd.min.js',t))"
```
内联后约 +200KB，换来断网也能看。

### 1.3 图表挂载器（必须有）
单个图表出错不得拖垮其余图表；Chart.js 加载失败要有可见提示：
```js
function mk(id, cfg){
  var el = document.getElementById(id);
  if(!el) return;
  if(!window.Chart){ el.outerHTML='<div class="cerr">图表库未加载，请联网后刷新</div>'; return; }
  try{ new Chart(el, cfg); }
  catch(e){ console.error('[chart] '+id, e); el.outerHTML='<div class="cerr">图表渲染失败：'+id+'</div>'; }
}
```
所有图表一律 `mk('c_xxx', {...})`，不要裸写 `new Chart(document.getElementById(...))`。

### 1.4 容器高度（"显示不全"的头号原因）
Chart.js 用 `maintainAspectRatio:false` 时高度完全由父容器决定，父容器必须给固定高度：
```css
.cv{position:relative;height:290px}
.cv.sm{height:240px}
.cv.lg{height:350px}
.cv.xl{height:480px}     /* 长标签横向图：状态名、子类名 */
canvas{display:block}
```
横向条形图经验公式：`高度 ≈ 行数 × 28px + 80px`。

### 1.5 配套 XLSX 数据包（可选，但审阅者很吃这一套）

HTML 给人看，XLSX 给人算。两者**必须从同一个 `metrics.json` 取数**，
绝不在 XLSX 脚本里重抄一遍数字——否则就是第 5 层要抓的「口径漂移」的翻版。

托管 Python **不自带 openpyxl**，先建隔离 venv 装（不要装到全局）：
```bash
PY="C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe"
"$PY" -m venv "C:/Users/Administrator/.workbuddy/binaries/python/envs/default"
"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" -m pip install openpyxl
```
之后统一用 venv 里的解释器跑 xlsx 脚本：
```bash
"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" 中间产物/build_xlsx.py
```

**两个必踩的坑**：

1. **`%` 字面量**：`"…× 50% × 80 元…" % val` 会 `ValueError: unsupported format character`。
   字面百分号写 `%%`，或改用 f-string / `.format()`。
2. **`PatternFill` 与 hex 字符串不能混用**：若把 `LFILL = PatternFill(...)` 当颜色常量，
   又写 `PatternFill("solid", fgColor=LFILL)` 就会
   `TypeError: fgColor should be <class 'Color'> but value is <class 'PatternFill'>`。
   统一定义一个 `_mkfill(f)` 兼容两种入参：
   ```python
   def _mkfill(f):
       if f is None: return None
       return f if isinstance(f, PatternFill) else PatternFill("solid", fgColor=f)
   ```

**自检**：生成后回读一遍并与模型对账（不要只看「保存成功」）：
```bash
python.exe -c "
import json; from openpyxl import load_workbook
wb=load_workbook('输出/xxx_数据包_MMDD.xlsx')
print(wb.sheetnames)
for n in wb.sheetnames: print(n, wb[n].dimensions)
"
```

---

## 2. 验证（关键步骤，不要跳过）

五层递进，每层都能独立发现不同类别的问题。
第 1/2 层无需浏览器、秒级完成，先跑；第 3/4 层要 Chrome；第 5 层只在「脚本算数」型报告才需要，但**最容易被漏**。

### 第 1 层：语法检查（最快，抓致命错误）
语法错误会让**整段脚本不执行**，表现为所有图表空白——但页面文字照常显示，极易误判为"部分图表问题"。
```bash
python.exe -c "
import re
s=open('报告.html',encoding='utf-8').read()
b=re.findall(r'<script>(.*?)</script>', s, re.S)
open('中间产物/_check.js','w',encoding='utf-8').write(b[-1])
print('blocks:',len(b))
"
node.exe --check 中间产物/_check.js && echo SYNTAX_OK
```
内联 Chart.js 后会有 2 个 script 块，取 `[-1]`（报告的）。

### 第 2 层：DOM 桩功能测试（无需浏览器，抓运行时错误 + 数据缺失）
用纯 node 桩化 `document` / `Chart`，让整个脚本跑一遍，检查：
- 是否有运行期异常
- 是否 16 张图全部 `mk()` 成功
- 每个 dataset 是否含 `NaN` / `undefined` / 空数组
- `options.scales` 里是否混入了 `indexAxis`（典型配置错误）
- 所有 `<tbody>` 是否被填充
- 表格单元格的**真实文本值**（比看截图准确得多）

脚本见 `assets/verify_js.js`。用法：
```bash
node.exe assets/verify_js.js 中间产物/_check.js
```

### 第 3 层：无头 Chrome 截图（抓纯视觉问题）
**整页截图**（窗口给足高度）：
```bash
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-sandbox \
  --user-data-dir="<workspace>/中间产物/shot/profile" \
  --screenshot="<abs>/full.png" --window-size=1500,6000 \
  --virtual-time-budget=15000 "file:///<abs>/report.html"
```

**分带截图**（页面很长时，用负 translateY 切带，避免只看到顶部）：
在 `</head>` 前注入 `<style>.wrap{transform:translateY(-2350px)}</style>`，
每带 `--window-size=1500,2350`，偏移取 0 / 2350 / 4700 / 7050 / 9400。

**单图隔离放大**（验证某张图是否被截断，最有用）：
在 `</body>` 前注入：
```js
document.querySelectorAll(".wrap > section, header, footer, .hr").forEach(function(s){
  if(!s.querySelector("#c_target")) s.style.display="none"; });
document.querySelectorAll(".box").forEach(function(b){
  if(!b.querySelector("#c_target")) b.style.display="none"; });
document.querySelector(".wrap").style.paddingTop="8px";
```
窗口 `1400x780`，`--virtual-time-budget=8000`。目标图会顶到页面最上方且保持原尺寸。
> 注意：只隐藏 `section` 而漏掉 `.hr`，会残留大量空白把图表顶到屏幕外。

**读图技巧**：1500px 宽的整页截图被模型缩放后**数字极易看错**（如 `-$32,412` 看成 `$12,412`）。
关键数值一律用第 2 层 dump 文本确认，不要靠读截图。

### 第 4 层：窄屏 / 手机端验证（报告要外发分享时必做）

**Chrome 无头窗口有 500px 最小值**：`--window-size=390,...` 会被钳到 500px 布局，
但截图画布仍是 390px 宽——于是你会截到一张**右侧被切掉的假截图**，误以为"手机端坏了"。
**必须用 iframe 造真实视口**（媒体查询按 iframe 宽度生效）：

```bash
node.exe assets/probe_mobile.js 390      # 量 390px 视口的真实溢出
node.exe assets/probe_mobile.js 768
node.exe assets/probe_mobile.js 1440
```
输出判读：
```
viewport=390  scrollWidth=375  OVERFLOW=-15   ← 合格（负值=有余量）
OVF_COUNT=655                                 ← ⚠️ 多数情况正常，见下
```
`documentElement.scrollWidth > innerWidth` 才是**页面横向溢出**，手机上看要左右拖屏。

> **`OVF_COUNT` 不是判据，`OVERFLOW` 才是。**
> 宽表格被 `overflow:auto` 容器包住时，表内 `td/th` 的 `getBoundingClientRect().right` 必然超出视口——
> 一个 30 张表的报告在 390px 下 `OVF_COUNT` 可能高达 600+，但 `OVERFLOW` 仍是 -15（合格）。
> 判读顺序：先看 `OVERFLOW`（必须 <0）；若 <0 则 `OVF_COUNT` 只用于**定位**可疑元素，
> 确认命中的都是表格/`pre` 后代即可放行；只有当 `OVERFLOW>0` 时才回头查 `OVF_COUNT` 里的非表格元素。

> **⚠️ 但 `OVERFLOW<0` 是必要不充分条件——还必须单独查「容器内滚动」。**
> `overflow-x:auto` 的容器把内容憋在内部滚动时，文档 `OVERFLOW` 依然 <0，
> 探针会报"零溢出"，可用户得左右拖才能看全，观感上等于被裁切。
> 实例：一个 9 节点的流程条在 1440px 下刚好排满，最后一格贴边被切，
> 而文档级探针显示 `溢出元素=0`——**是截图目视才发现的问题。**
>
> 补一段检测即可（与溢出检测并列跑）：
> ```js
> var sc = [];
> document.querySelectorAll('*').forEach(function(el){
>   var cs = getComputedStyle(el);
>   if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll')
>      && el.scrollWidth > el.clientWidth + 1){
>     sc.push(el.tagName.toLowerCase() + '.' + (el.className || '').split(' ')[0]
>             + ' (' + el.scrollWidth + '>' + el.clientWidth + ')');
>   }
> });
> ```
> 命中后分两类处理：
> - **可放行**：真正的宽表格（列多且不可避免）——横向滚动是通行做法
> - **应修**：布局类容器（流程条 / 节点带 / 卡片横排）——这是自己设计的，必须响应式化
>
> 两种修法：
> 1. **布局类**：降 `min-width` 与间距，或到断点改 `display:grid` 折行
>    （横排折成 5 列 2 行；折成单列时用 `.pnode:not(:last-child)::after{content:"▼"}`
>    在节点下方补方向感，别丢顺序暗示）
> 2. **表格类**：<760px 转**卡片式堆叠**——`thead{display:none}` + `tr{display:block}` +
>    `td::before{content:attr(data-label)}`，并给每个 `td` 补 `data-label="列名"`。
>    label 用脚本按 `thead` 顺序批量注入（`re.sub` 逐个 `td` 计数取模），**不要手写**——
>    一个 8×4 的表就是 32 处，手写必漏。
>    改完手机上零滑动即可读完，体验比横向滚动好一个量级。

**截图**用 `assets/shot_frame.js <宽度> <scrollY> <输出名>`（同款 iframe 方案）。
> 注意 `shot_frame.js` 把 `SRC` 硬编码为 `发布/index.html`。报告还在 `输出/` 阶段时，
> 复制一份到 `发布/index.html`，或照抄它新建一个把 `SRC` 指向当前报告的本地脚本。

**更省事的定位截法（优先用这个，不必算像素偏移）**：给 iframe 的 `src` 直接加锚点，
浏览器会把锚点滚到 iframe 顶部，父页面固定尺寸截图即可命中目标区段：
```html
<iframe src="file:///<abs>/report.html#s9" style="width:1440px;height:1180px;border:0"></iframe>
```
配合 `--window-size=1440,1180 --virtual-time-budget=6000 --screenshot=x.png`。
一次循环把各 `#sN` 逐张截完，比 translateY 分带省事且不会错位。
锚点命不中时（元素无 id）改用父页面脚本滚动：
```js
fr.contentWindow.scrollTo(0, fr.contentWindow.scrollY
  + fr.contentDocument.getElementById('c_disc').getBoundingClientRect().top - 150);
```
（同源前提：加 `--allow-file-access-from-files`，延迟 ~2.2s 等图表画完再滚。）

> **口诀：≥500px 用 `--window-size` 直接截；<500px 必须走 iframe 定宽；要截某一段就加锚点。**

---

### 第 5 层：口径一致性审计（**模型驱动的报告必做**）

只要报告是「脚本算数 → metrics.json → 模板注入」的结构，就一定会出现这个缺陷：
**模型在迭代中改了参数，但模板里硬编码的那句结论没跟着改。**
它不报错、截图也好看，却是最致命的一类错误——报告的自我表述与自己的模型互相矛盾。

真实案例：模型里 `rate` 已从 112 调到 69.5、分母从 1,050 调到 1,069 万间，
但模板仍写着「分母 1,050 万间 × 45% 渗透 × 加权 112 元/间/年」；
敏感性网格的 4 档取值甚至**不包含基准情形**（基准 82%，网格最大 75%），
导致「基准格」在图上根本不存在。

**做法**：把模板里每一个模型派生数字都当成待审对象，逐一与 metrics.json 对照。

```bash
python.exe -c "
import re,json
M=json.load(open('中间产物/metrics.json',encoding='utf-8'))
s=open('中间产物/report_template.html',encoding='utf-8').read()
# 把已知的正确值/可能过期的旧值都列成候选，扫全文
for pat in ['112','1,050','45%','17.9','2.7','9.8']:
    for m in re.finditer(re.escape(pat), s):
        ln=s.count(chr(10),0,m.start())+1
        print('[%s] L%d: %s'%(pat,ln,s.split(chr(10))[ln-1].strip()[:180]))
"
```

必查项（每项都要能与 JSON 对上一个精确值）：
1. 分母、渗透率/转化率、单价 → 与 `gross_all` / `pay_all` / `blended_rate` 对账
2. 图表标题里的区间与倍数 → 必须**由模型生成**（如 `sens['lo']`/`sens['hi']`），不要手写
3. 敏感性/情景网格 → 基准档必须落在网格内，且网格值必须覆盖基准
4. 结论句里的「增长由 X 驱动」→ 用模型真算一遍各因子 CAGR，别凭直觉写
5. 附录表格里引用的计数（N 条来源 / N 条假设）→ 用 `len()` 渲染，不要写死

> **根治办法**：凡能算的都别写字面量。区间、倍数、CAGR、计数一律
> `"...%s" % f(model)`，让模板无法与模型脱节。
> 这个审计做完，往往还能顺手发现「图表标签数与数据集点数不等」这类第 2 层才能抓的问题。

---

## 3. 踩过的坑（照抄避雷）

| 症状 | 根因 | 修法 |
|---|---|---|
| **所有**图表空白，文字正常 | JS 多一个 `}` → 整段语法错 | 第 1 层 `node --check` |
| 横向条形图变纵向、标签挤成一团 | `indexAxis:'y'` 写进了 `scales` 对象 | 必须是 `options` 顶层：`base({...scales}, {indexAxis:'y'})` |
| 长标签图（州名/子类）被压扁 | 容器高度不足 | 用 `.cv.xl`（480px+） |
| 颜色分档全落同一档 | **百分比 vs 小数混用**：`margin` 是小数（0.4424），却写 `margin < 10` → 恒真 | 比阈值用小数：`margin < 0.10` |
| 图表被截断在视口外 | 用了负 `margin-top` 而非 `transform:translateY` | 用 `transform` |
| `--dump-dom` 抓不到异步结果 | dump 在 load 时执行，早于 `img.onload` / `setTimeout` | 探针逻辑直接写进 `load` 回调，**不要包 setTimeout**；或改用截图 |
| **窄屏整页横向溢出**（手机要左右拖屏） | 网格项默认 `min-width:auto`，被宽表格/长文本顶开栅格列，连锁拉宽全页 | 加 `.grid>*{min-width:0;min-height:0}` |
| 窄屏仍是多列、卡片挤成一团 | 断点只做到"6 列→2 列"，没有窄屏折成单列的规则 | 补 `@media(max-width:760px){.g6,.g4,.g3,.g23,.g2{grid-template-columns:1fr}}` |
| 窄屏截图右侧被切、文字截断 | 误判：Chrome 无头窗口最小 500px，390px 截图是**假象** | 用 iframe 探针（第 4 层）确认真实 `scrollWidth` |
| **模板文字与模型数字互相矛盾**（不报错、截图也正常） | 模型参数改了，模板里硬编码的结论句/区间没跟着改 | 第 5 层口径审计；派生数字一律由模型渲染，不写字面量 |
| 敏感性/情景图里找不到「基准情形」 | 网格档位凭感觉定，没把基准值包进区间 | 网格必须覆盖并高亮基准档（如基准 82% → 档位含 0.82） |
| `openpyxl` 生成时报格式错 / `TypeError: fgColor` | `%` 字面量未转义成 `%%`；`fgColor` 传了 `PatternFill` 对象而非 hex 串 | 见 §1.5 的两个坑 |

**小数/百分比混用是最高频的静默 bug**：它不报错，只是渲染结果"看起来也对"。
凡是 `margin` / `rate` / `share` / `ratio` 字段做**阈值比较**时，先确认单位。

---

## 4. 交付前检查清单

- [ ] `node --check` 通过
- [ ] 16/16（或全部）图表 `mk()` 成功，无 `NaN`
- [ ] 每个 dataset 点数 = 预期分类数
- [ ] 所有表格有数据，抽样数值与源数据一致
- [ ] 抽查 2~3 张图的实际截图（尤其横向图与双轴图）
- [ ] **窄屏无横向溢出**：390 / 768px 下 `OVERFLOW<0`（第 4 层）；`OVF_COUNT` 偏大但命中的都是表格则可放行
- [ ] **口径一致性**（模型驱动报告必做）：模板里每个模型派生数字都能与 `metrics.json` 对上；敏感性网格含基准档；区间/倍数/CAGR/计数由模型生成而非手写（第 5 层）
- [ ] 配套 XLSX（若有）与 HTML **同源**取值，且生成后回读对账通过
- [ ] 外部依赖清零：`src="https?:` 计数为 0（Chart.js 已内联）
- [ ] 原始输入文件未被修改（只读）
- [ ] 中间产物放 `中间产物/`，最终交付物放根目录且**文件名带日期**
- [ ] 删除临时物：Chrome `profile/` 目录（单个可达 18MB）、分带 HTML、探针 HTML、`_check.js`
- [ ] 保留 `chart.umd.min.js`（重建报告需要）

### 4.1 要发布到线上分享时

把报告**单独复制到一个干净目录**再发布，不要把工作区整个上传：
```bash
node.exe -e "const fs=require('fs');fs.mkdirSync('发布',{recursive:true});fs.copyFileSync('报告_MMDD.html','发布/index.html')"
```
否则 `原始输入/` 的原始数据和 `中间产物/` 里的脚本会一并推到公网。发布用 `发布为应用` 技能。
