"""Real Chromium two-finger aiming and pull-to-shoot race regression.

The cue must not launch while the aiming finger is still moving. A completed
power pull is queued until the aiming pointer releases at its FINAL angle.
Cancellation must discard the pending shot, retaining selected power.
This does not constitute physical Samsung Galaxy A37 or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,detail,flush=True)

def screen(page,x,y):
    return page.evaluate("""({x,y})=>{
      const r=canvas.getBoundingClientRect();
      return focusActive
        ?{x:r.right-y/H*r.width,y:r.top+x/W*r.height}
        :{x:r.left+x/W*r.width,y:r.top+y/H*r.height};
    }""",{'x':x,'y':y})

def handle(page):
    return page.evaluate("""()=>{
      const r=document.getElementById('handle').getBoundingClientRect();
      const t=document.getElementById('track');
      const focus=focusActive;
      const pull=Math.max(72,t.clientHeight*.55);
      return {x:r.left+r.width/2,y:r.top+r.height/2,
              pull,focus,threshold:Math.max(42,t.clientHeight*.4)};
    }""")

def touch(cdp,kind,points):
    # CDP touchEnd points identify ENDED touch IDs, not remaining touches.
    # touchCancel requires an EMPTY touchPoints list by protocol.
    cdp.send('Input.dispatchTouchEvent',{'type':kind,
       'touchPoints':[{'x':p['x'],'y':p['y'],'id':i} for i,p in points]})

def state(page):
    return page.evaluate("""()=>({
       shooting,aim,aimPointer,dragAim,power,ballInHand,gameOver,
       queued:typeof pendingAimReleaseShot==='undefined'?null:pendingAimReleaseShot,
       vx:balls[0].vx,vy:balls[0].vy,
       strikePower:cueStrike&&cueStrike.power,
       impulse:Math.hypot(balls[0].vx,balls[0].vy),
       selectedImpulse:shotSpeed(power,false)
    })""")

def reset(page):
    page.evaluate("""()=>{
       rack();balls=[makeBall(0,340,285)];aim=0;breakShot=false;
       ballInHand=false;gameOver=false;showPower(70);
    }""")

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=True,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        cdp=page.context.new_cdp_session(page)
        modes=['normal']+(['big'] if w<=600 and h>w else [])
        for mode in modes:
            if mode=='big':page.locator('#focusMode').click()
            tag=f'{w}x{h} {mode}'
            reset(page)
            aim0=screen(page,700,285)
            aim1=screen(page,700,315)
            aim2=screen(page,700,355)
            h0=handle(page)
            powerEnd={'x':h0['x']-(h0['pull'] if h0['focus'] else 0),
                      'y':h0['y']+(0 if h0['focus'] else h0['pull'])}
            check(tag+' power pull exceeds shoot threshold',
                  h0['pull']>h0['threshold'],h0)
            touch(cdp,'touchStart',[(1,aim0)])
            touch(cdp,'touchStart',[(1,aim0),(2,h0)])
            touch(cdp,'touchMove',[(1,aim1),(2,h0)])
            touch(cdp,'touchMove',[(1,aim1),(2,powerEnd)])
            before=state(page)
            touch(cdp,'touchEnd',[(2,powerEnd)])
            held=state(page)
            check(tag+' two-finger power pull does not shoot before aim release',
                  not held['shooting'] and held['aimPointer'] is not None and
                  held['power']>70 and held['queued'] is True,
                  {'before':before,'after':held})
            touch(cdp,'touchMove',[(1,aim2)])
            final=state(page)
            check(tag+' aim can still move after power finger lifts',
                  not final['shooting'] and final['aim']>held['aim']+.025,
                  {'held':held,'final':final})
            touch(cdp,'touchEnd',[(1,aim2)])
            fired=state(page)
            check(tag+' final aim release fires exactly one queued shot',
                  fired['shooting'] and fired['aimPointer'] is None and
                  fired['queued'] is False and fired['strikePower']>70,
                  fired)
            check(tag+' shot direction uses final aiming finger position',
                  fired['shooting'] and abs(math.atan2(fired['vy'],fired['vx'])-final['aim'])<1e-7,
                  {'fired':fired,'final':final})
            check(tag+' queued shot preserves calibrated impulse and resets slider',
                  fired['shooting'] and abs(fired['impulse']-page.evaluate('shotSpeed(cueStrike.power,false)'))<1e-8
                  and fired['power']==45, fired)

            # Cancelled aiming must never launch the queued shot later.
            reset(page)
            aim0=screen(page,700,285);h0=handle(page)
            powerEnd={'x':h0['x']-(h0['pull'] if h0['focus'] else 0),
                      'y':h0['y']+(0 if h0['focus'] else h0['pull'])}
            touch(cdp,'touchStart',[(1,aim0)])
            touch(cdp,'touchStart',[(1,aim0),(2,h0)])
            touch(cdp,'touchMove',[(1,aim0),(2,powerEnd)])
            touch(cdp,'touchEnd',[(2,powerEnd)])
            touch(cdp,'touchCancel',[])
            cancelled=state(page)
            check(tag+' cancelled aim discards pending shot but retains power',
                  not cancelled['shooting'] and cancelled['aimPointer'] is None and
                  cancelled['queued'] is False and cancelled['power']>70,
                  cancelled)
            page.locator('#shoot').click()
            manual=state(page)
            check(tag+' manual SHOOT remains available after cancelled two-finger pull',
                  manual['shooting'] and manual['impulse']>0 and
                  abs(manual['impulse']-page.evaluate('shotSpeed(cueStrike.power,false)'))<1e-8,
                  manual)

            # Single-finger pull must retain its established auto-fire behaviour.
            reset(page)
            h0=handle(page)
            powerEnd={'x':h0['x']-(h0['pull'] if h0['focus'] else 0),
                      'y':h0['y']+(0 if h0['focus'] else h0['pull'])}
            touch(cdp,'touchStart',[(2,h0)])
            touch(cdp,'touchMove',[(2,powerEnd)])
            touch(cdp,'touchEnd',[])
            solo=state(page)
            check(tag+' ordinary power pull still shoots immediately',
                  solo['shooting'] and solo['strikePower']>70 and solo['power']==45,
                  solo)
            check(tag+' no browser exceptions',not errors,errors)
            if mode=='big':page.locator('#exitFocus').click()
        page.close()
    browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,'limits':'Real Chromium multitouch input; not Samsung physical FPS, shot feel, or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_TWO_FINGER_SHOT_RESULTS.json').write_text(json.dumps(result,indent=2))
print('TWO-FINGER AIM/SHOT',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
