#!/usr/bin/env python3
"""Frostclaw batch content agent. Nothing here calls Metricool or Instagram.

Commands:
  python agent.py build
  python agent.py check
  python agent.py draft --topic 'Boundary value analysis'
  python agent.py approve --id 13 --reviewed
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, timedelta
from difflib import SequenceMatcher
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.request import Request, urlopen

from render_posts import render_one, ASSETS as GENERATED_MEDIA

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'content' / 'posts.json'
DRAFTS = ROOT / 'drafts'
APPROVED = ROOT / 'approved'
DOCS = ROOT / 'docs'
MEDIA = DOCS / 'media'
CAPTIONS = ROOT / 'captions'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def config():
    return read_json(ROOT / 'config.json')


def all_posts():
    result = list(read_json(BASE))
    for path in sorted(APPROVED.glob('*.json')):
        result.append(read_json(path))
    return sorted(result, key=lambda x: int(x['id']))


def validate_post(p, existing):
    problems = []
    keys = ['id', 'pillar', 'title', 'hook', 'steps', 'takeaway', 'caption', 'hashtags']
    problems.extend('Missing required key: '+k for k in keys if k not in p)
    if problems:
        return problems
    if not str(p['id']).isdigit(): problems.append('ID must be numeric')
    if p['pillar'] not in ('QA BASICS', 'WORKFLOW', 'SPREADSHEETS'):
        problems.append('Pillar must be QA BASICS / WORKFLOW / SPREADSHEETS')
    for k,limit in [('title',64),('hook',110),('takeaway',95),('caption',900)]:
        if not isinstance(p[k],str) or not 8<=len(p[k])<=limit:
            problems.append(f'{k}: must be between 8 and {limit} characters')
    if not isinstance(p['steps'],list) or not 3<=len(p['steps'])<=5:
        problems.append('steps: expected 3 to 5')
    else:
        for i,step in enumerate(p['steps'],1):
            if not isinstance(step,dict) or not all(k in step for k in ('label','detail')):
                problems.append(f'step {i} missing label/detail')
            elif not 2<=len(step['label'])<=35 or not 4<=len(step['detail'])<=100:
                problems.append(f'step {i} label or detail too long/short')
    h = p['hashtags']
    if not isinstance(h,list) or not 3<=len(h)<=6 or not all(re.fullmatch(r'#[A-Za-z0-9_]{2,50}',s) for s in h):
        problems.append('hashtags: 3–6 valid #hashtags required')
    if any(bad in p['caption'].lower() for bad in ('guaranteed income','100% bug-free','buy now','link in bio')):
        problems.append('caption contains questionable promotional/absolute language')
    for old in existing:
        if old.get('id') == p['id']: problems.append(f'ID already exists: {p["id"]}')
        if SequenceMatcher(None,old.get('title','').lower(),p['title'].lower()).ratio()>0.80:
            problems.append('Potential duplicate title: '+old['title'])
    return problems


def next_day(posts):
    dates = [date.fromisoformat(p['date']) for p in posts if p.get('date')]
    return (max(dates) + timedelta(days=2)) if dates else date.today()+timedelta(days=2)


def calendar_posts():
    posts = all_posts()
    fixed = [date(2026,11,d) for d in range(21,31)] + [date(2026,12,2),date(2026,12,4)]
    last = fixed[-1]
    for i,p in enumerate(posts):
        if i < len(fixed):
            p['date'] = fixed[i].isoformat()
        elif not p.get('date'):
            last += timedelta(days=2)
            p['date'] = last.isoformat()
        else:
            last = date.fromisoformat(p['date'])
    return posts


def do_draft(topic,model):
    posts=calendar_posts()
    n=max([int(p['id']) for p in posts] + [int(p.stem) for p in DRAFTS.glob('*.json') if p.stem.isdigit()] + [0])+1
    next_id=f'{n:02}'
    pending=[read_json(q) for q in DRAFTS.glob('*.json')]
    datestr=next_day(posts+pending).isoformat()
    examples=', '.join(x['title'] for x in posts[-10:])
    prompt=f'''Write ONE original, accurate, useful Instagram infographic for Frostclaw Software.
Topic requested: {topic}. Do NOT repeat these existing topics: {examples}.
Write for junior QA testers and tech hobbyists. Explain something concrete and useful.
Return ONE JSON object ONLY, keys: id, pillar, title, hook, steps, takeaway, caption, hashtags, date.
id must be "{next_id}" and date must be "{datestr}".
pillar must be one of "QA BASICS", "WORKFLOW", "SPREADSHEETS".
title maximum 64 characters; hook maximum 110; takeaway maximum 95.
steps must be 3 or 4 objects each with label (max 35 chars) and detail (max 100 chars).
caption 80-450 characters, friendly tone, no unsupported promises or sales pitch.
hashtags list contains exactly 4 plain hashtags. Use factual claims that can be verified.
Do not use first person, fake experiences, copyrighted quotes, fake statistics or product ads.
'''
    body={'model':model,'prompt':prompt,'format':'json','stream':False,'options':{'temperature':0.45}}
    req=Request('http://127.0.0.1:11434/api/generate',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=240) as resp:
            output=json.load(resp)
    except Exception as e:
        print('Could not reach local Ollama. Install and run Ollama, then: ollama pull '+model, file=sys.stderr)
        raise SystemExit(str(e))
    try: p=json.loads(output['response'])
    except (ValueError,KeyError) as e: raise SystemExit(f'Model returned invalid JSON: {e}')
    p['id']=next_id
    p['date']=datestr
    issues=validate_post(p, posts)
    target=DRAFTS/f'{next_id}.json'
    target.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Draft saved:',target)
    if issues:
        print('QUALITY WARNINGS (edit the JSON before approval):')
        for issue in issues: print(' - '+issue)
    else: print('Automated structure checks passed. TECHNICAL FACTS STILL REQUIRE HUMAN REVIEW.')


def do_approve(id_,reviewed):
    if not reviewed:
        raise SystemExit('Approval requires --reviewed after manually reading and fact-checking the draft.')
    path=DRAFTS/f'{int(id_):02}.json'
    if not path.exists(): raise SystemExit('Draft not found: '+str(path))
    post=read_json(path)
    problems=validate_post(post,all_posts())
    if problems:
        print('\n'.join(problems));raise SystemExit('Fix the draft first. No approval recorded.')
    out=APPROVED/path.name
    shutil.copyfile(path,out)
    print('Approved:',out,'\nRun: python agent.py build')


def do_mark_scheduled(ids):
    valid={p['id'] for p in all_posts()}
    norm=[f'{int(i):02}' for i in ids]
    unknown=set(norm)-valid
    if unknown: raise SystemExit('Unknown post IDs: '+', '.join(sorted(unknown)))
    status=read_json(ROOT/'status.json')
    old=set(status.get('already_scheduled',[]))
    status['already_scheduled']=sorted(old | set(norm),key=int)
    (ROOT/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Marked scheduled:',', '.join(norm),'(update your queue with: python agent.py build)')

def do_check():
    posts=calendar_posts()
    issues=[]
    for i,p in enumerate(posts):
        errs=validate_post(p,posts[:i])
        issues.extend((p.get('id','?')+': '+x) for x in errs)
    print(f'{len(posts)} approved posts examined.')
    if issues:
        for x in issues: print('WARNING:',x)
    else:
        print('All posts pass structural checks. This does NOT verify technical claims.')
    return len(issues)


def do_build():
    issues=do_check()
    if issues: raise SystemExit('Fix validation errors before building.')
    cfg=config()
    DOCS.mkdir(exist_ok=True);MEDIA.mkdir(exist_ok=True);CAPTIONS.mkdir(exist_ok=True)
    GENERATED_MEDIA.mkdir(exist_ok=True)
    posts=calendar_posts()
    scheduled=set(read_json(ROOT/'status.json').get('already_scheduled',[]))
    owner=cfg['github_username']
    repo=cfg['github_repository']
    if (owner != 'YOUR_GITHUB_USERNAME' and not re.fullmatch(r'[A-Za-z0-9-]+',owner)) or not re.fullmatch(r'[A-Za-z0-9_.-]+',repo):
        raise SystemExit('Invalid GitHub username/repository in config.json')
    baseurl=f'https://{owner}.github.io/{repo}/media/'
    schedule=[]
    gallery=[]
    for ix,p in enumerate(posts,1):
        png=render_one(p,ix,len(posts))
        shutil.copyfile(GENERATED_MEDIA/png,MEDIA/png)
        caption=p['caption'].strip()+'\n\n'+' '.join(p['hashtags'])+'\n'
        cap=f"{p['id']}_caption.txt"
        (CAPTIONS/cap).write_text(caption,encoding='utf-8')
        schedule.append({'id':p['id'],'date_warsaw':p['date'],'time_warsaw':cfg['posting_time'],'status':'ALREADY_SCHEDULED' if p['id'] in scheduled else 'READY_FOR_APPROVAL','title':p['title'],'caption_file':f'captions/{cap}','public_image_url':baseurl+png})
        gallery.append(f'<article><img src="media/{escape(png)}" loading="lazy" alt="{escape(p["title"])}"><div><h2>{escape(p["title"])}</h2><p>{escape(p["caption"])}</p></div></article>')
    with (ROOT/'metricool_queue.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=schedule[0].keys());writer.writeheader();writer.writerows(schedule)
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Frostclaw Software — Tech Tips</title><style>
    body{font:16px system-ui,sans-serif;background:#091321;color:#ecf4fb;margin:0;padding:32px;}main{max-width:1050px;margin:auto}h1{font-size:2.2rem}p{line-height:1.6;color:#b7d0da}a{color:#5de3c8}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{background:#14283a;border:1px solid #284458;border-radius:14px;overflow:hidden}article img{width:100%;height:auto;display:block}article div{padding:18px}article h2{font-size:1.15rem}footer{margin-top:50px}</style></head><body><main>
    <h1>Frostclaw Software · Practical tech tips</h1><p>Short, original software testing and workflow guides for learners. Posts are educational examples and should be adapted to your software and requirements.</p><section>'''+''.join(gallery)+'''</section><footer><p>Also on Instagram: @frostclaw.software</p></footer></main></body></html>'''
    (DOCS/'index.html').write_text(page,encoding='utf-8')
    print(f'Built {len(posts)} post graphics, captions, queue and public gallery.')
    print('Note: the URLs in metricool_queue.csv work only AFTER you host /docs and replace YOUR_GITHUB_USERNAME in config.json.')
    print(f'{len(scheduled)} IDs marked ALREADY_SCHEDULED to prevent double booking.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('check');sub.add_parser('build')
    d=sub.add_parser('draft');d.add_argument('--topic',required=True);d.add_argument('--model',default=None)
    a=sub.add_parser('approve');a.add_argument('--id',required=True);a.add_argument('--reviewed',action='store_true')
    m=sub.add_parser('mark-scheduled');m.add_argument('--ids',nargs='+',required=True)
    args=p.parse_args()
    DRAFTS.mkdir(exist_ok=True);APPROVED.mkdir(exist_ok=True)
    if args.command=='check':sys.exit(1 if do_check() else 0)
    elif args.command=='build':do_build()
    elif args.command=='draft':do_draft(args.topic,args.model or config()['default_model'])
    elif args.command=='approve':do_approve(args.id,args.reviewed)
    elif args.command=='mark-scheduled':do_mark_scheduled(args.ids)
if __name__=='__main__':main()
