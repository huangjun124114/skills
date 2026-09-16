# 📚 课程要点还原报告 (Course Notes HTML Report)

> 把一场培训的多源材料（录音转写、课堂纪要、课件照片、讲师手册、外部研报）还原成一份**可二次输出**的完整课程要点 HTML 报告。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![WorkBuddy Skill](https://img.shields.io/badge/WorkBuddy-Skill-blue.svg)](https://github.com/huangjun124114/skills)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

---

## 解决什么问题

听完一场培训，手里有转写、纪要、一叠课件照片。常见的处理结果是**一份要点摘抄**——看起来完整，但没法二次使用。

本技能的输出目标是另外三件事：

| 要素 | 含义 |
|---|---|
| **可核查的事实分层** | 读者一眼分清「哪句能直接引用、哪个数字要核对、哪段是我的判断」 |
| **可复用的资产清单** | Prompt 原文、框架、清单被抽出来单独成节，可直接搬走用 |
| **一眼看到全局的知识地图** | 一页纸速览 + 全景图，不必读完 7 万字才知道讲了什么 |

---

## 三条判定标准（先看这个）

动手前先用这三条决定方案，选错要返工重做全部插图。

### ① 课件照片怎么处理

| 照片数 | 方案 |
|---|---|
| **> 30 张** | **目录式 + 双轨制** —— `index.html` + 同级 `images/`；照片嵌入**且**核心框架矢量重建 |
| < 10 张 | 单文件 + 纯矢量重建即可 |

> 两轨解决的是不同问题，照片密集场次必须都要：照片是现场证据但不可检索，重建图可检索但可能抄错。单文件 base64 会把 20 MB 图塞进正文，编辑器打不开。

### ② 「我的总结」合不合格

三段里**至少一段是判断或行动**（① 翻译 ② 判断 ③ 落地）。三段全是「老师说得对」→ 不合格，必须重写。

### ③ 能不能做推测性还原

**只有讲义、没有录音/纪要/课件照片的场次 → 不做。** 写进附录「覆盖边界说明」与交付说明，不要拿讲义去「写」一堂没听过的课。

---

## 安装

```bash
git clone --filter=blob:none --sparse https://github.com/huangjun124114/skills.git
cd skills
git sparse-checkout set skills/course-notes-html-report
cp -r skills/course-notes-html-report ~/.workbuddy/skills/
```

或下载本目录的 ZIP 后解压到 `~/.workbuddy/skills/course-notes-html-report/`。

---

## 技能包结构

```
course-notes-html-report/
├── SKILL.md                        流程骨架 + 三条判定标准（入口，317 行）
├── references/                     七份规范，按需加载
│   ├── 01-content-restoration.md   内容还原：四源分工 / 四档标注 / 总结三段式 / 误记词典 / 边界纪律
│   ├── 02-photo-pipeline.md        照片处理：拼图参数 / 去重 / 压缩双管线 / image_map / 相册生成 / 双轨制
│   ├── 03-style-spec.md            样式：23 设计令牌 / 色彩语义 / 排版尺度 / 20 组件 / 断点 / 打印
│   ├── 04-interaction-spec.md      交互：8 项行为契约 / 复制状态机 / 灯箱 / scroll spy / 性能预算
│   ├── 05-build-and-derive.md      工程：分片构建 / 侧栏派生 / MD 归档 / 脚本职责
│   ├── 06-verify-checklist.md      验证：五层验证 / 60 项验收总清单 / 线上七步 / 发布流程
│   └── 07-pitfalls.md              30 余条实测坑（环境 / 渲染 / 布局 / 内容）
├── scripts/                        可跑脚本，统一路径参数（--root / --task / --report）
│   ├── _paths.py                   统一路径配置与自动探测
│   ├── prep_images.py              照片管线 → image_map.json
│   ├── make_sheets.py              3×3 索引拼图
│   ├── build_report.py             分片拼接 → index.html（相册注入 / 条件内联图表 / 配平自检）
│   ├── build_md.py                 HTML → Markdown 归档版
│   ├── extract_sidenav.py          从既有导航版抽取侧栏三段模板
│   ├── build_sidenav.py            派生左侧导航版（不覆盖主报告）
│   ├── prep_publish.py             生成发布副本目录
│   ├── verify_report.py            五层验证
│   ├── verify_md.py                HTML ↔ Markdown 结构计数一致性
│   ├── verify_sidenav.py           正文零改动 + 原版未覆盖（字节级）
│   ├── verify_live.py              线上资源全量核验
│   ├── probe_overflow.py           多视口横向溢出探针
│   ├── probe_narrow.py             真视口窄屏探针（iframe 定宽）
│   ├── qa_scrollspy.py             scroll spy 逐节走查
│   └── qa_*.py                     各类截图与专项验证
└── assets/
    ├── head.html                   样式骨架（446 行，含全部 20 组件 CSS）
    ├── sidenav/                    侧栏三段模板（css / nav / js）
    └── README.md                   用法与插入位置
```

---

## 核心方法

### 四档忠实度标注

整份报告的生命线。最致命的错误是把「我的推断」和「老师原话」混在同一个样式里 —— 可信度归零。

| 档位 | 组件 | 视觉 | 纪律 |
|---|---|---|---|
| ① 老师原话 | `.quote` | 金框 | 逐字还原，不改写、不润色 |
| ② 课堂数据 | `.quote.d` | 青框 | 数字原样，未做独立复算则须声明 |
| ③ 复算校验 | 数据表 + `.note` | 中性 | 拿不到同一数据集就不做，别硬造 |
| ④ 我的总结 | `.mine` 🦞 | 绿框 | 必须与前三档视觉可区分 |

页脚必须放四档图例，附录再放一次「未做复算 + 原因」。

### 索引拼图法（照片密集场次的关键）

110 张照片逐张读 = 110 次调用，太贵。先压成 12 张 3×3 拼图（每格带 `pNNN + 时间戳` 黄标签），**一次读 9 张**，12 次看完全部；建立映射后，再对核心框架图（约 20 张）逐张精读原图。

照片编号顺序 = 课程顺序（文件名时间戳即讲课顺序），这是「照片自动归位」的依据。

压缩双管线实测均值：

| 用途 | 宽度 | 质量 | 均值 |
|---|---|---|---|
| 大图（灯箱） | 1400px | 78 | 129 KB |
| 缩略图（网格） | 560px | 72 | 28.3 KB |

### 分片构建（长报告必须这么做）

7 万字报告写在单文件里，任何一次编辑都要重读全文，成本爆炸且容易截断。拆成 `head.html` + `p1..pN.html`，由 `build_report.py` 拼接、套壳、注入灯箱、替换相册占位符、条件内联图表、追加交互脚本，最后做标签配平自检。

### 五层验证（可复跑，不许只说「已检查」）

| 层 | 查什么 | 判定 |
|---|---|---|
| L1 结构 | section id 无重复；站内链接都有落地章节；目录顺序 == 章节顺序 | 全通过 |
| L2 资源 | 正文引用图片全部存在；大图都有缩略图入口；有懒加载标记 | 零缺失 |
| L3 一致 | Prompt 块数 == 复制按钮数；每节都有 `.mine` + `.asset` | 完全相等 |
| L4 渲染 | 无头 Chrome 宽/窄截图成功；整页 PDF 生成成功 | 图 > 20 KB |
| L5 窄屏真视口 | iframe 定宽 360/390/480px：无横向溢出，容器外越界元素 0 | 全绿 |

派生版的「**正文零改动**」要有硬证据：新旧两版从 `<div class="wrap">` 起逐字节比对，并断言新版 style 块以原版为**前缀**（证明是追加而非改写）。

---

## 交付形态

```
输出/<报告名>_<MMDD>/
├── index.html                    ← 主报告，双击即开，零外部依赖
├── images/                       ← 大图 + t/ 缩略图（必须与 index.html 同级）
├── 课程要点_<MMDD>.md            ← Markdown 归档版（投喂知识库 / 转 Word）
├── 交付说明_<MMDD>.md            ← 二次输出入口
└── （可选）index_左侧导航版_<MMDD>.html
```

- **多版本并存、永不覆盖**：派生版一律加后缀，改新版不动旧版；
- **中间产物隔离**：脚本/拼图/截图留在 `中间产物/`，输出目录只放交付物；
- **原始输入全程只读**：禁止写入、重命名、移动。

报告可派生三种形态：**左侧常驻导航版**（滚动高亮 + 窄屏抽屉）、**Markdown 归档版**、**在线发布版**（发布副本目录 + 线上全量核验）。

---

## 依赖与边界

**环境**：Python 3.13+（Pillow）；无头 Chrome 用于渲染验证。视觉与交互的通用工程细节（分片拼接、内联 Chart.js、探针写法）另见配套技能 [`html-data-report`](../html-data-report/)，本技能不重复。

**不适用**：
- 只有讲义、无录音/纪要/照片的场次（不做推测性还原）
- 单篇短文整理（分片构建与五层验证是给长报告准备的）
- 需要在线协作编辑的场景（交付物是离线静态文档）

---

## License

[MIT](https://github.com/huangjun124114/skills/blob/main/LICENSE)
