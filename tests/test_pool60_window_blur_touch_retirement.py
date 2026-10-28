"""A blurred mobile game must not retain a half-finished aim, power or cue-placement gesture.

Model a browser window-blur interruption without relying on pointercancel being
delivered. Late releases must not commit a changed aim, weak/strong shot,
ball-in-hand placement or queued two-finger shot. This is Chromium input
regression, not physical Samsung Galaxy A37/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok:print('FAIL',name,json.dumps(details),flush=True)

def point(page,x,y):
    return page.evaluate("""({x,y})=>{
      const r=canvas.getBoundingClientRect();
      return focusActive?{x:r.right-y/H*r.width,y:r.top+x/W*r.height}
        :{x:r.left+x/W*r.width,y:r.top+y/H*r.height};
    }""",{'x':x,'y':y})

def state(page):
    return page.evaluate("""()=>({
      aim,power,shooting,queued:pendingAimReleaseShot,dragAim,
      aimPointer,powerDrag,powerPointer,placementPointer,
      ballInHand,x:balls[0].x,y:balls[0].y,
      impulse:shotSpeed(power,false),turn,breakShot
    })""")

def blur(page):
    # A notification shade, OS focus handoff or browser chrome can blur the
    # window without immediately hiding the document or issuing pointercancel.
    # Dispatch a focus-loss event while the page remains visible.
    page.evaluate("""()=>{
      window.dispatchEvent(new Event('blur'));
    }""")

def retired(s):
    return (not s['dragAim'] and s['aimPointer'] is None and
      not s['powerDrag'] and s['powerPointer'] is None and
      s['placementPointer'] is None and not s['queued'])

def touch(cdp,kind,points):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,
      'touchPoints':[{'x':p['x'],'y':p['y'],'id':i} for i,p in points]})

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
        for mode in (('normal','focus') if w<=390 and h>w else ('normal',)):
            if mode=='focus':page.locator('#focusMode').click()
            tag=f'{w}x{h} {mode}'

            # Window blur during a drag: no stale aim should be committed.
            page.evaluate('freshRack();aim=.25;lastAim=aim;')
            a=point(page,670,280);b=point(page,730,340)
            page.mouse.move(a['x'],a['y']);page.mouse.down()
            page.mouse.move(b['x'],b['y'],steps=3)
            moving=state(page)
            check(tag+' aim fixture moved',moving['dragAim'] and
              abs(moving['aim']-.25)>.05,moving)
            blur(page);blurred=state(page)
            check(tag+' blurred aim restores prior direction and retires pointer',
              retired(blurred) and abs(blurred['aim']-.25)<1e-8,blurred)
            page.mouse.up();late=state(page)
            check(tag+' late aim release cannot rotate cue or shoot',
              retired(late) and abs(late['aim']-.25)<1e-8 and
              not late['shooting'],late)

            # Window blur during a 30px power adjustment: discard the
            # incomplete pull and preserve its calibrated impulse.
            page.evaluate('freshRack();showPower(75)')
            box=page.locator('#handle').bounding_box()
            x=box['x']+box['width']/2;y=box['y']+box['height']/2
            focused=page.evaluate('focusActive')
            page.mouse.move(x,y);page.mouse.down()
            page.mouse.move(x-(30 if focused else 0),
                            y+(0 if focused else 30),steps=3)
            moving=state(page)
            check(tag+' power fixture changed before interruption',
              moving['powerDrag'] and abs(moving['power']-75)>2,moving)
            blur(page);blurred=state(page)
            check(tag+' blurred power restores 75% and calibrated impulse',
              retired(blurred) and abs(blurred['power']-75)<1e-8 and
              abs(blurred['impulse']-page.evaluate('shotSpeed(75,false)'))<1e-8,
              blurred)
            page.mouse.up();late=state(page)
            check(tag+' late power release cannot shoot or alter strength',
              retired(late) and abs(late['power']-75)<1e-8 and
              not late['shooting'],late)

            # A foul-placement drag is a transaction. Losing foreground
            # must restore the legal original cue position and ball-in-hand.
            page.evaluate("""()=>{
              freshRack();balls=[makeBall(0,400,285)];
              ballInHand=true;updateHUD();
            }""")
            a=point(page,450,285);b=point(page,520,310)
            page.mouse.move(a['x'],a['y']);page.mouse.down()
            page.mouse.move(b['x'],b['y'],steps=3)
            moving=state(page)
            check(tag+' placement fixture moved live cue',
              moving['placementPointer'] is not None and
              math.hypot(moving['x']-400,moving['y']-285)>20,moving)
            blur(page);blurred=state(page)
            check(tag+' blurred placement restores cue and leaves ball in hand',
              retired(blurred) and blurred['ballInHand'] and
              abs(blurred['x']-400)<1e-8 and abs(blurred['y']-285)<1e-8,
              blurred)
            page.mouse.up();late=state(page)
            check(tag+' late placement release cannot confirm old drag',
              retired(late) and late['ballInHand'] and
              abs(late['x']-400)<1e-8 and abs(late['y']-285)<1e-8,late)

            # Two real simultaneous touches: power finger releases while
            # aiming finger remains down, queuing an automatic shot.
            page.evaluate('freshRack();showPower(45)')
            a=point(page,680,280)
            box=page.locator('#handle').bounding_box()
            p={'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}
            pull=page.evaluate('Math.max(75,track.clientHeight*.58)')
            end={'x':p['x']-(pull if focused else 0),
                 'y':p['y']+(0 if focused else pull)}
            touch(cdp,'touchStart',[(1,a)])
            touch(cdp,'touchStart',[(1,a),(2,p)])
            touch(cdp,'touchMove',[(1,a),(2,end)])
            touch(cdp,'touchEnd',[(2,end)])
            queued=state(page)
            check(tag+' two-finger fixture queued shot',queued['queued'] and
              not queued['shooting'],queued)
            blur(page);blurred=state(page)
            check(tag+' blurred queued shot retired without firing',
              retired(blurred) and not blurred['shooting'] and
              abs(blurred['power']-45)<1e-8,blurred)
            touch(cdp,'touchEnd',[])
            late=state(page)
            check(tag+' late second finger release cannot shoot',
              retired(late) and not late['shooting'],late)

            # All controls remain usable after the interruption.
            page.evaluate('freshRack()')
            page.locator('#shoot').click()
            fired=state(page)
            check(tag+' deliberate SHOOT still works',
              fired['shooting'] and not fired['queued'],fired)
            if mode=='focus':page.evaluate('setTableFocus(false)')
        check(f'{w}x{h} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_WINDOW_BLUR_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Synthetic window blur with Chromium pointers; physical Samsung/human acceptance still required.'
},indent=2))
print('WINDOW BLUR TOUCH RETIREMENT',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
