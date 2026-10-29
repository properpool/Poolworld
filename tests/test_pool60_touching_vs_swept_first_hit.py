"""A real closing cue/object contact at t=0 must beat a later swept hit.
The old first-hit prepass ignored touching balls and prematurely chose the
later swept object, wrongly awarding a foul and ball in hand. Browser-only.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, ok, data):
    checks.append({'name':name,'passed':bool(ok),'details':None if ok else data})
    if not ok:
        print('FAIL',name,json.dumps(data),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=width<1100)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for near_id in (1,9):
            for direction in (-1,1):
                for side in (-1,1):
                    for cosine in (.30,.36,.42):
                        for speed in (7,9,11):
                            for gap in (.25,.5):
                                result=page.evaluate("""({nearId,direction,side,cosine,speed,gap})=>{
                                  rack();
                                  const cue=makeBall(0,400,285);
                                  const near=makeBall(nearId,
                                    400+direction*(2*rad-.001)*cosine,
                                    285+side*(2*rad-.001)*Math.sqrt(1-cosine*cosine));
                                  const far=makeBall(nearId===1?9:1,
                                    400+direction*(2*rad+gap),285);
                                  const initialNear=Math.hypot(near.x-cue.x,near.y-cue.y);
                                  const initialFar=Math.hypot(far.x-cue.x,far.y-cue.y);
                                  const separate=Math.hypot(far.x-near.x,far.y-near.y);
                                  balls=[cue,near,far];
                                  cue.vx=direction*speed;cue.vy=0;
                                  turn=1;groups={1:groupOf(nearId),2:groupOf(far.id)};
                                  breakShot=false;ballInHand=false;gameOver=false;winner=null;
                                  shooting=true;accumulator=0;events.length=0;
                                  shot={player:1,breakShot:false,firstHit:null,
                                    railAfterContact:true,pocketed:[],scratch:false,
                                    targetEight:false};
                                  physics(STEP);
                                  const firstHit=shot.firstHit;
                                  const nearSpeed=Math.hypot(near.vx,near.vy);
                                  const farSpeed=Math.hypot(far.vx,far.vy);
                                  const potted=balls.some(b=>b.potted);
                                  resolveShot();
                                  return {nearId,farId:far.id,initialNear,initialFar,
                                    separate,firstHit,nearSpeed,farSpeed,potted,
                                    turn,ballInHand,groups,gameOver,
                                    finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                                }""",{'nearId':near_id,'direction':direction,
                                    'side':side,'cosine':cosine,'speed':speed,'gap':gap})
                                tag=f'{width}x{height} near={near_id} dir={direction} side={side} cos={cosine} speed={speed} gap={gap}'
                                check(tag+' valid distinct non-overlapping layout',
                                    result['initialNear']<24.4 and
                                    result['initialNear']>24.39 and
                                    result['initialFar']>24.4 and
                                    result['separate']>24.4 and
                                    not result['potted'],result)
                                check(tag+' touching object receives real impulse',
                                    result['nearSpeed']>.05,result)
                                check(tag+' later swept object also receives impulse',
                                    result['farSpeed']>.05,result)
                                check(tag+' first cue hit is actual t=0 closing contact',
                                    result['firstHit']==near_id,result)
                                check(tag+' no false foul or ball in hand',
                                    result['turn']==2 and not result['ballInHand'] and
                                    not result['gameOver'],result)
                                check(tag+' finite state after shot resolution',
                                    result['finite'],result)
        check(f'{width}x{height} browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_TOUCHING_VS_SWEPT_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium physics/rules only; physical Samsung and human acceptance remain release-blocking.'},indent=2))
print('TOUCHING VS SWEPT FIRST HIT SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
