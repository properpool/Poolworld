"""Regression: the main action remains usable after fouls, including scratches.

A foul must not leave the player with an apparently broken SHOOT button.
A visible PLACE CUE action confirms the existing legal position or safely
relocates the cue if it overlaps another ball. Real touchscreen taps are used.
Chromium emulation is not physical Samsung or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
def tap(page,selector):
 box=page.locator(selector).bounding_box()
 page.touchscreen.tap(box['x']+box['width']/2,box['y']+box['height']/2)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(SOURCE.read_text(),wait_until='load')
  check(f'{w} initial action is enabled SHOOT',page.evaluate("!document.querySelector('#shoot').disabled && document.querySelector('#shoot').textContent==='SHOOT'"))
  # Fire a real low-power shot away from the rack to incur a no-contact foul.
  page.evaluate("() => {rack();breakShot=false;balls[0].x=320;balls[0].y=285;aim=Math.PI;showPower(25)}")
  tap(page,'#shoot')
  result=page.evaluate("""() => {
   const fired=shooting;
   let steps=0;while(!settled()&&steps++<4500)physics(STEP);
   const firstHit=shot?.firstHit,done=settled();
   if(done)resolveShot();
   return {fired,firstHit,done,steps,turn,ballInHand,action:document.querySelector('#shoot').textContent,
           disabled:document.querySelector('#shoot').disabled,status:document.querySelector('#status').textContent};
  }""")
  check(f'{w} real no-contact shot resolves as foul with ball in hand',
        result['fired'] and result['done'] and result['firstHit'] is None and result['ballInHand'] and result['turn']==2,result)
  check(f'{w} foul offers enabled PLACE CUE instead of dead SHOOT',
        result['action']=='PLACE CUE' and not result['disabled'] and 'PLACE CUE' in result['status'])
  tap(page,'#shoot')
  placed=page.evaluate("""() => ({ballInHand,legal:canPlace(balls[0].x,balls[0].y),
   label:document.querySelector('#shoot').textContent,shooting})""")
  check(f'{w} PLACE CUE confirms valid cue position without firing',
        not placed['ballInHand'] and placed['legal'] and placed['label']=='SHOOT' and not placed['shooting'],placed)
  tap(page,'#shoot')
  check(f'{w} subsequent SHOOT actually fires',page.evaluate('shooting && Math.hypot(balls[0].vx,balls[0].vy)>1'))
  # Simulate the resolved scratch rule path, then invalidate the cue position
  # by overlapping an object ball: confirmation must find an open location.
  page.evaluate("""() => {
   rack();breakShot=false;
   shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,pocketed:[0],scratch:true,targetEight:false};
   balls[0].potted=true;resolveShot();
   balls[0].x=balls[1].x;balls[0].y=balls[1].y;
  }""")
  check(f'{w} scratch gives cue-ball placement opportunity',
        page.evaluate("ballInHand && !balls[0].potted && document.querySelector('#shoot').textContent==='PLACE CUE'"))
  tap(page,'#shoot')
  relocated=page.evaluate("""() => ({
   legal:canPlace(balls[0].x,balls[0].y),
   distance:Math.hypot(balls[0].x-balls[1].x,balls[0].y-balls[1].y),
   ballInHand,label:document.querySelector('#shoot').textContent
  })""")
  check(f'{w} PLACE CUE repairs illegal overlapping cue position',
        relocated['legal'] and relocated['distance']>24.4 and not relocated['ballInHand'] and relocated['label']=='SHOOT',relocated)
  # Traditional touch-to-place is still available for players who wish to move the cue.
  page.evaluate("""() => {
   rack();breakShot=false;
   shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
   resolveShot();
  }""")
  pt=page.evaluate("() => ({legal:canPlace(250,180),ballInHand})")
  box=page.locator('#table').bounding_box()
  page.touchscreen.tap(box['x']+250/1100*box['width'],box['y']+180/570*box['height'])
  state=page.evaluate("() => ({ballInHand,x:balls[0].x,y:balls[0].y,label:document.querySelector('#shoot').textContent})")
  check(f'{w} table tap still repositions cue ball',
        pt['legal'] and pt['ballInHand'] and not state['ballInHand'] and abs(state['x']-250)<1 and abs(state['y']-180)<1 and state['label']=='SHOOT',state)
  check(f'{w} no JavaScript exceptions',not errors,errors)
  page.close()
 browser.close()
summary={'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,
 'limits':'Chromium simulated touch only; not physical Samsung or independent human acceptance.'}
(ROOT/'POOL_WORLD_6.0_FOUL_ACTION_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)
