# scripts/ 使用说明

所有脚本共用 `_paths.py` 做路径解析，**支持三个统一参数**（可混在脚本原有参数里）：

```
--root   <项目根>          含 原始输入/ 中间产物/ 输出/ 的目录
--task   <任务名>          中间产物下的子目录名（分片与 head.html 所在处）
--report <报告目录名>      输出/<这个目录>/（主报告 index.html 所在处）
```

等价的环境变量：`CR_ROOT` / `CR_TASK` / `CR_REPORT` / `CR_WORK` / `CR_OUT`。

**不传参数时会自动探测**（向上找项目根 → 找含 `p1.html` 的任务目录 → 找最近修改的报告目录）。
但**输出目录下有多个报告时自动探测可能选错**，稳妥做法是显式传 `--task` 与 `--report`。

先自检路径：

```bash
python _paths.py --task <任务名> --report <报告目录名>
```

---

## 脚本清单

| 脚本 | 何时用 | 关键参数 |
|---|---|---|
| `prep_images.py` | 照片管线：去重 / 双尺寸压缩 / 生成 `image_map.json` | `--shots-src` `--manual-src` |
| `make_sheets.py` | 生成 3×3 索引拼图（批量识图用） | — |
| `build_report.py` | 拼接分片 → 主报告 `index.html` | `--frag N`（只建到第 N 片） |
| `build_md.py` | HTML → Markdown 归档版 | — |
| `extract_sidenav.py` | 从**上一场**导航版成品抽三段模板 | 环境变量 `CR_SIDENAV_SRC` |
| `build_sidenav.py` | 派生左侧导航版（不覆盖主报告） | 顶部 `BRAND` 常量 |
| `prep_publish.py` | 建发布副本目录（+ 不可见 OG 标签） | — |
| `verify_report.py` | **五层验证**（结构 / 资源 / 一致 / 渲染 / 窄屏） | — |
| `verify_md.py` | HTML ↔ MD 结构计数一致性 | — |
| `verify_sidenav.py` | 正文零改动 + 主报告未被覆盖（字节级） | — |
| `verify_live.py` | 线上资源全量核验（sha1 + 逐张图片） | — |
| `probe_overflow.py` | 多视口横向溢出探针 | — |
| `probe_narrow.py` | 真视口窄屏探针（iframe 定宽） | — |
| `qa_scrollspy.py` | scroll spy 逐节走查（`--dump-dom`） | — |
| `qa_section_shots.py` | 逐节独立渲染截图 | — |
| `qa_sidenav_hl.py` | 三种高亮配色截图 | — |
| `qa_sidenav_narrow.py` | 窄屏抽屉行为验证 + 截图 | — |
| `qa_sidenav_shots.py` | 导航版关键状态截图 | — |
| `qa_gallery.py` | 相册专项截图 | — |

---

## 典型工作流（按顺序）

```bash
# 0) 自检路径
python _paths.py --task course_report_day2 --report "XXX_0915"

# 1) 照片：压缩 + 映射表 + 索引拼图
python prep_images.py --task course_report_day2 --report "XXX_0915" \
    --shots-src "<项目根>/原始输入/Day2/day2" \
    --manual-src "<项目根>/原始输入/Day2/<手册目录>/images"
python make_sheets.py --task course_report_day2 --report "XXX_0915"

# 2) 构建（写完 p1..pN.html 与 head.html 之后）
python build_report.py  --task course_report_day2 --report "XXX_0915"

# 3) 验证
python verify_report.py --task course_report_day2 --report "XXX_0915"

# 4) 派生与归档
python build_sidenav.py --task course_report_day2 --report "XXX_0915"
python build_md.py      --task course_report_day2 --report "XXX_0915"

# 5) 派生版专项验证
python verify_sidenav.py --task course_report_day2 --report "XXX_0915"
python qa_scrollspy.py   --task course_report_day2 --report "XXX_0915"
python verify_md.py      --task course_report_day2 --report "XXX_0915"

# 6) （可选）发布
python prep_publish.py   --task course_report_day2 --report "XXX_0915"
python verify_live.py    --task course_report_day2 --report "XXX_0915" \
    --url "https://xxx.app.workbuddy.host"
```

---

## 依赖

- Python 3 标准库 + **Pillow**（照片管线、索引拼图）
- 无头 Chrome（渲染验证、截图）：`C:/Program Files (x86)/Google/Chrome/Application/chrome.exe`
- `chart.umd.min.js`（**仅当**报告里出现 `<canvas>` 才需要，放在中间产物目录）

## 运行时注意

- **每条命令前导出 PATH**（本机 bash 缺 coreutils）：
  `export PATH="/c/Windows/System32:/c/Windows:/usr/bin:/bin"`
- `crashpad` 报错日志无害，用 `| grep -v crashpad` 过滤（中文输出可能被 grep 判为二进制，用 `grep -av`）
- curl 要加 `--ssl-no-revoke`，且**不要 `-o /tmp/...`**
