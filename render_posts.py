"""Render Frostclaw Software Instagram image posts and scheduling assets.

Usage: python render_posts.py
Requires Pillow. Everything runs locally; no accounts or API keys needed.
"""
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
from datetime import date, datetime, time, timedelta
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / 'content' / 'posts.json'
ASSETS = ROOT / 'assets'
CAPTIONS = ROOT / 'captions'
W, H = 1080, 1350
NAVY = (9, 19, 33)
PANEL = (18, 34, 52)
WHITE = (239, 246, 251)
MUTED = (166, 190, 206)
ACCENTS = {
    'QA BASICS': (85, 231, 201),
    'WORKFLOW': (181, 157, 249),
    'SPREADSHEETS': (250, 194, 112),
}


def font_path(bold=False):
    paths = []
    if os.name == 'nt':
        paths = [r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf',
                 r'C:\Windows\Fonts\segoeuib.ttf' if bold else r'C:\Windows\Fonts\segoeui.ttf']
    else:
        paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
    for p in paths:
        if Path(p).exists():
            return p
    return None


def ft(size, bold=False):
    p = font_path(bold)
    if p:
        return ImageFont.truetype(p, size=size)
    return ImageFont.load_default(size=size)


def wrap_text(draw, text, font, width):
    words = text.split()
    lines, current = [], ''
    for word in words:
        proposed = f'{current} {word}'.strip()
        if draw.textbbox((0,0), proposed, font=font)[2] <= width:
            current = proposed
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def ellipsize_to_width(draw, text, font, width):
    if draw.textbbox((0,0), text, font=font)[2] <= width:
        return text
    while len(text)>1 and draw.textbbox((0,0), text+'...', font=font)[2] > width:
        text = text[:-1]
    return text+'...'


def render_one(post, idx, total):
    accent = ACCENTS.get(post['pillar'], (85,231,201))
    im = Image.new('RGB', (W,H), NAVY)
    draw = ImageDraw.Draw(im)
    # Soft stripes and decorative geometry, original vector-only design.
    for y in range(H):
        t = y / H
        r = round(NAVY[0] + 10*t)
        g = round(NAVY[1] + 10*t)
        b = round(NAVY[2] + 16*t)
        draw.line((0,y,W,y), fill=(r,g,b))
    draw.ellipse((810,-160,1390,420), outline=tuple(int(x*.24+NAVY[i]*.76) for i,x in enumerate(accent)), width=3)
    draw.ellipse((-420,1040,200,1650), outline=(35,62,77), width=3)
    # Brand area
    draw.rounded_rectangle((70,69,116,115), radius=11, fill=accent)
    draw.text((84,73), 'F', font=ft(33,True), fill=NAVY)
    draw.text((133,70), 'FROSTCLAW SOFTWARE', font=ft(27,True), fill=WHITE)
    label = post['pillar']
    pillwidth = draw.textbbox((0,0),label,font=ft(21,True))[2] + 38
    draw.rounded_rectangle((W-70-pillwidth,73,W-70,115), radius=18, fill=(35,54,70))
    draw.text((W-70-pillwidth+19,81),label, font=ft(21,True), fill=accent)
    draw.line((70,144,1010,144),fill=(39,64,80),width=2)

    # Title
    title = post['title']
    fsize = 68
    while fsize >= 50:
        f = ft(fsize,True)
        lines = wrap_text(draw,title,f,925)
        if len(lines) <= 3:
            break
        fsize -= 2
    y = 205
    for line in lines:
        draw.text((70,y),line,font=f,fill=WHITE)
        y += fsize + 16
    hook_y = max(405, y+14)
    hook_font = ft(29,False)
    for line in wrap_text(draw,post['hook'],hook_font,940):
        draw.text((71,hook_y),line,font=hook_font,fill=MUTED)
        hook_y += 43

    # Tip card
    cardtop = 514
    cardbot = 1125
    draw.rounded_rectangle((70,cardtop,1010,cardbot),radius=30,fill=PANEL,outline=(53,82,98),width=2)
    steps = post['steps']
    n=len(steps)
    usable = 544
    row_h = usable // n
    for i,st in enumerate(steps):
        top = 544 + i*row_h
        draw.rounded_rectangle((99,top+6,164,top+71),radius=16,fill=tuple(int(NAVY[c]*.28+accent[c]*.72) for c in range(3)))
        draw.text((116,top+19),f'{i+1:02}',font=ft(25,True),fill=NAVY)
        label_font=ft(36,True)
        label = ellipsize_to_width(draw, st['label'], label_font, 779)
        draw.text((191,top+2),label,font=label_font,fill=WHITE)
        detail_font=ft(27)
        details=wrap_text(draw,st['detail'],detail_font,760)
        for j,ln in enumerate(details[:2]):
            draw.text((191,top+53+j*35),ln,font=detail_font,fill=MUTED)
        if i<n-1:
            draw.line((191,top+row_h-10,978,top+row_h-10),fill=(40,65,79),width=2)

    # Bottom takeaway
    tw=post['takeaway']
    takeaway_font=ft(25,True)
    lines=wrap_text(draw,tw,takeaway_font,917)
    ty=1175
    draw.rounded_rectangle((70,1158,1010,1258),radius=24,fill=(35,55,72))
    for line in lines[:2]:
        draw.text((97,ty),line,font=takeaway_font,fill=accent)
        ty+=32
    draw.text((70,1300),'FROSTCLAW SOFTWARE   /   SIMPLE IDEAS, BETTER WORK',font=ft(19,True),fill=MUTED)
    number=f'{idx:02} / {total:02}'
    numberwidth=draw.textbbox((0,0),number,font=ft(19,True))[2]
    draw.text((1010-numberwidth,1300),number,font=ft(19,True),fill=MUTED)
    fname=f"{post['id']}_{post['pillar'].lower().replace(' ','_')}.png"
    im.save(ASSETS/fname,optimize=True)
    return fname


def main():
    ASSETS.mkdir(exist_ok=True)
    CAPTIONS.mkdir(exist_ok=True)
    data=json.loads(CONTENT.read_text(encoding='utf-8'))
    # Trial campaign: daily November 21-30, then two December posts.
    dates=[date(2026,11,d) for d in range(21,31)] + [date(2026,12,2),date(2026,12,4)]
    rows=[]
    for idx,p in enumerate(data,1):
        img=render_one(p,idx,len(data))
        hashtags=' '.join(p['hashtags'])
        caption=f"{p['caption']}\n\n{hashtags}\n"
        name=f"{p['id']}_caption.txt"
        (CAPTIONS/name).write_text(caption,encoding='utf-8')
        when=dates[idx-1]
        rows.append({
            'date':when.isoformat(), 'time_Warsaw':'18:30', 'post_id':p['id'],
            'topic':p['title'], 'image_path':f'assets/{img}',
            'caption_path':f'captions/{name}', 'status':'DRAFT — review before scheduling'
        })
    with (ROOT/'posting_schedule.csv').open('w',newline='',encoding='utf-8-sig') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    print(f'Generated {len(data)} images, captions and posting_schedule.csv')


if __name__=='__main__':
    main()
