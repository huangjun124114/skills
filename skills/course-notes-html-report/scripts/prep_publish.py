# -*- coding: utf-8 -*-
"""准备「共享发布版」目录。

来源：输出/WorkBuddy实战落地营_完整课程要点_0915/index_左侧导航版_0915.html（左侧常驻导航版）
去向：输出/WorkBuddy实战落地营_Day2共享版_0915/
       ├─ index.html   ← 与来源逐字节相同，仅在 </head> 前插入 Open Graph 元信息（不可见）
       └─ images/      ← 132 张大图 + 132 张缩略图（原样复制）

设计原则：
  * 只做「复制 + 插入不可见的 meta」，正文一个字不改；
  * 不触碰原交付目录（index.html / 导航版 / md 全程只读）；
  * index.html 作为入口名，静态托管可自动识别。
"""
import io
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
SRC_DIR = CFG.report_dir
DST_DIR = CFG.publish_dir()
SRC_HTML = os.path.join(SRC_DIR, os.path.basename(CFG.sidenav_name()))

OG = (
    '<meta name="description" content="混沌·大湾区 AI 先锋计划（WorkBuddy AI 实战落地营 深圳场）'
    '9/15 上午场完整课程要点：17 章 · 上下半场 · 110 张课件照片 · 12 条可复用 Prompt。">\n'
    '<meta property="og:type" content="article">\n'
    '<meta property="og:title" content="WorkBuddy AI 实战落地营 · 完整课程要点（9/15 上午场）">\n'
    '<meta property="og:description" content="AI + 整合营销与 GTM 策略 · 爆款视频复刻与 Meme 营销：'
    '17 章完整还原，含老师原话、课堂数据、我的总结与可复用资产。">\n'
    '<meta property="og:locale" content="zh_CN">\n'
)


def main():
    if not os.path.exists(SRC_HTML):
        sys.exit('缺少源文件：%s' % SRC_HTML)

    src = io.open(SRC_HTML, encoding='utf-8').read()

    # ---- 1. 插入 OG（只插在 </head> 之前，正文零改动）----
    marker = '</head>'
    assert src.count(marker) == 1, '</head> 不唯一，停手'
    out = src.replace(marker, OG + marker, 1)

    # ---- 2. 建目录 ----
    os.makedirs(DST_DIR, exist_ok=True)
    dst_html = os.path.join(DST_DIR, 'index.html')
    io.open(dst_html, 'w', encoding='utf-8', newline='').write(out)

    # ---- 3. 复制 images ----
    src_img = os.path.join(SRC_DIR, 'images')
    dst_img = os.path.join(DST_DIR, 'images')
    if os.path.isdir(dst_img):
        shutil.rmtree(dst_img)
    shutil.copytree(src_img, dst_img)

    # ---- 4. 自检 ----
    chk = io.open(dst_html, encoding='utf-8').read()
    print('== 发布副本自检 ==')
    print('  index.html        %8.1f KB' % (os.path.getsize(dst_html) / 1024))
    print('  与原版差异字符数   %d（应等于插入的 OG 长度 %d）' % (len(chk) - len(src), len(OG)))
    print('  差异位置含 og:     %s' % ('是' if OG.split('\n')[0] in chk else '否'))
    # 正文区块逐字节比对
    a = chk[chk.find('<div class="wrap">'):]
    b = src[src.find('<div class="wrap">'):]
    print('  .wrap 正文区块一致 %s（%d 字符）' % ('是' if a == b else '否', len(b)))

    n_full = len([f for f in os.listdir(dst_img) if f.lower().endswith('.jpg')])
    n_th = len([f for f in os.listdir(os.path.join(dst_img, 't'))
                if f.lower().endswith('.jpg')])
    tot = sum(os.path.getsize(os.path.join(dst_img, f))
              for f in os.listdir(dst_img) if f.lower().endswith('.jpg'))
    tot_th = sum(os.path.getsize(os.path.join(dst_img, 't', f))
                 for f in os.listdir(os.path.join(dst_img, 't')))
    print('  images/           大图 %d 张 / 缩略图 %d 张' % (n_full, n_th))
    print('  体积              大图 %.2f MB + 缩略图 %.2f MB = %.2f MB'
          % (tot / 1048576, tot_th / 1048576, (tot + tot_th) / 1048576))

    # 资源引用完整性：HTML 里引用的每张图都必须存在于副本
    refs = set(re.findall(r'images/(t/)?([pm]\d+)\.jpg', chk))
    miss = []
    for sub, code in refs:
        p = os.path.join(dst_img, 't' if sub else '', code + '.jpg')
        if not os.path.exists(p):
            miss.append(p)
    print('  引用图片 %d 个，缺失 %d 个 %s' % (len(refs), len(miss), miss[:5]))
    print('  外部 http(s) 依赖  %d 个' % len(re.findall(r'(?:src|href)="https?://', chk)))

    print('\n发布目录：%s' % DST_DIR)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
