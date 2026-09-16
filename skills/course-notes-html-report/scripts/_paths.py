# -*- coding: utf-8 -*-
"""课程要点报告脚本族的共用路径配置。

三种用法（优先级从低到高）：
  1) 改本文件的 DEFAULT_* 常量
  2) 环境变量：CR_ROOT / CR_WORK / CR_TASK / CR_REPORT  / CR_OUT
  3) 命令行：  --root <项目根>  --work <中间产物目录>  --task <任务名>
               --report <输出报告目录名>  --out <输出根>

典型调用（脚本自己会解析，命令行参数可混在原有参数里）：

    python build_report.py --root "D:/work/混沌训练营" \\
        --task course_report_day2 \\
        --report "WorkBuddy实战落地营_完整课程要点_0915"

不传参数时的自动探测：
  - root   : 从当前目录向上找「含 输出/ 或 原始输入/ 的目录」
  - task   : 找 <root>/中间产物 下含 p1.html 的目录
  - report : 找 <root>/输出 下唯一（或最近修改）的目录
"""
import argparse
import os
import re
import sys

DEFAULT_ROOT = ''
DEFAULT_TASK = ''
DEFAULT_REPORT = ''
DEFAULT_OUT = '输出'


def _find_root(start=None):
    """向上找含 原始输入/ 或 输出/ 的祖先目录。"""
    d = os.path.abspath(start or os.getcwd())
    for _ in range(6):
        if os.path.isdir(os.path.join(d, '原始输入')) or os.path.isdir(os.path.join(d, '输出')):
            return d
        p = os.path.dirname(d)
        if p == d:
            break
        d = p
    return os.path.abspath(start or os.getcwd())


def _find_task(root):
    """找 <root>/中间产物 下含 p1.html 的目录。"""
    base = os.path.join(root, '中间产物')
    if not os.path.isdir(base):
        return ''
    cands = []
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, 'p1.html')):
            cands.append(d)
    if not cands:
        return ''
    if len(cands) == 1:
        return cands[0]
    # 多个 → 取 p1.html 最近修改的
    return max(cands, key=lambda d: os.path.getmtime(os.path.join(base, d, 'p1.html')))


def _find_report(out_root):
    """找 <out_root> 下唯一（或最近修改）的报告目录。"""
    if not os.path.isdir(out_root):
        return ''
    cands = [d for d in sorted(os.listdir(out_root))
             if os.path.isdir(os.path.join(out_root, d))
             and (os.path.exists(os.path.join(out_root, d, 'index.html'))
                  or os.path.exists(os.path.join(out_root, d, '交付说明.md')))]
    if not cands:
        return ''
    if len(cands) == 1:
        return cands[0]
    best = max(cands, key=lambda d: os.path.getmtime(os.path.join(out_root, d)))
    sys.stderr.write('[提示] 输出目录下有 %d 个候选报告目录，已选最近修改的「%s」。\n'
                     '       若不是目标目录，请显式指定 --report <目录名>。\n' % (len(cands), best))
    return best


def _parse():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--root', default=os.environ.get('CR_ROOT', DEFAULT_ROOT))
    ap.add_argument('--work', default=os.environ.get('CR_WORK', ''))
    ap.add_argument('--task', default=os.environ.get('CR_TASK', DEFAULT_TASK))
    ap.add_argument('--report', default=os.environ.get('CR_REPORT', DEFAULT_REPORT))
    ap.add_argument('--out', default=os.environ.get('CR_OUT', DEFAULT_OUT))
    ap.add_argument('--shots-src', default=os.environ.get('CR_SHOTS_SRC', ''),
                    help='原始课件照片目录（prep_images 用）')
    ap.add_argument('--manual-src', default=os.environ.get('CR_MANUAL_SRC', ''),
                    help='原始手册截图目录（prep_images 用）')
    return ap.parse_known_args()[0]        # 未知参数交还原脚本


class _Cfg(object):
    def __init__(self):
        a = _parse()
        self.root = os.path.abspath(a.root or _find_root())
        self.out_root = a.out if os.path.isabs(a.out) else os.path.join(self.root, a.out)

        task = a.task or _find_task(self.root)
        self.work = os.path.abspath(a.work) if a.work else os.path.join(
            self.root, '中间产物', task or 'course_report')

        name = a.report or _find_report(self.out_root)
        self.report_name = name
        self.report_dir = name if os.path.isabs(name) else os.path.join(self.out_root, name)

        # 日期后缀（MMDD），从报告目录名尾部提取，用于派生版 / 归档版命名
        m = re.search(r'_(\d{3,4})$', os.path.basename(self.report_dir.rstrip('/\\')))
        self.date = m.group(1) if m else ''

        self.images = os.path.join(self.report_dir, 'images')
        self.thumbs = os.path.join(self.images, 't')
        self.shots_src = a.shots_src
        self.manual_src = a.manual_src
        self.mapfile = os.path.join(self.work, 'image_map.json')
        self.sheets = os.path.join(self.work, 'sheets')
        self.shots = os.path.join(self.work, 'shots')
        self.txt = os.path.join(self.work, 'txt')
        # Chart.js 可能放在中间产物根目录或任务目录
        for p in (os.path.join(self.work, 'chart.umd.min.js'),
                  os.path.join(self.root, '中间产物', 'chart.umd.min.js')):
            if os.path.exists(p):
                self.chartjs = p
                break
        else:
            self.chartjs = os.path.join(self.work, 'chart.umd.min.js')

    # ---------- 派生文件名约定 ----------
    def sidenav_name(self):
        """左侧导航版文件名（与主报告并存，不覆盖基线）。"""
        return self.dist('index_左侧导航版_%s.html' % self.date)

    def md_name(self):
        """Markdown 归档版文件名。"""
        return self.dist('课程要点_%s.md' % self.date)

    def readme_name(self):
        """交付说明文件名。"""
        return self.dist('交付说明_%s.md' % self.date)

    # ---------- 便捷 ----------
    def frag(self, *names):
        return [os.path.join(self.work, n) for n in names]

    def fragments(self):
        """按数字顺序返回 p1.html … pN.html 的绝对路径。"""
        if not os.path.isdir(self.work):
            return []
        fs = [f for f in os.listdir(self.work) if re.match(r'^p\d+\.html$', f)]
        fs.sort(key=lambda x: int(re.findall(r'\d+', x)[0]))
        return [os.path.join(self.work, f) for f in fs]

    def dist(self, filename):
        """交付目录下的文件路径（报告目录别名）。"""
        return os.path.join(self.report_dir, filename)

    def publish_dir(self, suffix='共享版'):
        """发布副本目录：输出/<报告名去掉日期>_<suffix>_<日期>/"""
        m = re.match(r'^(.*?)_(\d{3,4})$', self.report_name)
        if m:
            base, date = m.group(1), m.group(2)
        else:
            base, date = self.report_name, ''
        nm = '%s_%s_%s' % (base, suffix, date) if date else '%s_%s' % (base, suffix)
        return os.path.join(self.out_root, nm.replace('__', '_'))

    def show(self):
        print('== 路径配置 ==')
        print('  root      : %s' % self.root)
        print('  work      : %s' % self.work)
        print('  report    : %s' % self.report_dir)
        print('  images    : %s' % self.images)
        print('  chartjs   : %s' % ('%s%s' % (self.chartjs,
                                             '' if os.path.exists(self.chartjs) else '  (缺失)')))


CFG = _Cfg()

if __name__ == '__main__':
    CFG.show()
    fs = CFG.fragments()
    print('  分片      : %d 个  %s' % (len(fs), ' '.join(os.path.basename(f) for f in fs)))
