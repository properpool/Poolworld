"""Real browser-pointer regression for drag-to-place cue ball after a foul.

A player must be able to press, drag, and release the cue ball, without
committing placement on pointerdown. Invalid drops and interrupted gestures
must restore the previous legal position. Touch taps and rotated portrait
BIG TABLE geometry must continue to work. Chromium only: no physical Samsung
or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,detail=None):
 checks.append({'name':name,'passed':bool(passed),'detail':detail})
 if not passed:print('FAIL',name,detail,flush=True)

def state(page):
 return page.evaluate("""() => ({
  x:balls[0].x,y:balls[0].y,ballInHand,shooting,shot:shot!==null,
  aim,turn,label:document.getElementById('shoot').textContent,
  valid:canPlace(balls[0].x,balls[0].y),
  placementActive:typeof placementPointer!=='undefined'&&placementPointer!==null
 })""")

def screen(page,x,y):
 return page.evaluate("""({x,y})=>{
  const r=canvas.getBoundingClientRect();
  return focusActive
   ?{x:r.right-y/H*r.width,y:r.top+x/W*r.height}
   :{x:r.left+x/W*r.width,y:r.top+y/H*r.height};
 }""",{'x':x,'y':y})

def touch(cdp,kind,point=None):
 points=[] if point is None else [{'x':point['x'],'y':point['y'],'id':1}]
 cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':points})

def foul(page):
 return page.evaluate("""() => {
  rack();breakShot=false;
  shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
        pocketed:[],scratch:false,targetEight:false};
  resolveShot();
  return {ballInHand,turn,legal:canPlace(balls[0].x,balls[0].y)};
 }""")

with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,
  executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
  args=['--no-sandbox'])
 for w,h in ((360,800),(390,844),(844,390),(768,1024)):
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  page.evaluate('window.requestAnimationFrame=()=>0')
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(HTML,wait_until='load')
  cdp=page.context.new_cdp_session(page)
  tag=f'{w}x{h}'
  modes=['normal']+(['big'] if h>w else [])
  for mode in modes:
   if mode=='big':page.locator('#focusMode').click()
   initial=foul(page)
   check(f'{tag} {mode} foul creates legal ball in hand',
         initial['ballInHand'] and initial['legal'] and initial['turn']==2,initial)
   start=state(page);target={'x':420,'y':215}
   check(f'{tag} {mode} target legal',page.evaluate('canPlace(420,215)'))
   p0=screen(page,start['x'],start['y']);p1=screen(page,420,215)
   touch(cdp,'touchStart',p0)
   down=state(page)
   check(f'{tag} {mode} press does not prematurely confirm ball in hand',
         down['ballInHand'] and down['placementActive'] and down['label']=='PLACE CUE',down)
   touch(cdp,'touchMove',p1)
   moving=state(page)
   check(f'{tag} {mode} real touch drag previews target before release',
         moving['ballInHand'] and moving['placementActive'] and
         abs(moving['x']-420)<1.5 and abs(moving['y']-215)<1.5,moving)
   check(f'{tag} {mode} drag does not aim or fire',
         not moving['shooting'] and moving['shot']==False and abs(moving['aim']-start['aim'])<1e-10,moving)
   touch(cdp,'touchEnd')
   released=state(page)
   check(f'{tag} {mode} release confirms dragged legal cue position',
         not released['ballInHand'] and not released['placementActive'] and
         released['label']=='SHOOT' and abs(released['x']-420)<1.5 and
         abs(released['y']-215)<1.5 and released['valid'],released)
   check(f'{tag} {mode} release does not fire',not released['shooting'] and not released['shot'],released)

   # A cancelled drag must restore the legal starting position and preserve
   # the next player's placement turn, not leave an invisible captured pointer.
   foul(page);origin=state(page)
   p0=screen(page,origin['x'],origin['y']);p1=screen(page,445,235)
   touch(cdp,'touchStart',p0);touch(cdp,'touchMove',p1)
   moved=state(page)
   touch(cdp,'touchCancel')
   cancelled=state(page)
   check(f'{tag} {mode} cancellation restores original cue location',
         abs(cancelled['x']-origin['x'])<1e-7 and
         abs(cancelled['y']-origin['y'])<1e-7,{'moved':moved,'cancelled':cancelled})
   check(f'{tag} {mode} cancellation retains placement turn and unlocks touch',
         cancelled['ballInHand'] and not cancelled['placementActive'] and
         cancelled['label']=='PLACE CUE' and not cancelled['shooting'],cancelled)

   # A drop on another object ball must not silently accept an illegal
   # position or complete the turn.
   foul(page);origin=state(page)
   page.evaluate("""() => {balls[1].x=440;balls[1].y=220}""")
   check(f'{tag} {mode} occupied target rejected',not page.evaluate('canPlace(440,220)'))
   touch(cdp,'touchStart',screen(page,origin['x'],origin['y']))
   touch(cdp,'touchMove',screen(page,440,220))
   touch(cdp,'touchEnd')
   rejected=state(page)
   check(f'{tag} {mode} invalid release restores cue and retains ball in hand',
         rejected['ballInHand'] and rejected['valid'] and
         abs(rejected['x']-origin['x'])<1e-7 and
         abs(rejected['y']-origin['y'])<1e-7 and
         rejected['label']=='PLACE CUE' and not rejected['placementActive'],rejected)

   # Traditional tap-to-place must still work for users who prefer tapping.
   foul(page)
   tap=screen(page,260,185)
   touch(cdp,'touchStart',tap);touch(cdp,'touchEnd')
   tapped=state(page)
   check(f'{tag} {mode} one tap still places the cue ball',
         not tapped['ballInHand'] and tapped['label']=='SHOOT' and
         abs(tapped['x']-260)<1.5 and abs(tapped['y']-185)<1.5,tapped)
   check(f'{tag} {mode} no browser exceptions',not errors,errors)
   if mode=='big':page.locator('#exitFocus').click()
  page.close()
 browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
 'checks':checks,'limits':'Real Chromium touch injection; physical Samsung A37 and independent human acceptance remain release-blocking.'}
(ROOT/'POOL_WORLD_6.0_BALL_IN_HAND_DRAG_RESULTS.json').write_text(json.dumps(result,indent=2))
print('BALL-IN-HAND DRAG',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
