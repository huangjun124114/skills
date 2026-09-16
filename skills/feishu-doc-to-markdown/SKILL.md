---
name: feishu-doc-to-markdown
description: >
  把飞书云文档（wiki / docx）导出为可独立分发的本地 markdown：正文逐字保留，
  图片与文件附件（视频/zip/pdf）下载到本地并改写为相对路径，分栏、引用、HTML
  表格等飞书专有结构降级为标准 markdown。
  触发词：飞书文档下载为markdown、飞书文档导出、wiki导出markdown、飞书文档转md、
  保存飞书文档、文档图片下载、feishu doc to markdown、导出学员手册、导出手册。
agent_created: true
---

# 飞书云文档 → 本地 markdown

把飞书文档变成「拷走整个文件夹就能用」的 markdown。核心难点不是取正文，而是
**飞书专有结构 + 私有资源链接**：图片是 `feishu.cn/file/<token>` 私有链接，外发即失效。

## 快速使用

```bash
python ~/.workbuddy/skills/feishu-doc-to-markdown/scripts/feishu_md_export.py \
  "<文档URL或token>" --outdir "<输出目录>" [--name "<文件名前缀>"]
```

产出结构：

```
<输出目录>/
├── <name>.md          # 正文，图片/附件均为相对路径
├── images/            # 图片，按文档顺序编号 + 上下文命名
└── attachments/       # 视频 / zip / pdf 等文件附件（仅当文档里有）
```

调用前按项目约定确定 `--name`：**最终交付文件名带日期**（MMDD 或 MM-DD，如 `学员手册_0915`）。
多份文档「分开存放」= 每份一个独立子目录。

## 脚本已处理的飞书专有结构

| 原始形态 | 转换结果 |
|-|-|
| `<title>X</title>` | 移除（HTML 元数据，markdown 里无意义；标题由文件名体现） |
| `<figure><source name="a.mp4" token="T"/></figure>` | 下载到 `attachments/` → `[a.mp4](attachments/a.mp4)` |
| `![](https://feishu.cn/file/T)` | 下载到 `images/` → `![](images/NN_上下文.png)` |
| `<grid><column>...` | 退化为顺序内容，多栏内容各自成行（否则会粘连） |
| `<cite doc-id="T" file-type="wiki" title="X">` | `[X](https://my.feishu.cn/wiki/T)` |
| `<table><tr><td rowspan=...>` | 标准 markdown 表格，rowspan/colspan 展开为重复值 |
| `<p>` `</p>` `<blockquote>` | 去包裹标签，保留内容 |

## 必须绕开的坑

1. **bash PATH 在本机会失效**（`dirname: command not found` → ls/find/grep 全挂）。
   每条命令前显式导出：
   ```bash
   export PATH="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages:/c/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Windows/System32:/c/Windows:$PATH"
   ```
   另外 PowerShell 工具在本机不返回 stdout，统一走 Bash。

2. **Windows 下 `lark-cli` 不能被 subprocess 直接执行**（它是 `.cmd`）。
   脚本已内置 `lark_prefix()`：优先用 `node + node_modules/@larksuite/cli/scripts/run.js`。
   自己写子进程调用时不要直接传 `"lark-cli"`。

3. **图片扩展名会丢**。`docs +media-download --output <无扩展名路径>` 由工具按
   Content-Type 补扩展名；但如果文件名里本身带 `.`（例如上下文命名得到
   `2.新建画布创作`），工具会误判「已有扩展名」而**不补**，落盘得到无扩展名文件。
   必须按文件头（PNG `89504e47` / JPEG `ffd8ff` / GIF / RIFF-WEBP）嗅探后补全 —— 
   脚本的 `ensure_ext()` 已实现，实测同一文档里会混有 png 和 jpg。

4. **下载工具的返回值不可全信**：它可能返回 `"output file already exists"` 之类的
   非致命错误，但文件其实已落盘。判定标准是**文件是否存在**，不要按返回码提前退出。

5. **`/wiki/` 链接**由 `docs +fetch` 自动解析；`<cite>` 里的 `doc-id` 同时支持
   `/wiki/<id>` 和 `/docx/<id>` 两种 URL，可直接用 wiki 形式回链。

## 验收清单

导出后逐项确认，全部通过才算完成：

- [ ] 残留扫描为空：`grep -n 'feishu.cn/file\|<title>\|<source\|<figure\|<grid\|<column\|<cite\|<p>\|<table>' <md>`
- [ ] 图片无扩展名数 = 0：`ls images | grep -vc '\.\(png\|jpg\|jpeg\|gif\|webp\)$'`
- [ ] md 中每个相对引用在磁盘上都存在（图片数、附件数对得上）
- [ ] 正文与飞书源一致（只动结构、不动文字）

## 常见规模参考

- 纯文本文档：几秒完成，产出 1 个 md（+ 少量图）
- 图文操作手册：27 张图 + 6 个附件约 63 MB，下载约 50 秒 —— 
  用 `run_in_background` 跑，避免前台等待
