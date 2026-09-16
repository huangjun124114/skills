# 常见坑（全部为实测踩过）

> 每条都带**症状 → 原因 → 绕法**。遇到「代码明明对但结果不对」时先来这里对照。

---

## 1. 无头 Chrome 相关

### 1.1 「滚动后截图」会截到空白页 ← 排查最久的一个坑

**症状**：用 `url#anchor` 或注入 `window.scrollTo()` 之后截图，得到的是一张**纯白图**
（**不是深色底**，所以一眼能看出「什么都没画」）。

**原因**：`--virtual-time-budget` 下滚动后的重绘不会发生。

**绕法（两种，按场景选）**：

```python
# 绕法 A：把目标 <section> 抽出来单独成页再截图（滚动位置 = 0）
ms = list(re.finditer(r'<section id="(s\d+)">', html))
# 取 [ms[i].start(): ms[i+1].start()] → 拼成单节 HTML → 截图
# 临时页写在交付目录内，保证 images/ 相对路径可用；用完即删
```

```
绕法 B（验证 position:fixed 元素时首选）：侧栏、悬浮按钮本来就固定在视口内，
根本不需要滚动 —— 直接脚本给目标项加上激活类再截首屏即可。
```

> 顺带好处：**每节独立渲染 = 顺带验证了「这一节单独拿出来也能看」**。

### 1.2 最小窗口宽约 485px

**症状**：按 390px 截图，实际按 485px 布局再裁切，结论失真。

**绕法**：窄屏一律走 **iframe 定宽**验证（在页面里嵌 `<iframe style="width:390px">` 再截图）。
不要靠 `--window-size`。

### 1.3 `--virtual-time-budget` 下 `scroll` 事件不会自动派发

**症状**：高亮、进度条、吸顶这类滚动交互的测试**全部误判成「代码坏了」**。
`requestAnimationFrame` 也不回调。

**绕法（两侧都要改）**：

```js
// 探针侧：scrollTo 之后手动派发
window.scrollTo(0, top + 40);
window.dispatchEvent(new Event('scroll'));

// 产品侧：onScroll 别只写 rAF，必须配 setTimeout 兜底
// —— 后台标签页、嵌入环境同样会节流 rAF
```

**判定技巧**：在探针结果里顺带记录 `window.pageYOffset`。
若 y 在变而高亮没动，就是事件没派发，不是逻辑错。

### 1.4 `--dump-dom` 的换行是 `\r\n`

**症状**：「结果明明生成了，正则却说没有」。

**绕法**：结果正则别写 `@@QA@@\n`，改用 `@@QA@@([\s\S]*?)@@END@@` 或 `\r?\n`。
取回后还要顺手打印 stdout 长度 / 是否含标记，**别只打印 stderr**（那是空的，看不出问题）。

### 1.5 探针脚本在截图模式下会污染截图

**症状**：为压缩 `--dump-dom` 体积，探针跑完会把 `documentElement` 换成纯结果文本 ——
同一个脚本拿去截图，截到的就是那堆文字而不是页面。

**绕法**：加个 `DUMP` 开关（dump 模式才替换，截图模式保持原样），一个脚本两用。

### 1.6 多视口连跑要给每个视口独立 `--user-data-dir`

**症状**：共用默认 profile 时出现「1440 通过、1600/900/500 全部失败」的**假阴性**。

**绕法**：带 `--user-data-dir=<work>/profile_<tag>`，跑完删掉（体积大且可再生成）。

### 1.7 `--screenshot` 只认绝对路径

相对路径报 `Failed to write file: 系统找不到指定的路径`。

---

## 2. 布局与窄屏

### 2.1 文档级「零溢出」不等于没有裁切

`overflow-x:auto` 的容器（流程条 / 节点带 / 表格外框）把内容憋在内部滚动时，
`documentElement.scrollWidth` 不会超，探针报「零溢出」，
但最后一格贴边被切、用户得左右拖才能看全。

**必须另跑一段「容器内滚动」检测**：遍历所有 `overflowX:auto|scroll` 的元素，
比对 `scrollWidth > clientWidth + 1`。

- 布局类容器（自己设计的流程条）→ 降 `min-width`/间距，或断点处改 `display:grid` 折行
- 表格类 → 窄屏转**卡片式堆叠**：`thead{display:none}` + `tr{display:block}` +
  `td::before{content:attr(data-label)}`，`data-label` 用脚本按 thead 顺序批量注入

> **判定口诀：文档不横滚 ≠ 内容看得全。**
> 实测：9 节点流程条在 1440px 下刚好排满、末格被切，而文档级探针显示「溢出元素=0」，
> 靠抽样截图目视才发现 —— **这条只靠数字验证不出来，必须看图。**

### 2.2 溢出探针的假警报

**反面同样成立**：探针查「越界元素」时，**必须跳过 `overflowX:auto|scroll` 祖先内的元素**，
否则会把设计内的横滚表格报成布局溢出
（实测 360px 下报出 365 个「越界元素」，其实全在同一张表里）。

**判据定成两条**：`documentElement.scrollWidth <= 视口宽` **且** 容器外越界元素为 0。

### 2.3 全局 `table{min-width:520px}` 会撑破窄屏

`.tw` 容器有 `overflow:auto` 没问题，但 `.kfig` 里的裸 `<table>` 没有滚动容器。

```css
@media(max-width:760px){
  table{min-width:0;font-size:12.4px}
  .tw table{min-width:452px}
  .kfig table{min-width:0}
}
```

---

## 3. HTML 结构

### 3.1 `<div class="steps"><li>` 写成 div

浏览器能渲染但 HTML 非法，且 `.steps>li` 依赖直接子元素。**统一用 `<ol class="steps">`**。

### 3.2 中英混排下 `--dump-dom` 的输出会被 HTML 转义

探针输出前对 `&quot; &amp; &lt; &gt;` 还原。

### 3.3 标签配平自检的正常噪声

`<span>` / `<a>` / `<p>` 在 HTML5 里可省略闭合标签，配平会有少量差异。
用它**抓「差几十个」的粗错**，不要追求零差异。

---

## 4. 内容处理

### 4.1 同一张课件重复拍照

**按内容哈希去重，不要按文件名**。保留最清晰的一张，剔除理由写进脚本注释。

### 4.2 篇幅失控

详尽版容易写成流水账。控制手段：**老师原话只保留「有观点、有数字、有类比」的句子**，
客套话与现场互动过渡语一律不录。

### 4.3 顺手「统一」课件内部的矛盾

这是**最容易犯且最致命**的错误——统一掉就等于伪造。见 `01-content-restoration.md` §6。

### 4.4 遮挡文字凭猜测补

**不要猜**。用同一页的另一张留存照片补齐，并显式标注补齐方式；补不了就写「未还原」。

---

## 5. Markdown 转换

见 `05-build-and-derive.md` §4（转换器五个实现要点 + 七条必查坑），此处不重复。
最危险的一条先提醒：**`block()` 返回值类型不统一会让整篇按单字拆开，而且不报错。**

---

## 6. 本机环境（Windows + Git Bash）

| # | 坑 | 绕法 |
|---|---|---|
| 1 | **bash PATH 失效**：`dirname` / `grep` / 通配符全不可用 | 每条 Bash 命令前显式导出：<br>`export PATH="/c/Windows/System32:/c/Windows:/usr/bin:/bin"` |
| 2 | 通配符匹配失败（`*.txt` 报找不到文件） | 改用显式路径，或交给 Python 的 `glob` |
| 3 | 读长文件不要用 `head -c`（缺 coreutils） | 用 Read 工具的 offset/limit，或 Python 切片 |
| 4 | Python 用托管解释器（含 Pillow） | `C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe` |
| 5 | `crashpad` 报错日志无害 | `\| grep -v crashpad` 过滤 |
| 6 | **curl 必须加 `--ssl-no-revoke`** | 否则 `schannel: CRYPT_E_REVOCATION_OFFLINE` 直接失败 |
| 7 | **curl 不要 `-o /tmp/...`** | 报 `(23) client returned ERROR on write`，写到项目目录里 |
| 8 | **别用 `nslookup` 判 DNS** | 本机 DNS 会追加 `.com.cn` 搜索后缀，看起来「解析成功」其实是 dnspod 备案占位页。用 DoH：<br>`curl -H 'accept: application/dns-json' 'https://223.5.5.5/resolve?name=X&type=A'` 看 `Status`/`Answer` |
| 9 | 无头 Chrome 路径 | `C:/Program Files (x86)/Google/Chrome/Application/chrome.exe`（**不在 Program Files**） |

---

## 7. 环境能力边界（不要浪费轮次去试）

- **本机无头 Chrome 访问 `*.app.workbuddy.host` 可能瞬时失败**（`ERR_CONNECTION_CLOSED`），
  curl / WebFetch 同时正常 → 这是**瞬时网络抖动**，隔几分钟重跑就恢复。
  **不要因为 Chrome 失败就判定站点挂了**，也不要写进交付说明当结论。
- Chrome `--window-size` 最小值约 485px（见 §1.2）。
- `--dump-dom` 拿不到注入脚本结果时，先查换行符（见 §1.4），再查脚本是否被 CSP 拦。
