"""A real low-speed cushion rebound after legal object contact must count for
the no-rail/no-pot foul rule even when it is too quiet for a rail sound.

Chromium 120Hz deterministic rules/physics, not physical Samsung Galaxy A37
FPS, shot feel, audio loudness, or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,condition,data):
    checks.append({'name':label,'passed':bool(condition),'detail':data})
    if not condition: print('FAIL',label,json.dumps(data),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        for wall in ('left','right','top','bottom'):
            for speed in (.035,.050,.063,.120):
                data=page.evaluate("""({wall,speed})=>{
                  rack();pocketVisuals.length=0;events.length=0;
                  const normal=wall==='left'?[1,0]:wall==='right'?[-1,0]:
                    wall==='top'?[0,1]:[0,-1];
                  const x=wall==='left'?L+rad+.001:wall==='right'?R-rad-.001:400;
                  const y=wall==='top'?T+rad+.001:wall==='bottom'?B-rad-.001:285;
                  balls=[makeBall(0,400,285),makeBall(1,x,y)];
                  const target=balls[1];
                  target.vx=-normal[0]*speed;target.vy=-normal[1]*speed;
                  turn=1;groups={1:'solids',2:'stripes'};
                  breakShot=false;gameOver=false;ballInHand=false;
                  shooting=true;shot={player:1,breakShot:false,firstHit:1,
                    railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                  const beforeImpulse=shotSpeed(75,false);
                  physics(STEP);
                  const impact={rail:shot.railAfterContact,
                    outgoing:target.vx*normal[0]+target.vy*normal[1],
                    soundKinds:events.map(e=>e[0]),potted:target.potted,
                    firstHit:shot.firstHit};
                  let ticks=1;
                  while(!settled()&&ticks<80){physics(STEP);ticks++}
                  const settledNow=settled();
                  const railBeforeResolution=shot.railAfterContact;
                  resolveShot();
                  return {impact,settledNow,ticks,railBeforeResolution,
                    turn,ballInHand,shooting,gameOver,
                    cuePotted:balls[0].potted,objectPotted:target.potted,
                    calibrated:shotSpeed(75,false)===beforeImpulse};
                }""",{'wall':wall,'speed':speed})
                tag=f'{width}x{height} {wall} {speed:.3f}'
                check(tag+' physically rebounds inward',
                    data['impact']['outgoing']>0,data)
                check(tag+' legal first object contact retained',
                    data['impact']['firstHit']==1 and not data['impact']['potted'],data)
                check(tag+' rebound registers rail-after-contact',
                    data['impact']['rail'] and data['railBeforeResolution'],data)
                check(tag+' shot naturally settles',data['settledNow'] and data['ticks']<80,data)
                check(tag+' no false foul or ball-in-hand',
                    data['turn']==2 and not data['ballInHand'] and not data['shooting'],data)
                check(tag+' quiet collision retains audio threshold',
                    ('rail' in data['impact']['soundKinds'])==(speed>.07),data)
                check(tag+' cue and scoring unchanged',
                    not data['cuePotted'] and not data['objectPotted'] and
                    not data['gameOver'] and data['calibrated'],data)
            control=page.evaluate("""wall=>{
                rack();events.length=0;
                const normal=wall==='left'?[1,0]:wall==='right'?[-1,0]:
                  wall==='top'?[0,1]:[0,-1];
                const x=wall==='left'?L+rad+.001:wall==='right'?R-rad-.001:400;
                const y=wall==='top'?T+rad+.001:wall==='bottom'?B-rad-.001:285;
                balls=[makeBall(0,400,285),makeBall(1,x,y)];
                balls[1].vx=-normal[0]*.05;balls[1].vy=-normal[1]*.05;
                turn=1;groups={1:'solids',2:'stripes'};breakShot=false;
                gameOver=false;ballInHand=false;shooting=true;
                shot={player:1,breakShot:false,firstHit:null,
                    railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                physics(STEP);
                const before=shot.railAfterContact;
                // A rail struck BEFORE any object contact must not satisfy
                // the after-contact requirement retroactively.
                shot.firstHit=1;
                resolveShot();
                return {before,turn,ballInHand};
            }""",wall)
            tag=f'{width}x{height} {wall} pre-contact control'
            check(tag+' earlier rail not credited',not control['before'],control)
            check(tag+' earlier rail still yields foul',
                  control['turn']==2 and control['ballInHand'],control)
        check(f'{width}x{height} no JS exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_SOFT_RAIL_FOUL_RESULTS.json').write_text(json.dumps({
  'passed':passed,'total':len(checks),'checks':checks,
  'limits':'Chromium physics/rules only; Samsung Galaxy A37 and human acceptance release-blocking.'
},indent=2))
print('SOFT RAIL FOUL',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
