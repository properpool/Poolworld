"""Regression: a rounded pocket-jaw rebound AFTER legal cue contact in the
same 120Hz physics tick must satisfy the cushion-after-contact rule.
The existing rail chronology tests cover straight cushions but not jaw noses.
Real Chromium physics and match adjudication, NOT physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, condition, data):
    checks.append({'name':name,'passed':bool(condition),'details':data})
    if not condition: print('FAIL',name,json.dumps(data),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1100,has_touch=w<1100)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for direction in (-1,1):
            for power in (25,75):
                for case in ('cue-before-jaw','jaw-before-cue','no-cue-contact'):
                    data=page.evaluate("""([direction,level,caseName])=>{
                      const speed=shotSpeed(level,false),travel=speed*.5;
                      const fraction=caseName==='cue-before-jaw'?.08:
                        caseName==='jaw-before-cue'?.65:1.5;
                      const cue=makeBall(0,400,285);
                      const obj=makeBall(1,400+direction*(2*rad+travel*fraction),285);
                      // The upper-left corner's rounded jaw is at (L+42,T).
                      // Ball is just outside the 19.2-unit expanded nose,
                      // moving upward: its real jaw impact occurs at t~0.15.
                      // It never crosses the straight top rail.
                      const jawBall=makeBall(9,L+cornerMouth,T+rad+jawRadius+.3);
                      cue.vx=direction*speed;jawBall.vy=-4;
                      balls=[cue,obj,jawBall];turn=1;
                      groups={1:'solids',2:'stripes'};
                      ballInHand=false;gameOver=false;winner=null;breakShot=false;
                      shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
                        pocketed:[],scratch:false,targetEight:false};
                      shooting=true;accumulator=0;events.length=0;showPower(level);
                      const initialJawY=jawBall.y;
                      physics(STEP);
                      const result={firstHit:shot.firstHit,
                        railAfterContact:shot.railAfterContact,
                        jawY:jawBall.y,initialJawY,jawVy:jawBall.vy,
                        objectSpeed:Math.hypot(obj.vx,obj.vy),
                        speedBefore:speed,speedAfter:shotSpeed(level,false),
                        state:balls.flatMap(b=>[b.x,b.y,b.vx,b.vy,b.spin])};
                      resolveShot();
                      return {...result,ballInHand,turn,gameOver};
                    }""",[direction,power,case])
                    tag=f'{w}x{h} dir={direction} power={power} {case}'
                    hit=case!='no-cue-contact'
                    legal=case=='cue-before-jaw'
                    check(tag+' real cue first hit',
                          data['firstHit']==(1 if hit else None),data)
                    check(tag+' jaw actually rebounds',
                          data['jawVy']>0 and data['jawY']>data['initialJawY']-3,data)
                    check(tag+' chronological jaw rule',
                          data['railAfterContact']==legal,data)
                    check(tag+' correct foul and ball-in-hand',
                          data['ballInHand']==(not legal),data)
                    check(tag+' ordinary turn and no premature game over',
                          data['turn']==2 and not data['gameOver'],data)
                    check(tag+' unchanged power and finite physics',
                          abs(data['speedBefore']-data['speedAfter'])<1e-10
                          and all(math.isfinite(v) for v in data['state']),data)
        check(f'{w}x{h} no browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_JAW_CONTACT_CHRONOLOGY_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Deterministic Chromium physics only, no physical Samsung/human acceptance.'
},indent=2))
print('JAW CHRONOLOGY SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
