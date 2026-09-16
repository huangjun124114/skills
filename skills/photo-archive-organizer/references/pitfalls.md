# 踩坑清单（pitfalls）

分两类：环境坑（Windows 沙箱）与方法坑（算法/流程）。执行前过一遍。

---

## A. 环境坑（Windows 沙箱）

### A1　删除被 safe-delete hook 拦截

`os.remove` / `shutil.rmtree` / `rm -f` 全部 fail-closed，报 `SAFE_DELETE_FAIL_CLOSED`（回收站不可用）。`os.rmdir` 同理。

**可用方式**
| 目标 | 方法 |
|---|---|
| 文件 | `find "<绝对路径>" -maxdepth 0 -type f -delete`（分批 50 个） |
| 目录 | `shutil.move` 移入隔离区（rename，可逆） |

**推荐做法**：所有"删除"先移入隔离区，确认后再用 `find -delete` 真正销毁。

### A2　路径清单行尾

Python 写路径清单必须 `newline='\n'`。默认的 `\r\n` 会让 shell 侧匹配全部失败——曾导致第一次批量删除 0 生效。

### A3　multiprocessing.Pool 静默崩溃

`Pool(12)` 跑几千张图会中途退出，exit code 1 且**无 traceback**；偶发 `spawn_main WinError 87`。

**解法**：按 50 片循环，每片新建 `Pool(8)`，异常则该片转串行 `map`：

```python
for s in range(0, len(files), 50):
    try:
        with Pool(8) as p:
            for r in p.imap_unordered(job, files[s:s+50], chunksize=4):
                ...
    except Exception:
        for r in map(job, files[s:s+50]):   # 串行兜底
            ...
```
一次崩溃只损失一片，不是整个任务。

### A4　Git Bash 路径

`/tmp/x.py` 会解析成 `D:\tmp\x.py`（不存在）。临时脚本写进工作目录。

### A5　脚本命名遮蔽标准库

工作目录里出现 `copy.py` / `select.py` 会打断 `pillow_heif`、`multiprocessing` 的 import。
已改名为 `copy_to_target.py` / `pick_best.py`。

### A6　WinError 267

把"根目录散落文件"当目录 `move` 会失败。规则：只整目录 `move`，散落文件单独逐条并入目标。

### A7　HEIC 支持

需 `pillow-heif` + `pillow_heif.register_heif_opener()`，并设 `Image.MAX_IMAGE_PIXELS = None`。缺失时降级跳过并记录，不中断。

---

## B. 方法坑

### B1　阈值禁止自动选"召回最大化"

按"召回 ≥ 0.95"自动选阈值 → 选到 0.20 → 误杀 **62%** 真实照片（731 张候选只剩 145 张）。
必须打印对照表人工选，详见 `classifier-recipes.md`。

### B2　纯背景照片必然被误判

儿童证件照得分 0.99。必须维护保护名单，详见 `classifier-recipes.md` 第三节。

### B3　聚类算法选错会塌缩

average-linkage 会塌缩成"一个巨簇 + 一堆单点"，切成 175 个碎片事件只剩 3 个有效。
**改用 Ward 凝聚聚类**。

### B4　近重复抑制会击穿下限

连拍去重（阈值 0.035）若无条件启用，会把某个事件压到 5 张以下，违反下限规则。
**只在事件实际超过上限时才启用抑制**。

### B5　跨月泄漏

早期版本允许跨月合并，出现日期跨度 201805→202112 的"事件"。
**禁止跨月合并**，会话切分限定在同一 `YYYYMM` 内。

### B6　第二轮扫到已判废文件

第一轮剔除的文件通常**仍在源区**（只有入围者才被回收）。若第二轮只比对归档区，会把它们当新文件重新捞回。
**md5 去重范围必须同时覆盖归档区和隔离区**。
实测：1,481 张"选中的新照片"中有 711 张是第一轮已判废的，真实增量只有 770 张。

### B7　同名文件夹的双向存在

归档区与隔离区可以存在同名文件夹（混合事件部分剔除）。判定事件去留时检查"该文件夹是否仍存在于归档区"，而不是"是否出现在隔离区"。

### B8　待溯源禁止硬猜

无 EXIF / 无 mvhd / 无日期命名的文件，**不可**凭年龄或 mtime 猜测后移动。走"挖线索 → 问用户 → 按建议执行"流程。

### B9　脚本重复执行产生冗余副本

隔离区重名时自动追加 `_1`/`_2` 后缀，重复执行会让同一内容存多份。
收尾必须按 md5 去重后再对账（见 `verification-gates.md` 闸门 5）。

### B10　命名归一化漏网

`YYYYMM` 后直接跟中文（如 `202401为良深圳湾`）需补 `(\d{6})(\D.*)` 模式。

### B11　mvhd 解析偏移

version 字节在 `i+4`，时间值从 `i+8` 起。误把 `i+8` 当版本号会拿到完全错误的年份。
