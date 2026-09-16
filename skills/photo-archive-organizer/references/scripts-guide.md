# 脚本总表（scripts-guide）

调用任何脚本前查阅本文件。所有脚本默认 **dry-run**，加 `--apply` 才写盘；路径全部参数化，不硬编码任何项目目录。

## 通用约定

| 约定 | 说明 |
|---|---|
| `--apply` | 缺省为干跑，只打印计划；加后才真正执行 |
| 路径 | 全部通过参数传入，脚本内不含任何绝对路径 |
| 并行 | `--chunk`（默认 50）与 `--workers`（默认 8）控制分片；并行失败自动转串行 |
| 退出码 | 0 = 成功；非 0 = 有失败项或闸门未通过，可直接在流程中判断 |
| HEIC | worker 内惰性调用 `ensure_heif()`，子进程不会因 spawn 丢失注册 |

## 模式 B 脚本（P3–P8）

| 脚本 | 步骤 | 主要参数 |
|---|---|---|
| `date_infer.py` | P4 | `--root --out [--folder-first] [--min-loo 0.95] [--min-ym --max-ym]` |
| `extract_features.py` | P5–P6 | `--dated --out --visual-out [--chunk 50] [--workers 8]` |
| `cluster_events.py` | P5 | `--feats --visual --out [--gap 2] [--target 70] [--maxk 4] [--alpha 2.0] [--min-size 5]` |
| `train_classifier.py` | 语义清理 | `--positive --negative --score --out --threshold`（**阈值必填**）`[--force]` |
| `make_contact_sheet.py` | 语义清理 | `--scored scores.json --out review.html [--top N] [--thumb 320] [--mark 0.7] [--only-marked] [--embed-full]` |
| `verify_gates.py` | 检验 | `--archive [--quarantine] [--backup] [--delete-list] [--expected-remove] [--expected-keep] [--cap 80] [--min-files 3] [--json]` |
| `safe_delete.py` | P8 | `move --list --quarantine` / `purge --list [--batch 50]` |

### 典型链路

```bash
python scripts/date_infer.py        --root SRC --out dated.json --apply
python scripts/extract_features.py  --dated dated.json --out feats.json \
                                    --visual-out visual.npy --apply
python scripts/cluster_events.py    --feats feats.json --visual visual.npy \
                                    --out events.json --apply
#   ... 人工命名事件、按 events.json 写入归档区 ...
python scripts/train_classifier.py  --positive ARCHIVE --negative QUARANTINE \
                                    --score feats.json --out scores.json \
                                    --threshold 0.55 --apply
python scripts/make_contact_sheet.py --scored scores.json --out review.html \
                                    --mark 0.55 --only-marked --apply   # 人工复核
python scripts/verify_gates.py      --archive ARCHIVE --quarantine Q --backup BAK \
                                    --delete-list del.txt --expected-remove 116 --cap 80
python scripts/safe_delete.py move  --list del.txt --quarantine Q --apply
```

最小可行路径（跳过语义清理与判别器）见 `SKILL.md` 第 3.1 节。

## 模式 A 脚本（迁移合并链路）

对应 `SKILL.md` 第 3 章「模式 A 附加流程」的 A1–A6。

| 脚本 | 步骤 | 用途 | 关键参数 |
|---|---|---|---|
| `scan.py` | — | 只读概览 + 计划 | `--root` |
| `backup.py` | P2 | 安全备份 | `--src --dst` |
| `migrate.py` | A1 | 合并 + 自动日期推断 | `--root --merge-map --birth-years --apply` |
| `fix_ext.py` | A2 | magic byte 扩展名修复 | `--root --apply` |
| `normalize_names.py` | A3 | 文件夹名归一化 | `--root --apply` |
| `organize_loose.py` | A4 | 根目录松散文件归组 | `--root --target --apply` |
| `analyze_pending.py` | A5 | 待溯源线索 + 分析表 | `--root --pending --report` |
| `apply_pending.py` | A5 | 按用户建议执行 | `--root --map --apply` |
| `verify.py` | A6 | md5 守恒 + 结构检查 | `--root [--backup]` |

## 共用基础库 `_common.py`

| 类别 | 函数 |
|---|---|
| 模式 A | `magic_ext`、`video_date`、`exif_date`、`parse_filename_date`、`parse_folder_date`、`parse_age`、`infer_date` |
| 模式 B | `exif_date_full`、`parse_ymd`、`parse_ts13`、`xmp_date`、`seq_of`、`loo_validate`、`quality_score`、`chunked_pool` |
| 共用 | `ensure_pillow`、`ensure_heif`、`md5_file`、`iter_files`、`print_affected`、`norm`（在 `verify_gates.py` 内） |

## 各脚本的失败处理

| 脚本 | 失败时 |
|---|---|
| `date_infer.py` | 无法推断日期的文件标记 `src=NONE`，**不猜测**；由调用方排除 |
| `extract_features.py` | 单张失败不影响其余，末尾打印 FAIL 清单 |
| `cluster_events.py` | `--feats` 与 `--visual` 行数不匹配时直接报错退出 |
| `train_classifier.py` | 样本不足（正/负 < 20）报错；AUC < 0.65 中止（`--force` 可覆盖） |
| `verify_gates.py` | 任一闸门未通过 → 退出码 1，并在报告中列出失败项 |
| `safe_delete.py` | 清单含 CRLF 直接拒绝；文件不存在时跳过并报告 |
| `make_contact_sheet.py` | 单张缩略图失败跳过，不中断整页 |
