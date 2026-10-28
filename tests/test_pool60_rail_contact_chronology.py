"""Rail rebound after first cue contact in the SAME 120 Hz tick is legal.
Chronological fixture: an unrelated moving object ball reaches a cushion at
t~=0.15, while the cue strikes a legal object at t~=0.08 (before rail) or
t~=0.65 (after rail). The current physics loop reflects rails before
earliestCueContact(), so the early contact was previously falsely fouled.
Browser physics and rule adjudication, NOT Samsung hardware acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,condition,data):
    checks.append({'name':name,'passed':bool(condition),'details':data})
    if not condition: print('FAIL',name,data,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for direction in (-1,1):
            for power in (25,75):
                for case in ('cue-before-rail','rail-before-cue','no-cue-contact'):
                    data=page.evaluate("""([direction,level,caseName])=>{
                      const speed=shotSpeed(level,false),travel=speed*.5;
                      const fraction=caseName==='cue-before-rail'?.08:
                        caseName==='rail-before-cue'?.65:1.5;
                      const cue=makeBall(0,400,285);
                      const obj=makeBall(1,400+direction*(2*rad+travel*fraction),285);
                      const rail=makeBall(9,direction>0?R-rad-.3:L+rad+.3,400);
                      cue.vx=direction*speed;rail.vx=direction*4;
                      balls=[cue,obj,rail];turn=1;groups={1:'solids',2:'stripes'};
                      ballInHand=false;gameOver=false;winner=null;breakShot=false;
                      shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
                        pocketed:[],scratch:false,targetEight:false};
                      shooting=true;accumulator=0;events.length=0;showPower(level);
                      const originalSpeed=shotSpeed(power,false);
                      physics(STEP);
                      const state={firstHit:shot.firstHit,railAfterContact:shot.railAfterContact,
                        railV:rail.vx,objectSpeed:Math.hypot(obj.vx,obj.vy),
                        speedBefore:originalSpeed,speedAfter:shotSpeed(power,false),
                        positions:balls.flatMap(b=>[b.x,b.y,b.vx,b.vy])};
                      resolveShot();
                      return {...state,ballInHand,turn,gameOver};
                    }""",[direction,power,case])
                    name=f'{w}x{h} dir={direction} power={power} {case}'
                    hit=case!='no-cue-contact'
                    legal=case=='cue-before-rail'
                    check(name+' actual first cue contact',data['firstHit']==(1 if hit else None),data)
                    check(name+' moving object actually rebounds from rail',
                        data['railV']*direction<0,data)
                    check(name+' chronological rail adjudication',
                        data['railAfterContact']==legal,data)
                    check(name+' ball in hand only for real foul',
                        data['ballInHand']==(not legal),data)
                    check(name+' no accidental game over, normal turn resolution',
                        not data['gameOver'] and data['turn']==2,data)
                    check(name+' impulse unchanged and finite state',
                        abs(data['speedBefore']-data['speedAfter'])<1e-10
                        and all(math.isfinite(v) for v in data['positions']),data)
        check(f'{w}x{h} no Chromium page errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_RAIL_CONTACT_CHRONOLOGY_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Real Chromium physics and match rules; no physical Galaxy A37 acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
