# -*- coding: utf-8 -*-
"""课件照片与手册截图的精选 / 压缩 / 归档。

产出（目录式交付的图片资源）：
  <报告目录>/images/pNNN.jpg      1400px 大图（灯箱用）
  <报告目录>/images/t/pNNN.jpg     560px 缩略图（网格 / 相册用）
  <报告目录>/images/mNNN.jpg       手册截图
  <中间产物>/image_map.json        映射表（构建 / 相册 / 验证的唯一数据源）

用法：
  python prep_images.py --root <项目根> --task <任务名> --report <报告目录名> \\
      --shots-src "<原始输入>/DayN/dayN" \\
      --manual-src "<原始输入>/DayN/<手册目录>/images"

剔除原则：同一页 PPT 的重复拍摄，保留最清晰的一张。
"""
import io
import json
import os
import re
from PIL import Image

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
SRC_SHOT = CFG.shots_src
SRC_MAN = CFG.manual_src
OUT = CFG.report_dir
IMG = CFG.images
THUMB = CFG.thumbs
HERE = CFG.work

# ============================================================
#  同页重复拍摄 → 剔除（保留最清晰的一张）
#  逐条用注释注明剔除理由，例如：
#      'IMG_20260915_104325.jpg',  # 与 102418「爆款的核心法则：以暴制暴」同页
#  注意：剔除不是丢弃——原图仍在 原始输入/（只读）。重复张是遮挡时的补字备份。
# ============================================================
DROP = set()

FULL_W, FULL_Q = 1400, 78
THUMB_W, THUMB_Q = 560, 72


def save_pair(im, base):
    """同时输出大图与缩略图，返回 (full_kb, thumb_kb)。"""
    im = im.convert('RGB')
    o = im
    if im.width > FULL_W:
        o = im.resize((FULL_W, round(im.height * FULL_W / im.width)), Image.LANCZOS)
    fp = os.path.join(IMG, base + '.jpg')
    o.save(fp, 'JPEG', quality=FULL_Q, optimize=True, progressive=True)
    t = im
    if im.width > THUMB_W:
        t = im.resize((THUMB_W, round(im.height * THUMB_W / im.width)), Image.LANCZOS)
    tp = os.path.join(THUMB, base + '.jpg')
    t.save(tp, 'JPEG', quality=THUMB_Q, optimize=True, progressive=True)
    return os.path.getsize(fp) / 1024, os.path.getsize(tp) / 1024, o.size


def main():
    if not SRC_SHOT or not os.path.isdir(SRC_SHOT):
        print('!! 未指定课件照片源目录。请加参数：')
        print('   --shots-src "<项目根>/原始输入/<DayN>/<照片目录>"')
        return 1
    print('源目录（课件照片）: %s' % SRC_SHOT)
    print('源目录（手册截图）: %s' % (SRC_MAN or '(未指定，跳过)'))
    print('报告目录          : %s' % OUT)

    for d in (IMG, THUMB):
        os.makedirs(d, exist_ok=True)

    mapping = {'shots': [], 'manual': []}

    # ---------- 一、课件照片 ----------
    fs = sorted(f for f in os.listdir(SRC_SHOT) if f.lower().endswith('.jpg'))
    kept = [f for f in fs if f not in DROP]
    print('课件照片: 源 %d 张 → 剔除 %d 张 → 保留 %d 张' % (len(fs), len(DROP), len(kept)))
    tot_f = tot_t = 0
    for i, f in enumerate(kept, 1):
        code = 'p%03d' % i
        im = Image.open(os.path.join(SRC_SHOT, f))
        fk, tk, sz = save_pair(im, code)
        tot_f += fk
        tot_t += tk
        hhmmss = re.search(r'_(\d{6})\.jpg', f).group(1)
        mapping['shots'].append({
            'code': code, 'src': f, 'time': '%s:%s:%s' % (hhmmss[:2], hhmmss[2:4], hhmmss[4:]),
            'w': sz[0], 'h': sz[1],
        })
        if i % 20 == 0 or i == len(kept):
            print('   ... %d/%d' % (i, len(kept)))
    print('  大图合计 %.1f MB，缩略图合计 %.1f MB' % (tot_f / 1024, tot_t / 1024))

    # ---------- 二、操作手册截图 ----------
    # 源目录里每个截图存在两份（带扩展名 / 不带扩展名，内容完全相同）→ 按编号前缀去重
    if os.path.isdir(SRC_MAN):
        raw = sorted(os.listdir(SRC_MAN))
        byno = {}
        for f in raw:
            m = re.match(r'^(\d+)_', f)
            if not m:
                continue
            k = m.group(1)
            # 优先保留带扩展名的
            if k not in byno or f.lower().endswith(('.png', '.jpg', '.jpeg')):
                byno[k] = f
        ms = [byno[k] for k in sorted(byno)]
        print('\n手册截图: 源 %d 个文件 → 按编号去重后 %d 张' % (len(raw), len(ms)))
        tot_f2 = 0
        for i, f in enumerate(ms, 1):
            code = 'm%03d' % i
            m = re.match(r'^(\d+)_(.*)$', f)
            label = m.group(2) if m else f
            im = Image.open(os.path.join(SRC_MAN, f))
            fk, tk, sz = save_pair(im, code)
            tot_f2 += fk
            mapping['manual'].append({
                'code': code, 'src': f, 'label': label, 'w': sz[0], 'h': sz[1],
            })
        print('  大图合计 %.1f MB' % (tot_f2 / 1024))

    with io.open(os.path.join(HERE, 'image_map.json'), 'w', encoding='utf-8') as fp:
        json.dump(mapping, fp, ensure_ascii=False, indent=1)
    print('\n映射表 → image_map.json')
    print('图片目录 → %s' % IMG)
    n = len(os.listdir(IMG)) - 1  # 减去 t 子目录
    print('总计: 大图 %d 张, 缩略图 %d 张' % (n, len(os.listdir(THUMB))))


if __name__ == '__main__':
    main()
