# assets/ 说明

可直接复用（复制后按场次改文案）的成品资产。

---

## `head.html`（446 行）

**样式骨架**：`<title>` + 完整 `<style>`，含 23 个设计令牌与全部 20 个组件。

**用法**：复制到 `中间产物/<任务名>/head.html`，只改两处：

1. `<title>` 改成本场报告的标题；
2. 若本场有特殊组件需求，在文件末尾追加（**不要改已有令牌**——改了会破坏系列场次的一致性）。

**注意**：本文件**不含** `<head>` / `<body>` 标签，套壳由 `build_report.py` 负责。
文件内容与 `references/03-style-spec.md` 的参数表一一对应，**参数表是权威**。

---

## `sidenav/`（侧栏三段模板）

派生「左侧常驻导航版」时使用，由 `extract_sidenav.py` 从成品中抽取，或直接复制本目录。

| 文件 | 插入位置 | 内容 |
|---|---|---|
| `sidenav_css.html` | `</style>` **之前** | `--sidew` + `aside.side` + 抽屉样式 + 打印还原（含 1100px 断点） |
| `sidenav_nav.html` | `<body>` 之后、`<div class="wrap">` 之前 | 侧栏 DOM + 抽屉把手 + 遮罩 |
| `sidenav_js.html` | `</body>` **之前** | scroll spy + 进度条 + 平滑定位 + 抽屉开合 |

**用法**：把这三个文件放到 `中间产物/<任务名>/sidenav/`，
然后跑 `build_sidenav.py`（它会读主报告 `index.html` 的目录 DOM 重新生成导航项，
并自动替换品牌区文案 —— 品牌文案在同脚本顶部的 `BRAND` 常量里改）。

**为什么导航项要重新生成**：侧栏里另写一份目录必然与正文脱节。
从主报告 `<nav class="toc">` 解析，改章节时侧栏自动跟着变。

**行为契约**（scroll spy 探针公式、点击 900ms 锁、触底锁末节、抽屉三关闭路径等）
见 `references/04-interaction-spec.md` §5。
