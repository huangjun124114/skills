# -*- coding: utf-8 -*-
"""线上站点资源完整性核验：逐一下载 index.html 引用的全部图片，校验 200 / 字节数 / JPEG 头。"""
import io
import os
import re
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

BASE = 'https://day2-ai-marketing-notes.app.workbuddy.host/'
HERE = CFG.work
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LOCAL = os.path.join(ROOT, '输出', 'WorkBuddy实战落地营_Day2共享版_0915')
MIRROR = os.path.join(HERE, 'live_check')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch(rel):
    url = BASE + rel.replace('\\', '/')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
            data = r.read()
            return rel, r.status, len(data), data
    except Exception as e:  # noqa: BLE001
        return rel, getattr(e, 'code', 0), 0, b''


def main():
    idx = io.open(os.path.join(MIRROR, 'index.html'), encoding='utf-8').read()
    refs = sorted(set(re.findall(r'images/(?:t/)?[pm]\d+\.jpg', idx)))
    print('线上 index.html 引用图片（去重）：%d 个' % len(refs))

    local_full = len([f for f in os.listdir(os.path.join(LOCAL, 'images'))
                      if f.lower().endswith('.jpg')])
    local_thumb = len([f for f in os.listdir(os.path.join(LOCAL, 'images', 't'))
                       if f.lower().endswith('.jpg')])
    print('本地副本 images/ ：大图 %d + 缩略图 %d = %d' % (local_full, local_thumb,
                                                        local_full + local_thumb))

    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(fetch, refs))

    ok = [r for r in results if r[1] == 200]
    bad = [r for r in results if r[1] != 200]
    print('HTTP 200        ：%d / %d' % (len(ok), len(results)))
    if bad:
        for r in bad:
            print('   [FAIL] %s -> http=%s' % (r[0], r[1]))

    # JPEG 头 + 与本地副本字节一致性
    notjpeg, mismatch, same = [], [], 0
    for rel, status, size, data in ok:
        if not data.startswith(b'\xff\xd8\xff'):
            notjpeg.append(rel)
            continue
        lp = os.path.join(LOCAL, rel.replace('/', os.sep))
        if os.path.exists(lp):
            lb = open(lp, 'rb').read()
            if lb == data:
                same += 1
            else:
                mismatch.append('%s 线上 %d / 本地 %d' % (rel, len(data), len(lb)))
    print('JPEG 头正常     ：%d' % (len(ok) - len(notjpeg)))
    if notjpeg:
        print('   非 JPEG：%s' % ', '.join(notjpeg[:5]))
    print('与本地逐字节相同：%d' % same)
    if mismatch:
        print('   [WARN] 不一致 %d 个：' % len(mismatch))
        for m in mismatch[:8]:
            print('     ' + m)

    # 404 行为
    r = fetch('images/definitely-not-exist-xyz.jpg')
    print('不存在路径      ：http=%s（预期 404）' % r[1])

    # 镜像落盘（供离线渲染验证）
    for rel, status, size, data in ok:
        if '/t/' in rel and 'images/t/' not in rel:
            pass
        d = os.path.join(MIRROR, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d, 'wb').write(data)
    print('镜像已落盘      ：%s' % MIRROR)

    verdict = (not bad) and (not notjpeg) and (not mismatch) and r[1] == 404
    print('\nVERDICT %s' % ('PASS' if verdict else 'FAIL'))
    return 0 if verdict else 1


if __name__ == '__main__':
    sys.exit(main())
