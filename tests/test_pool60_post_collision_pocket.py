"""Pocket capture must run after contact correction, before shot settlement.

A late rail-side ball collision can push an otherwise resting object ball
inside a real pocket well AFTER the first swept capture pass. If all velocities
are already below the settle threshold, the shot ends before another physics
step can capture it: a visibly pocketed ball remains on the table and scores
nothing. These Chromium geometry checks do not establish physical Samsung
frame rate or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1100,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        for side in ('top','bottom'):
            for offset in (0,1.6):
                data=page.evaluate("""({side,offset})=>{
                  rack();pocketVisuals.length=0;events.length=0;
                  const hole=side==='top'?[W/2,T-8]:[W/2,B+8];
                  const towardCloth=side==='top'?1:-1;
                  const startY=hole[1]+towardCloth*(20.5+offset);
                  // Two stationary balls have a small legal-solver overlap.
                  // Their positional correction pushes ball 1 into the well
                  // without creating a velocity or another simulation tick.
                  balls=[makeBall(0,320,285),makeBall(1,W/2,startY),
                    makeBall(9,W/2,startY+towardCloth*22.7)];
                  shot={player:1,breakShot:false,firstHit:null,
                    railAfterContact:false,pocketed:[],scratch:false,
                    targetEight:false};
                  shooting=true;breakShot=false;turn=1;gameOver=false;
                  groups={1:null,2:null};ballInHand=false;
                  const before={x:balls[1].x,y:balls[1].y,
                    cueX:balls[0].x,cueY:balls[0].y,
                    shotSpeed:shotSpeed(75,false)};
                  physics(STEP);
                  const target=balls[1],dx=target.x-hole[0],dy=target.y-hole[1];
                  const after={x:target.x,y:target.y,potted:target.potted,
                    inWell:dx*dx+dy*dy<POCKET_CAPTURE_RADIUS2,
                    pocketed:[...shot.pocketed],ghosts:pocketVisuals.map(g=>g.id),
                    soundKinds:events.map(e=>e[0]),cueX:balls[0].x,cueY:balls[0].y,
                    settled:settled(),shotSpeed:shotSpeed(75,false)};
                  if(after.settled)resolveShot();
                  after.afterResolution={shooting,ballInHand,turn,
                    targetPotted:balls[1].potted};
                  return {before,after};
                }""",{'side':side,'offset':offset})
                tag=f'{w}x{h} {side} offset={offset}'
                a=data['after'];b=data['before']
                check(tag+' starts outside pocket well',
                    math.hypot(b['x']-550,b['y']-(70 if side=='top' else 500))>27*.74,data)
                check(tag+' stationary contact settles without extra physics',
                    a['settled'] and not a['afterResolution']['shooting'],data)
                check(tag+' cue remains unmoved and shot power calibrated',
                    a['cueX']==b['cueX'] and a['cueY']==b['cueY'] and
                    a['shotSpeed']==b['shotSpeed'],data)
                if offset==0:
                    check(tag+' final centre enters real pocket well',a['inWell'],data)
                    check(tag+' capture occurs before settlement',a['potted'] and
                        a['afterResolution']['targetPotted'],data)
                    check(tag+' pot is recorded once in match rules',
                        a['pocketed']==[1],data)
                    check(tag+' sink ghost and recorded pocket sound survive',
                        a['ghosts']==[1] and a['soundKinds'].count('pocket')==1,data)
                else:
                    check(tag+' near-miss remains outside capture radius',
                        not a['inWell'],data)
                    check(tag+' no phantom pot or sink visual',
                        not a['potted'] and not a['pocketed'] and
                        not a['ghosts'] and 'pocket' not in a['soundKinds'],data)
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POST_COLLISION_POCKET_RESULTS.json').write_text(json.dumps({
  'passed':passed,'total':len(checks),'checks':checks,
  'limits':'Chromium deterministic physics and scoring, not Samsung A37 hardware or human acceptance.'
},indent=2))
print('POST-COLLISION POCKET',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
