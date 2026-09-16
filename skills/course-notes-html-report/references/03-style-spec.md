# 视觉与样式规范

> 直接可用的样式骨架见 `assets/head.html`（446 行，含全部组件 CSS）。
> **本文件是权威参数表**；`assets/head.html` 是其实现。改样式只改 `head.html` 一处，**不要用行内样式**。

---

## 1. 设计令牌（唯一真源，写在 `head.html` 的 `:root`）

```css
:root{
  /* 底色系 */
  --bg:#0a0e15; --bg2:#0d131d; --card:#131c2a; --card2:#18233a; --card3:#1d2a43;
  --line:#243149; --line2:#31425f;
  /* 文字系 */
  --tx:#e9eff8; --tx2:#a8b6cb; --tx3:#7c8a9e;
  /* 主色：金（下半场 / 品牌 / 老师原话） */
  --gold:#f5b942; --gold2:#ffd47a; --goldbg:rgba(245,185,66,.10);
  /* 副色：蓝（上半场 / 信息 / 中性提示） */
  --blue:#4aa8ff; --blue2:#8ccbff; --bluebg:rgba(74,168,255,.10);
  /* 语义色 */
  --cyan:#3ddad7; --green:#3ddc97; --red:#ff6b6b; --purple:#a78bfa; --pink:#f472b6;
  /* 布局（侧栏版追加，见 assets/sidenav/sidenav_css.html） */
  --sidew:288px;
}
```

**主题固定为深色**。这是系列场次的统一观感，不要按「用户当前 IDE 主题」切换——
交付物是**独立分发的文档**，不是嵌入宿主环境的组件。

---

## 2. 色彩语义表（**不得随意换色**）

| 颜色 | 令牌 | 固定语义 | 用在哪 |
|---|---|---|---|
| 金 | `--gold` | 老师原话 / 下半场 / 品牌强调 | `.quote`、`.sec-h.pm .no`、`em`、表头 |
| 蓝 | `--blue` | 上半场 / 信息提示 / 代码 | `.sec-h.am .no`、`.hl.info`、`.kcol.am` |
| 青 | `--cyan` | 课堂数据 | `.quote.d` |
| 绿 | `--green` | 我的总结 | `.mine` |
| 紫 | `--purple` | 可复用资产 / 标签 | `.asset`、`.badge` |
| 红 | `--red` | 风险 / 卡点 | `.hl` |

> **上下半场双色体系**：上半场 A 用蓝、下半场 B 用金（`.am` / `.pm` 两个修饰类贯穿
> 章节头、步骤序号、表格表头、导航项、知识地图两列）。
> **这是全篇最重要的视觉锚点**，让读者在任意位置都知道「我在上半场还是下半场」。

---

## 3. 排版尺度表

| 元素 | 字号 | 其他 |
|---|---|---|
| `body` | 15px（≤760px → 14.5px） | `line-height:1.85`、`letter-spacing:.01em` |
| `h1.title` | 38px（→27px） | 渐变文字 `linear-gradient(102deg,#fff,#ffe6b0,var(--gold))` |
| `.sec-h h2`（章节标题） | 23px（→19.5px） | `font-weight:750` |
| `h3.sub` | 17.5px | 左侧 4px 竖条 `::before` |
| `h4.sub2` | 15px | 金色（蓝场用 `--blue2`） |
| `.lead` | 14.5px | 章节导语 |
| `.quote` | 14.5px | 行高 1.85 |
| `.mine p` | 13.8px | |
| `.asset li` | 13.5px | |
| `table` | 13.2px | `th` 12.5px（→12.4px） |
| `pre.prompt` / `code` | 12.8px | 等宽 `ui-monospace,Consolas` |
| `.src` / `.badge` | 11px | 时间戳、标签 |

**间距节奏**：`section` 下边距 54px · `scroll-margin-top:22px` · 块级组件上下 16px ·
`.grid` gap 14px · `.card` padding 16px 18px · `.wrap` padding `0 20px 90px`。

**容器宽度**：`.wrap` `max-width:1160px` + 居中。

---

## 4. 组件清单（20 个，不得自造同类）

| 组件 | 类名 | 用途 | 关键约束 |
|---|---|---|---|
| 章节头 | `.sec-h` + `.no` + `.tt` + `.st` | 章节标题 | `.no` 是编号徽章（A1/B1/12/附） |
| 卡片 | `.card` / `.card.mini` / `.card.tinted` | 并列要点 | `h5` 可含 `.badge` |
| 网格 | `.grid` + `.g2/.g3/.g4/.g23` | 布局 | 子元素须 `min-width:0` |
| 老师原话 | `.quote` | 四档① | 左侧金边，`::before` 自带标签 |
| 课堂数据 | `.quote.d` | 四档② | 青色 |
| 我的总结 | `.mine` | 四档④ | `::before` 是 🦞，左侧留 52px |
| 可复用资产 | `.asset` | 行动清单 | 虚框 |
| 高亮盒 | `.hl` / `.hl.ok` / `.hl.info` | 风险 / 确认 / 提示 | 左侧 3px 语义色 |
| 指标卡 | `.kv` + `.i` + `.v` + `.k` | 数字总览 | 4 列，`.v` 可 `.bl/.gn/.rd` |
| 表格 | `.tw` + `table` | 对照 / 清单 | **必须包 `.tw`**（提供横向滚动） |
| 步骤条 | `<ol class="steps">`（`.am` 蓝） | 有序方法 | `counter-reset` 自动编号 |
| 流程条 | `.flow` + `.st` + `.arw` | 闭环 / 管道 | 弹性换行 |
| 折叠相册 | `details.gal` | 照片 | `summary` 展示数量与时间范围 |
| 照片网格 | `.shots`（`.one`/`.three`） | 正文配图 | 默认 2 列 |
| 照片卡 | `.shot` + `a[data-zoom]` + `.cap` | 单张照片 | `a` 由 JS 接管灯箱 |
| 矢量重建图 | `.kfig` | 框架图 | `h5::before` 自动加「重建」 |
| 案例卡 | `.case` + `.ch` | 案例 | |
| 定义列表 | `.dl` + `.d` | 术语表 | `grid 150px 1fr` |
| 知识地图 | `.kmap` + `.kmap-body` + `.kspine` | 全局地图 | `1fr 132px 1fr` |
| 来源标注 | `.src` | 时间戳 / 出处 | 11px 灰 |
| 代码盒 | `.pbox` + `.pbox-h` + `pre.prompt` + `.cbtn` | Prompt | **必须有复制按钮** |

> 组件表列 20 项（含 `.src`）；其余类名（`.fig` / `.knode` / `.toc-grid` 等）是上述组件的内部结构类，
> 不要单独当组件用。

---

## 5. 响应式断点

| 断点 | 变化 |
|---|---|
| `≤1100px` | 左侧栏收成抽屉（仅导航版，见 interaction-spec §5） |
| `≤980px` | `.g3/.g4/.kv` → 2 列；`.kmap-body` → 单列（脊柱转横排）；`.dl .d` → `120px 1fr` |
| `≤760px` | 全部网格 → 单列；`h1` 27px；`body` 14.5px；`.wrap` padding `0 14px 70px`；`.quote/.mine/.asset/.hl` 收窄内边距 |

### 窄屏表格的处理（必做，否则撑破视口）

```css
@media(max-width:760px){
  table{min-width:0;font-size:12.4px}   /* 全局放开最小宽度 */
  .tw table{min-width:452px}            /* 但有滚动容器的表保留宽表 */
  .kfig table{min-width:0}              /* 重建表可压缩 */
}
```

**若不放开**：全局 `table{min-width:520px}` 会撑破窄屏——`.tw` 容器有 `overflow:auto` 没问题，
但 `.kfig` 里的裸 `<table>` 没有滚动容器，会直接把文档顶宽。

**验证方式**：真视口探针（iframe 定宽模拟 360/390/480px）断言
`document.scrollWidth == 视口宽`，且**容器外**越界元素数为 0
（判定时必须跳过 `overflowX:auto|scroll` 祖先内的元素）。

---

## 6. 打印 / 导出 PDF

```css
@media print{
  .zoom{display:none!important}                       /* 灯箱隐藏 */
  .shots,.shots.three{grid-template-columns:1fr 1fr}  /* 照片两列 */
  details.gal{border:0} details.gal>summary{display:none}
  details.gal .gb{padding:0}                          /* 相册全部展开 */
  aside.side,.sidenav-btn,.sidenav-mask{display:none!important}
  body.has-side{padding-left:0}
  body.has-side nav.toc{display:block}                /* 侧栏版还原页内目录 */
}
```

> 目标：**打印出来的是一份完整文档**，不是网页截图。
> 实测整页 PDF 约 8 MB（17 节 / 7.8 万字 / 264 张图）。

---

## 7. 禁用项（硬约束）

| 禁止 | 原因 |
|---|---|
| 任何外部 CDN / 远程字体 / 外链 script | 必须**离线可打开**；图表库要内联 |
| `fetch` / `XMLHttpRequest` / `import()` | 同上（`file://` 下会被 CORS 拦） |
| 用图片替代文字（把框架图整张截图当内容） | 不可检索、不可复制、打印模糊 |
| 自造第六种标注色 | 破坏四档体系 |
| 修改设计令牌去「美化」 | 破坏系列场次的一致性（要能拼接） |
| 把 `.mine` 写成复述 | 见 content-restoration §3 反例 |
| 用行内样式覆盖布局 | 样式真源只在 `head.html`，否则改一处漏九处 |

**「零外部依赖」自检**：构建脚本里扫 `link` / `src=` / `url(` / `@import`，命中即报警。
注意**正文里出现的 `https://...` 示例链接是文本，不是依赖**，不要误删。
