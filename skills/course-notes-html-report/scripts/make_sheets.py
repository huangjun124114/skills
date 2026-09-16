import os, json, math
from PIL import Image, ImageDraw, ImageFont

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import CFG          # noqa: E402  统一路径配置（--root/--task/--report）

ROOT = CFG.root
IMG = CFG.images
OUT = CFG.sheets
os.makedirs(OUT, exist_ok=True)

amap = json.load(open(os.path.join(ROOT,'中间产物','course_report_day2','image_map.json'), encoding='utf-8'))
shots = amap['shots']

TILE_W = 470
TILE_H = int(TILE_W * 1050 / 1400)
COLS, ROWS = 3, 3
PAD = 6
LABEL_H = 22
PER = COLS * ROWS

try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
except Exception:
    font = ImageFont.load_default()

n = len(shots)
sheets = math.ceil(n / PER)
for s in range(sheets):
    chunk = shots[s*PER:(s+1)*PER]
    W = COLS*(TILE_W+PAD)+PAD
    H = ROWS*(TILE_H+LABEL_H+PAD)+PAD
    canvas = Image.new('RGB', (W, H), (18,18,20))
    d = ImageDraw.Draw(canvas)
    for i, it in enumerate(chunk):
        r, c = divmod(i, COLS)
        x = PAD + c*(TILE_W+PAD)
        y = PAD + r*(TILE_H+LABEL_H+PAD)
        p = os.path.join(IMG, it['code']+'.jpg')
        try:
            im = Image.open(p).convert('RGB').resize((TILE_W, TILE_H), Image.LANCZOS)
        except Exception as e:
            print('ERR', p, e); continue
        canvas.paste(im, (x, y))
        d.rectangle([x, y+TILE_H, x+TILE_W, y+TILE_H+LABEL_H], fill=(240,196,88))
        d.text((x+5, y+TILE_H+2), f"{it['code']}  {it['time']}", fill=(20,20,20), font=font)
    op = os.path.join(OUT, f"sheet_{s+1:02d}.jpg")
    canvas.save(op, 'JPEG', quality=82)
    codes = ','.join(x['code'] for x in chunk)
    print(f"sheet_{s+1:02d}.jpg  {W}x{H}  {codes}")
