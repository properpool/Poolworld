"""Keyboard foul recovery, tablet stylus aiming, and natural-rack match stress.

Chromium browser assertions, NOT physical-device or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(name, condition, detail=None):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
    print(('PASS' if condition else 'FAIL'),name,detail,flush=True)

STRESS="""({shots,seed})=>{
 const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
 rack();breakShot=false;
 let completed=0,reracks=0,fouls=0,invalid=0,unsettled=0,minDistance=1e9,maxSteps=0;
 for(let i=0;i<shots;i++){
  if(gameOver){rack();breakShot=false;reracks++}
  if(ballInHand){fouls++;if(!confirmCuePlacement()){invalid++;break}}
  const cue=balls[0], targets=balls.filter(b=>b.id!==0&&!b.potted);
  if(!targets.length){rack();breakShot=false;reracks++;continue}
  const target=targets[Math.floor(random()*targets.length)];
  aim=Math.atan2(target.y-cue.y,target.x-cue.x)+(random()-.5)*.22;
  showPower(23+random()*70);
  if(!shoot()){invalid++;break}
  let n=0;while(!settled()&&n++<4500)physics(STEP);
  maxSteps=Math.max(maxSteps,n);
  if(!settled()){unsettled++;break}
  resolveShot();completed++;
  for(const b of balls)if(!b.potted){
   if(!Number.isFinite(b.x)||!Number.isFinite(b.y)||!Number.isFinite(b.vx)||!Number.isFinite(b.vy)){invalid++}
  }
  for(let a=0;a<balls.length;a++)for(let b=a+1;b<balls.length;b++){
   if(balls[a].potted||balls[b].potted)continue;
   minDistance=Math.min(minDistance,Math.hypot(balls[a].x-balls[b].x,balls[a].y-balls[b].y));
  }
  if(invalid)break;
 }
 return {completed,reracks,fouls,invalid,unsettled,minDistance,maxSteps};
}"""

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
    for width,height in [(1366,768),(768,1024),(390,844)]:
        page=browser.new_page(viewport={'width':width,'height':height},
                              is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.set_content(SOURCE.read_text(),wait_until='load')
        if width==1366:
            page.evaluate("""() => {rack();breakShot=false;shot={player:1,breakShot:false,firstHit:null,
              railAfterContact:false,pocketed:[],scratch:false,targetEight:false};shooting=true;resolveShot()}""")
            check('desktop foul requires cue placement',page.evaluate("ballInHand && !shooting && document.querySelector('#shoot').textContent==='PLACE CUE'"))
            page.keyboard.press('Space')
            check('desktop Space confirms cue without firing',page.evaluate("!ballInHand && !shooting && document.querySelector('#shoot').textContent==='SHOOT'"))
            page.keyboard.press('Space')
            check('desktop second Space initiates shot',page.evaluate("shooting && Math.hypot(balls[0].vx,balls[0].vy)>3"))
            page.evaluate("() => {let n=0;while(!settled()&&n++<4500)physics(STEP);if(settled())resolveShot()}")
            check('desktop keyboard shot resolves',page.evaluate('!shooting'))
            page.evaluate('rack()')
            page.keyboard.down('Space')
            page.keyboard.up('Space')
            page.evaluate('rack()')
            page.keyboard.insert_text('')
            page.evaluate("""() => document.dispatchEvent(new KeyboardEvent('keydown',{code:'Space',repeat:true,bubbles:true,cancelable:true}))""")
            check('desktop repeated Space cannot accidentally shoot',page.evaluate('!shooting'))
            page.locator('details').evaluate('(el) => {el.open=true}')
            page.locator('#strength').focus()
            before=page.evaluate("() => ({active:document.activeElement?.id,shooting})")
            page.keyboard.press('Space')
            after=page.evaluate("() => ({active:document.activeElement?.id,shooting})")
            check('desktop slider focus blocks gameplay Space',not after['shooting'],{'before':before,'after':after})
        if width==768:
            for delta in (10,18):
                data=page.evaluate("""(delta)=>{
                  rack();aim=0;const b=balls[0],r=canvas.getBoundingClientRect();
                  const x=r.left+b.x/W*r.width,y=r.top+b.y/H*r.height;
                  pointAim({pointerType:'pen',clientX:x+delta,clientY:y});
                  return {aim,delta};
                }""",delta)
                check(f'tablet stylus within {delta}px does not snap aim',abs(data['aim'])<1e-10,data)
            data=page.evaluate("""()=>{
              rack();aim=0;const b=balls[0],r=canvas.getBoundingClientRect();
              const x=r.left+b.x/W*r.width,y=r.top+b.y/H*r.height;
              pointAim({pointerType:'pen',clientX:x+62,clientY:y+25});
              return {aim};
            }""")
            check('tablet deliberate distant stylus aim works',abs(data['aim'])>.1,data)
        for seed in (91,2026):
            outcome=page.evaluate(STRESS,{'shots':24,'seed':seed})
            check(f'{width}px natural-rack {seed} completes 24 physics shots',
                  outcome['completed']==24 and outcome['unsettled']==0 and outcome['invalid']==0,outcome)
            check(f'{width}px natural-rack {seed} no settled ball overlap',
                  outcome['minDistance']>=2*12.2-.8,outcome)
        check(f'{width}px no browser errors',not errors,errors)
        page.close()
    browser.close()
summary={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,
         'limitations':'Chromium automation and scripted stress only; not real-device or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_INPUT_RECOVERY_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)
