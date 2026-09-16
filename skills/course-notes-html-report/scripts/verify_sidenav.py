# -*- coding: utf-8 -*-
"""
证明「不修改内容、不覆盖当前版本」：
  A. 主报告 index.html 未被改动（与侧栏版中的正文逐字节比对）
  B. 侧栏版对主报告只做了「追加」：style 块是前缀式追加，正文 .wrap 区块完全一致
  C. 侧栏版自身仍是纯静态（无外部资源、无网络请求）
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
OUTDIR = CFG.report_dir
A = os.path.join(OUTDIR, 'index.html')            # 原版
B = os.path.join(OUTDIR, os.path.basename(CFG.sidenav_name()))  # 侧栏版

fails = []


def check(name, ok, detail=''):
    print('  [%s] %-34s %s' % ('OK  ' if ok else 'FAIL', name, detail))
    if not ok:
        fails.append(name)


def wrap_block(t):
    """取 <div class="wrap"> 起点 → </body> 前的正文区块"""
    i = t.find('<div class="wrap">')
    j = t.rfind('</body>')
    return t[i:j]


def main():
    a = io.open(A, encoding='utf-8').read()
    b = io.open(B, encoding='utf-8').read()

    print('== A. 正文区块逐字节比对 ==')
    wa = wrap_block(a)
    wb = wrap_block(b)
    # 侧栏版在 </body> 前多插了一段侧栏脚本，去掉它再比
    m = re.search(r'<script>\s*/\* =+\s*\n\s*v2：左侧常驻导航交互[\s\S]*?</script>\s*$', wb)
    if m:
        wb_trim = wb[:m.start()].rstrip() + '\n'
    else:
        wb_trim = wb
    check('正文区块长度一致', len(wa) == len(wb_trim),
          '原版=%d 侧栏版=%d 差=%d' % (len(wa), len(wb_trim), len(wb_trim) - len(wa)))
    check('正文区块内容完全相同', wa == wb_trim)
    if wa != wb_trim:
        for k in range(min(len(wa), len(wb_trim))):
            if wa[k] != wb_trim[k]:
                print('      首个差异 @%d: ...%r ... vs ...%r ...'
                      % (k, wa[k - 60:k + 60], wb_trim[k - 60:k + 60]))
                break

    print('\n== B. 只做「追加」而非「改写」 ==')
    # style 块：原版 style 的尾部内容应原样出现在侧栏版 style 中
    sa = re.search(r'<style>([\s\S]*?)</style>', a).group(1)
    sb = re.search(r'<style>([\s\S]*?)</style>', b).group(1)
    check('原 style 块完整保留', sb.startswith(sa.rstrip()),
          '原 %d 字符 · 侧栏版 %d 字符（+%d）' % (len(sa), len(sb), len(sb) - len(sa)))
    check('侧栏样式为纯追加', len(sb) > len(sa) and sb.startswith(sa.rstrip()))

    # body 标签变化
    check('body 仅加 class/id', '<body class="has-side" id="top">' in b and '<body>' in a)

    # section / 组件计数一致
    for pat, label in [(r'<section id="s\d+"', 'section 数'),
                       (r'<div class="quote"', '老师原话'),
                       (r'<div class="quote d"', '课堂数据'),
                       (r'<div class="mine">', '我的总结'),
                       (r'<div class="asset">', '可复用资产'),
                       (r'<div class="kfig">', '重建框架'),
                       (r'<pre class="prompt">', 'Prompt 块'),
                       (r'<div class="shot">', '照片块'),
                       (r'<a href="images/', '大图引用')]:
        na, nb = len(re.findall(pat, a)), len(re.findall(pat, b))
        check(label + '一致', na == nb, '%d / %d' % (na, nb))

    print('\n== C. 侧栏版仍为纯静态 ==')
    ext = (re.findall(r'<script[^>]*\bsrc\s*=\s*["\']https?://', b)
           + re.findall(r'<link[^>]*\bhref\s*=\s*["\']https?://', b)
           + re.findall(r'\bsrc\s*=\s*["\']https?://', b)
           + re.findall(r'@import\s+(?:url\()?["\']?https?://', b))
    check('无外部资源加载', len(ext) == 0)
    check('无 fetch/XHR', len(re.findall(r'fetch\(|XMLHttpRequest', b)) == 0)
    check('无 CDN 域名', not re.search(r'cdn\.|unpkg|jsdelivr|googleapis|fonts\.', b))
    check('图片全为相对路径', len(re.findall(r'src="images/', b)) > 0
          and len(re.findall(r'src="https?://', b)) == 0)
    check('原版文件未被覆盖', os.path.getsize(A) == 396067,
          'index.html = %d 字节' % os.path.getsize(A))

    print('\n== 汇总 ==')
    if fails:
        print('  失败 %d 项：%s' % (len(fails), '、'.join(fails)))
        return 1
    print('  全部通过：正文零改动，原版未被覆盖，侧栏版纯静态可离线打开')
    return 0


if __name__ == '__main__':
    sys.exit(main())
