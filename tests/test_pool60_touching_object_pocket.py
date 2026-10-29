"""A ball already touching a faster incoming ball must receive its real
t=0 impulse before the first ball enters a side pocket in the same physics tick.
The pre-collision pocket sweep must not erase the touching-ball impact.
Separating, equal-speed and gapped balls are negative controls. Browser-only.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,data):
    checks.append({'name':name,'passed':bool(ok),'details':data})
    if not ok:print('FAIL',name,json.dumps(data),flush=True)

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
        for side in ('top','bottom'):
            for level in (45,75,95):
                for order in ('a-first','b-first'):
                    for scenario in ('touching-closing','touching-separating',
                                     'touching-equal','gapped-chasing'):
                        result=page.evaluate("""([side,level,order,scenario])=>{
                          const dir=side==='top'?1:-1,well=side==='top'?T-8:B+8;
                          const factor=shotSpeed(level,false)/shotSpeed(75,false);
                          const incoming=8*factor;
                          const trailing=(scenario==='touching-separating'?4:
                            scenario==='touching-equal'?8:14)*factor;
                          const distance=scenario==='gapped-chasing'?2*rad+8:2*rad-.001;
                          const a=makeBall(1,W/2,well+dir*21.4);
                          const b=makeBall(9,W/2,a.y+dir*distance);
                          const cue=makeBall(0,320,285);
                          a.vy=-dir*incoming;b.vy=-dir*trailing;
                          balls=order==='a-first'?[cue,a,b]:[cue,b,a];
                          turn=1;groups={1:'solids',2:'stripes'};
                          breakShot=false;ballInHand=false;gameOver=false;winner=null;
                          shot={player:1,breakShot:false,firstHit:null,
                            railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                          shooting=true;events.length=0;pocketVisuals.length=0;
                          showPower(level);
                          const impulse=shotSpeed(power,false);
                          physics(STEP);
                          return {aPotted:a.potted,bPotted:b.potted,
                            bSpeed:Math.hypot(b.vx,b.vy),initialB:trailing,
                            aSpeed:Math.hypot(a.vx,a.vy),pocketed:shot.pocketed.slice(),
                            ghosts:pocketVisuals.map(g=>g.id),
                            sounds:events.map(e=>e[0]),firstHit:shot.firstHit,
                            cue:[cue.x,cue.y,cue.vx,cue.vy],power,impulse,
                            finite:balls.every(x=>[x.x,x.y,x.vx,x.vy,x.spin,x.follow]
                              .every(Number.isFinite))};
                        }""",[side,level,order,scenario])
                        tag=f'{width}x{height} {side} power={level} {order} {scenario}'
                        closing=scenario=='touching-closing'
                        check(tag+' pocketed object captured once',
                            result['aPotted'] and not result['bPotted']
                            and result['pocketed']==[1] and result['ghosts']==[1],result)
                        check(tag+' real closing contact transfers momentum',
                            (result['bSpeed']<result['initialB']*.8 if closing
                             else abs(result['bSpeed']-result['initialB'])<.12),result)
                        check(tag+' collision sound only for actual impact',
                            (result['sounds'].count('ball')>=1 if closing
                             else result['sounds'].count('ball')==0),result)
                        check(tag+' pocket sound exactly once',
                            result['sounds'].count('pocket')==1,result)
                        check(tag+' cue and first-hit rule remain untouched',
                            result['cue']==[320,285,0,0]
                            and result['firstHit'] is None,result)
                        check(tag+' calibrated shot impulse and finite state',
                            result['power']==level
                            and abs(result['impulse']-(.45+7.9*(level/100)**.92))<1e-8
                            and result['finite'],result)
        check(f'{width}x{height} no Chromium errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_TOUCHING_OBJECT_POCKET_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium physics only; physical Samsung and independent human acceptance remain blocked.'},indent=2))
print('TOUCHING OBJECT POCKET SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
