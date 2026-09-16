---
name: library-page-archive
description: >
  把一份已托管的 WorkBuddy 资料库 HTML 页面（kind=web，分享链接形如
  www.workbuddy.link/p/<nodeId> 或 workbuddy.cn/space/d/<nodeId>）**完整复刻到本地**，
  并派生一份高保真 Markdown 归档版。
  适用：用户给一个 space / workbuddy.link 分享链接，说"整理 / 复刻 / 归档 / 存下来 /
  做成 markdown / 这份内容我要留一份"。
  做法：node-info 判 kind → list_page_artifacts 取产物地址 → curl 拉完整单文件 →
  字节级落盘（sha1 比对证明零改动）→ 机械转换为 Markdown（章节编号 / 框架条目 /
  提示词代码块 / 表格的保真转换，含四个必避的转换坑）→ 离线与交互双重质检。
  与资料库自带的 §4.5 clone-flow 区别：clone-flow 是"在资料库新建一份等价副本"，
  本技能是"把产物拉到本地并存档"，不走 databaseId 重映射。
  触发词：复刻页面、归档资料库页面、保存分享链接、space 链接、workbuddy.link、
  整理这份纪要、页面转 markdown、把这份文档存下来、library page archive、
  archive shared page、page to markdown。
agent_created: true
---

# 资料库已托管页面：本地复刻 + Markdown 归档

把一份**已托管的资料库 HTML 页面**完整搬到本地，既保留可交互的原件，
又产出一份能检索、能二次引用的 Markdown 归档版。

---

## 0. 先确认这是不是本技能的场景

| 用户意图 | 走哪条路 |
|---|---|
| "复刻 / 归档 / 存下来 / 转 markdown"一份**已托管的 page 链接** | **本技能** |
| "做同款 / 克隆一份到我的资料库"（要新建等价副本） | 资料库 skill 的 §4.5 `clone-flow.md`（需 databaseId 重映射） |
| 改已托管页面的内容 | 资料库 skill 的 §4 `edit-flow.md`（增量事务） |
| 把本地素材做成新的在线 page | 资料库 skill 的 §8 `beautify-flow.md` |

> **判定要点**：本技能**只读不写**远端——从远端拉产物到本地。任何"要新建/要改远端"的诉求都不在本技能。

---

## 1. 链路（四步，最小实现）

### 第 1 步 · 归一化 nodeId

链接形态 → nodeId：

| 链接形态 | nodeId |
|---|---|
| `https://www.workbuddy.link/p/1uHlxkwWT6MilnLA3suld9` | `/p/` 后那段 |
| `https://www.workbuddy.cn/space/d/1uHlxkwWT6MilnLA3suld9` | `/d/` 后那段 |
| 裸 nodeId | 原值 |

### 第 2 步 · 判 kind（决定能不能走本技能）

```bash
# mode=client 需先换票：ToolSearch → DeferExecuteTool(connect_open_platform, skill_id=library)
printf '%s\n%s' "<token>" '{"nodeId":"<nodeId>"}' \
  | python3 "<library_skill_dir>/space_api.py" space.workspace.node-info --token-stdin --stdin
```

- `kind=web` / `kind=page` → ✅ 本技能
- `kind=doc` → 是文档，走 library `doc/entry.md` 读正文
- `kind=database` → 是表格，走 library `database/entry.md`

### 第 3 步 · 取产物地址并下载

```bash
printf '%s' "<token>" | python3 "<library_skill_dir>/page/list_page_artifacts.py" \
  --token-stdin --node-id "<nodeId>"
# 输出 KS_IMPORT_OK 风格 JSON：data.url（产物根地址）+ data.artifacts[].path

# 拼 {data.url}{path} 直接 curl 拉取，即得完整单文件
curl -s --ssl-no-revoke -L "{data.url}{path}" -o "中间产物/_archive/<name>.html" \
  -w "%{http_code} %{size_download}\n"
```

**注意**：
- `--ssl-no-revoke` 必加（本机 schannel 吊销检查会直接失败）
- **不要 `curl -o /tmp/...`**，写到项目目录
- 发布态定格版本用 `list_page_publish_artifacts.py`（取 `meta.publishVersion`）；
  未发布过的页面会返回 `Code_ERR_PAGE_NOT_PUBLISHED`

### 第 4 步 · 字节级落盘 + 自证

```bash
cp "<下载的.html>" "输出/<报告名>_<MMDD>/index.html"
# 用 sha1 比对，证明零改动
```

```python
import hashlib
a = open(src, 'rb').read(); b = open(dst, 'rb').read()
print(hashlib.sha1(a).hexdigest(), hashlib.sha1(b).hexdigest(), a == b)
```

**落盘必须保持字节一致**——不注入、不美化、不改样式。要加交付说明就单独放一个 md，不要动 HTML。

---

## 2. 离线可用性核查（三条，先查再交付）

```python
import re
h = open('index.html', encoding='utf-8').read()
# ① 外部资源引用
ext = [m for m in set(re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', h))
       if m.startswith(('http', '//'))]
print('外部资源引用:', len(ext), ext[:5])
# ② 图片
print('img 标签:', len(re.findall(r'<img', h)), '| base64 内联:', len(re.findall(r'data:image/', h)))
# ③ 正文里的 URL（通常只是示例文本，不是资源依赖）
print('正文 URL 数:', len(set(re.findall(r'https?://[^\s"\'<>)]+', h))))
```

- **外部资源引用 = 0 且 img = 0** → 纯自包含，**断网可用**，双击即开
- 有外部引用 → 需逐条判断是资源依赖还是正文文本；真依赖要下载到本地并改相对路径
- > 判据：只有出现在 `src` / `href` 属性里的才算资源依赖；出现在正文段落里的 http 链接是**示例文本**

---

## 3. 交互核查（无头 Chrome，可选但推荐）

```bash
CHROME="/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
"$CHROME" --headless=new --disable-gpu --virtual-time-budget=9000 \
  --window-size=1440,1200 --dump-dom "file:///<abs>/index.html" > dom.html
```

看 DOM 里 JS 是否跑起来了（侧栏导航、卡片、筛选按钮、计数文本）：

```python
import re
d = open('dom.html', encoding='utf-8').read()
print('侧栏导航:', len(re.findall(r'<a[^>]+data-for="s\d+"', d)))
print('卡片:', len(re.findall(r'class="fitem', d)))
print('筛选钮:', re.findall(r'data-mod="([^"]*)"', d))
print('计数:', re.findall(r'id="fcount"[^>]*>([^<]*)<', d))
```

**坑**：`--dump-dom` 输出是 `\r\n`，正则用 `\r?\n` 或 `([\s\S]*?)`，别写 `\n`。

---

## 4. HTML → Markdown 保真转换（核心难点）

目标：正文**逐字保留**，把页面结构降级为标准 markdown。**不增补、不删改、不总结。**

### 4.1 执行顺序（错一步就丢编号）

```
① 去 <script> / <style>
② 去 UI 外壳（header / aside / nav / 搜索面板 / 进度条 / 按钮 / input）
③ 去 HTML 注释（含 <!--pnid:...--> 这类调试注释）
④ 去 data-page-node-id / data-pnid 属性
⑤ ★ 块级转换：h2（章节编号）→ summary（框架编号）→ 表格 → 清单 → .pw 提示词块 → 加粗/斜体/代码
⑥ 剥剩余的 class / style / id 属性
⑦ 剥所有标签
⑧ 空行与孤标记清理
```

> **★ 第 ⑤ 步必须在第 ⑥ 步之前。** 章节编号靠 `class="no"`、框架编号靠 `class="fid"` 识别；
> 先剥 class，编号就丢了，产出会变成 `## 00怎么用这份文档`（编号与标题黏在一起）。

### 4.2 四类结构的转换映射

| 源结构 | Markdown |
|---|---|
| `<h2>` + `<span class="no">01</span>标题 | `## 01 标题`（编号 + 空格 + 标题） |
| `<summary>` + `<span class="fid">1.1</span>标题 | `### 1.1 标题` |
| `<table>` | markdown 表格（首行后插 `\|---\|`） |
| `<div class="pw">`（`.pwh` 里 `.pt` 标题 + `.pm` 元信息 + `<pre>` 正文） | `**标题** · 元信息` + 带 ```text 围栏的代码块 |
| `<strong>` / `<b>` | `**x**` |
| `<em>` / `<i>` | `*x*` |
| `<a href="#s8">框架索引</a>` | 纯文本（归档版无页内跳转） |
| `<ul>` / `<ol>` / `<li>` | `- ` / `1. ` |

### 4.3 ★ 四个必避的坑（都实测踩过）

**坑 1 · 编号丢空格** —— 见 4.1，`class="no"` / `class="fid"` 必须在块级转换后才剥。
正确写法是先捕获编号、再从 inner 里删掉那个 span，最后 `编号 + ' ' + 标题`：

```python
NUM = []
inner = re.sub(r'<span[^>]*class="no"[^>]*>([\s\S]*?)</span>',
               lambda x: (NUM.append(x.group(1).strip()), '')[1], inner)
t = clean_inline(inner)
if NUM: t = NUM[0] + ' ' + t
```

**坑 2 · 加粗标记不配对（`**x** y**`）** —— 源页 `<b>` 跨标签/换行边界时，
非贪婪匹配会吃掉一侧标记。修法：

```python
# ✅ 只清"空加粗对"
body = re.sub(r'\*\*[ \t]*\*\*', '', body)
body = re.sub(r'\*\*\*\*', '', body)

# ❌ 绝对禁用：会把 **加粗** 的开头 ** 一起吃掉
body = re.sub(r'\*\*{2,}', '', body)
```

最后对 `**` 计数为**奇数**的行做一次孤标记降级（丢一个标记，宁可少一处加粗也不留破坏渲染的残标记）：

```python
def repair_bold(line):
    if line.count('**') % 2 == 0 or line.lstrip().startswith('#'):
        return line
    pos = [m.start() for m in re.finditer(r'\*\*', line)]
    p = pos[-1]
    return line[:p] + line[p+2:]
```

**坑 3 · 非贪婪跨块** —— `<div class="pw">[\s\S]*?</div>` 会因为 `.pw` 内嵌套 div 而提前收尾；
改用「起始标记 → 到 `<pre>…</pre>` → 收尾 `</div>`」的锚定写法：

```python
r'<div[^>]*class="pw"[^>]*>[\s\S]*?<pre[^>]*>[\s\S]*?</pre>[\s\S]*?</div>'
```

**坑 4 · 表格被吞** —— 先转 `<table>` 再做其他块级替换，否则 `</tr>` 到 `</table>` 之间的内容会被当普通文本拍平。

### 4.4 ★ 质检位（转换完必跑，作为覆盖性证明）

```python
import re
s = open(dst, encoding='utf-8').read(); L = s.split('\n')
print('章节数(##):',        len([l for l in L if l.startswith('## ')]))
print('框架条目(###):',      len([l for l in L if l.startswith('### ')]))
print('提示词块(```text):',  s.count('```text'))
print('表格行(|):',         len([l for l in L if l.startswith('|')]))
print('残留 pnid:',         s.count('pnid'))
print('残留 HTML 标签:',     len(re.findall(r'</?(?:div|span|strong|b|em|td|tr|table|details|summary|section|p)\b', s)))
print('不配对加粗行:',       len([l for l in L if l.count('**') % 2]))
```

**全部应为**：残留 pnid = 0、残留标签 = 0、不配对加粗 = 0；
章节/框架/提示词数量应**与源页自述数字一致**（例：源页写"145 条框架""28 个提示词"，
质检就必须数出 145 和 28——**这是最好的覆盖性校验位**）。

> ⚠️ 框架编号格式不止 `1.x`：可能混有 `§`、`#n`、`M2-n`、`M3-n`、`M4-n`。
> 统计时别只 match `^\d+\.\d+`，否则会漏算一大批而误判为"丢内容"。

---

## 5. 归档版取舍（要在交付说明里声明）

以下是**必须明说的取舍**，避免用户以为内容被删：

- **页脚交互提示条**（主题切换 / 搜索快捷键说明）、**首屏 hero 大字** = UI 外壳 → 归档版用开头说明替代
- **折叠展开**（`<details>`）→ 归档版直接展开为「### 标题 + 表格」
- **一键复制按钮** → 归档版转为 ```` ```text ```` 代码块（仍可复制）
- **搜索 / 筛选 / 主题切换** → 归档版不提供，需打开 `index.html`

---

## 6. 交付物清单（目录式，沿用本工作区约定）

```
输出/<名称>_<MMDD>/
├── index.html                    # 字节级复刻件（主交付物）
├── <名称>_<MMDD>.md              # Markdown 归档版
└── 交付说明_<MMDD>.md            # 保真度校验表 + 离线/交互核查 + 取舍声明
```

交付说明里至少要有：**源 SHA1 / 交付 SHA1 / 字节一致 ✅**、
**Markdown 转换质检表**（章节 / 框架 / 提示词 / 残留三项）、**离线可用性结论**、
**归档版取舍声明**、以及**内容归属与引用边界**（若是他人整理的内容，必须写明）。

---

## 7. 执行检查单

- [ ] nodeId 已归一化，`kind` 已确认是 `web` / `page`
- [ ] 产物已下载，`index.html` 与源 **sha1 一致**
- [ ] 外部资源引用数 = 0（或有依赖已本地化）
- [ ] 无头 Chrome DOM 核验：导航 / 卡片 / 筛选 / 计数均正常
- [ ] Markdown 归档版：章节数 / 框架数 / 提示词数 **与源页自述一致**
- [ ] 质检三项归零：残留 pnid = 0、残留标签 = 0、不配对加粗 = 0
- [ ] 交付说明含：保真度表 + 质检表 + 取舍声明 + 引用边界
- [ ] 未能复刻的部分（如远端付费墙、需登录的资源）已明确列出

---

## 8. 边界与安全

- **只读远端**：本技能不改远端任何内容；要改走 `edit-flow.md`
- **不改原始输入**：下载到 `中间产物/`，成品放 `输出/`
- **内容归属**：复刻的是他人整理的内容时，交付说明必须写明"非本工作区产出、
  仅做保真复刻、未改写未校订"，并保留源链接
- **不绕过权限**：需登录 / 付费墙后才有完整产物时，如实说明未能获取的部分，不伪造内容
