# 交互规范

> 原则：**纯原生 JS、零外部依赖、渐进增强**（JS 失效时页面仍可读）。
> 全部脚本内联在 `</body>` 前，样式内联在 `<head>`。
> 可直接复用的实现：`assets/sidenav/sidenav_js.html`（侧栏）+ `scripts/build_report.py` 内嵌的 `TAIL_JS`（复制/灯箱/相册）。

---

## 1. 交互清单与行为契约

| # | 交互 | 触发 | 行为 | 收尾 |
|---|---|---|---|---|
| 1 | **Prompt 复制** | 点 `.cbtn[data-copy]` | 取同 `.pbox` 内 `pre` 的 `innerText` → 写剪贴板 | 文案变「已复制」1.6s 后复原 |
| 2 | **照片灯箱** | 点 `a[data-zoom]` | 大图 `src` 取自 `a[href]`，说明取 `data-cap`，加 `.on`，锁滚动 | 背板 / × / Esc 关闭并清 `src` |
| 3 | **折叠相册懒加载** | `details.gal` 展开 | 把内部 `img[data-src]` 提升为 `src` | 只做一次 |
| 4 | **侧栏滚动高亮** | 滚动 / resize / load | 探针线公式定位当前节 → 高亮对应导航项 | 触底锁定最后一节 |
| 5 | **激活项自动入视野** | 高亮切换时 | 最小滚动量把激活项滚进侧栏可视区 | 内边距 12px |
| 6 | **阅读进度条** | 滚动 | `width = y / max * 100%` | — |
| 7 | **点击跳转** | 点侧栏项 | 平滑滚动到 `元素top - 16px`；写回 `history.replaceState('#id')` | 900ms 内不抢高亮 |
| 8 | **窄屏抽屉** | `≤1100px` 点把手 | `body.nav-open` 显隐；遮罩 / Esc / 拉宽自动收起 | 遮罩点击关闭 |

**契约的含义**：这 8 项是**必须实现**的行为，验收清单里逐项打勾。
第 1—3 项基线版必备；第 4—8 项仅导航版需要。

---

## 2. 复制按钮状态机

```
[复制] ──click──▶ copy(pre.innerText)
   ├── 成功 ──▶ [已复制] (+ .ok 绿色) ──1.6s──▶ [复制]
   └── 失败 ──▶ [请手动选择]
```

**实现要求**：

1. `navigator.clipboard.writeText` 优先；不可用（**`file://` 下常见**）时降级到
   隐藏 `<textarea>` + `execCommand('copy')`；
2. 文案复原要读回 `data-old`，**不要硬编码「复制」**（便于将来改词）；
3. 按钮与代码块的从属关系用 `btn.closest('.pbox').querySelector('pre')` 定位，**不要靠索引**。

```js
document.querySelectorAll('[data-copy]').forEach(function(btn){
  btn.addEventListener('click', function(){
    var box = btn.closest('.pbox');
    var pre = box ? box.querySelector('pre') : null;
    if (!pre) return;
    copyText(pre.innerText).then(function(){
      var old = btn.getAttribute('data-old') || '复制';
      btn.setAttribute('data-old', old);
      btn.textContent = '已复制'; btn.classList.add('ok');
      setTimeout(function(){ btn.textContent = old; btn.classList.remove('ok'); }, 1600);
    }).catch(function(){ btn.textContent = '请手动选择'; });
  });
});
```

> **为什么 `file://` 降级是刚需**：交付要求「离线双击可打开」，
> 而 `navigator.clipboard` 在 `file://` 协议下常被拒（非安全上下文）。
> **没有降级路径 = 复制按钮在离线场景全废**，而 Prompt 复制正是报告的卖点之一。

---

## 3. 灯箱行为契约

| 项 | 要求 |
|---|---|
| DOM | **单例**，放在 `<body>` 起始处：`.zoom#zoom > button.zx + img + div.zc` |
| 打开 | 用**事件委托**（`document` 上监听 `click`，找 `closest('a[data-zoom]')`）——相册是懒生成的，不要逐个绑定 |
| 遮罩 | `rgba(4,7,12,.95)`，`padding:26px 20px 62px`（底部留说明空间） |
| 大图 | `max-height: calc(100vh - 110px)`，圆角 8px，投影 `0 24px 70px rgba(0,0,0,.7)` |
| 说明 | 底部居中，内容 = `data-cap`（章节 ｜ 编号 · 时间戳） |
| 关闭 | ① 点背板 ② 点 `×` ③ Esc —— **三者都要**；关闭时 `zi.removeAttribute('src')`（释放内存） |
| 滚动锁 | 打开时 `documentElement.style.overflow='hidden'`，关闭时置 `''` |
| 可访问性 | `role="dialog"` `aria-modal="true"`；`×` 有 `aria-label="关闭"` |

---

## 4. 折叠相册懒加载契约

- 相册内所有 `<img>` 初始只写 `data-src`，**不写 `src`**；
- 监听 `details` 的 `toggle` 事件，`open` 时批量提升 `data-src → src` 并
  `removeAttribute('data-src')`（**幂等，只提升一次**）；
- 缩略图加 `loading="lazy"` 与显式 `width`/`height`；
- **验证断言**：`img[data-src]` 数量 > 0（证明懒加载存在），
  且构建统计里打印「懒加载图片 N 张」。

---

## 5. 侧栏导航契约（派生版核心）

### 结构（三段插入，正文零改动）

| 段 | 插入位置 | 内容 |
|---|---|---|
| 样式 | `head.html` 的 `</style>` **之前** | `--sidew` + `aside.side` + 抽屉 + 打印还原 |
| DOM | `<body>` **之后、`<div class="wrap">` 之前** | `aside.side#sidebar` + `.sidenav-btn` + `.sidenav-mask` |
| 脚本 | `</body>` **之前** | scroll spy + 跳转 + 抽屉 |
| 属性 | `<body>` 改为 `class="has-side" id="top"` | 进度条与淡出动画需要独立滚动容器 |

### 滚动高亮（scroll spy）关键算法

```js
/* 探针线：视口高度的 30%，但最多 260px —— 避免大屏下「高亮跳两节」 */
var probe = y + Math.min(window.innerHeight * 0.30, 260);
var id = secs[0].id;
for (var i = 0; i < secs.length; i++) {
  var top = secs[i].getBoundingClientRect().top + y;
  if (top <= probe) id = secs[i].id; else break;      // secs 已按 offsetTop 排序
}
if (max > 0 && y >= max - 2) id = secs[secs.length - 1].id;  // 触底锁定末节
setActive(id);
```

### 其余规则

| 项 | 规格 |
|---|---|
| 侧栏宽度 | `--sidew:288px`，`body.has-side{padding-left:var(--sidew)}` |
| 固定方式 | `position:fixed; left:0; top:0; height:100dvh`（`100vh` 兜底） |
| 高亮态 | `.on`：左 2px 竖条（`border-left-color`）+ 底色 + `font-weight:600` + `aria-current="true"` |
| 高亮配色 | A 段 `--bluebg`/`--blue`；B 段 `--goldbg`/`--gold`；中性段金 |
| 只留一项 | `setActive` 里**先清上一项**再置新项，同一时刻只有 1 项 `.on` |
| 点击锁定 | `lock = Date.now() + 900`，期间 spy 直接 `return`，避免「点击后高亮乱跳」 |
| 节流 | `rAF` 优先 + `setTimeout(done, 60)` **兜底**（后台标签页 / 无头环境下 rAF 会被节流） |
| 滚动监听 | `addEventListener('scroll', onScroll, {passive:true})` |
| 进度条 | `width = (y/max*100).toFixed(2) + '%'`，`transition:width .12s linear` |
| 锚点直达 | 载入时若有 `#hash`，`setTimeout(…, 60)` 后滚到 `top - 16px` |
| 导航项来源 | **从主报告目录 DOM 解析生成**，不要在侧栏里另写一份（防止与正文脱节） |
| 分组标签 | 速览 / 上半场·A1—An / 下半场·B1—Bn / 工具与参考（`.snav-g`，`.mg` 蓝 / `.pg` 金） |

### 窄屏（≤1100px）转抽屉

| 项 | 规格 |
|---|---|
| 侧栏 | `width:min(300px,85vw)`；`transform:translateX(-100%)` → `body.nav-open` 时归位 |
| 过渡 | `transform .27s cubic-bezier(.4,0,.2,1)`；`box-shadow:0 0 70px rgba(0,0,0,.72)` |
| 把手 | 左边缘竖排按钮（`writing-mode:vertical-rl`），`☰` + 竖排「目录」，`top:50%` |
| 遮罩 | `rgba(4,7,12,.66)`，`z-index:55`（低于侧栏 60、低于把手 70） |
| 关闭路径 | 遮罩点击 / Esc / 拉宽到 `≥1101px`（`matchMedia` 监听） |

> **把手优于左上角按钮**：左上角会压住 hero 标题；左边缘竖排把手不占内容区。

### 布局要点（关键是别用 `margin-left`，否则窄屏没法收）

```css
body.has-side{padding-left:288px}                       /* 让出侧栏 */
body.has-side .wrap{max-width:1160px;margin:0 auto}     /* 正文在剩余宽度内居中 */
aside.side{position:fixed;left:0;top:0;width:288px;height:100vh;height:100dvh;
  display:flex;flex-direction:column}                   /* 100dvh 兼容移动端地址栏 */
body.has-side nav.toc{display:none}                     /* 页内目录隐藏，避免两套导航重复 */
```

侧栏三段：`.side-top`（品牌 + 进度条）/ `.side-scroll`（`overflow-y:auto` 的列表）/ `.side-foot`。

隐藏页内目录**用纯 CSS（不改 DOM）**，这样正文片段与源文件都不动，且打印可复原。

---

## 6. 键盘与可访问性

| 项 | 要求 |
|---|---|
| Esc | 关闭灯箱 + 关闭抽屉 |
| 语义 | `aside[aria-label]`、`nav`、`details/summary` 原生语义、`role="dialog" aria-modal` |
| 状态 | 高亮项带 `aria-current="true"` |
| 图标按钮 | 必须有 `aria-label`（`×`、`☰`） |
| 焦点 | 不使用 `tabindex` 黑魔法；用原生可聚焦元素（`a`/`button`/`summary`） |
| 动效 | `@media(prefers-reduced-motion:reduce){ transition:none!important; scroll-behavior:auto }` |

---

## 7. 性能预算

| 指标 | 目标 |
|---|---|
| 首屏图片请求 | 只加载正文配图缩略图（相册不加载） |
| 单张网格图 | ≤ 30 KB（560px / q72） |
| 单张大图 | ≤ 250 KB（1400px / q78） |
| JS 总量 | ≤ 10 KB（不含内联的图表库） |
| 图表库 | 仅当正文出现 `<canvas>` 时才内联（Chart.js 约 205 KB，**能省则省**） |
| 外部请求 | **0** |

---

## 8. 图表（可选增强）

用 Chart.js，**必须内联** `chart.umd.min.js`（约 205 KB）。
构建脚本**检测到 `<canvas>` 后才内联**，避免无用体积。

> 实测经验：**照片与框架表已能承载信息时，不要为图而图**。
> 一次 17 节的课程报告最终未使用任何图表——课堂的核心信息形态是「框架」和「对照」，
> 不是「时间序列」，强行画图反而稀释信息。
