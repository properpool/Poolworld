"""Real Chromium regression: resetting or undoing a match must retire old
aim/power touchscreen gestures, including a pending two-finger shot.
A late finger release must never rotate a new rack or fire an undone shot.
Physical Samsung Galaxy A37/human acceptance remains release-blocking.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, ok, detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)

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
      return {x:r.left+r.width/2,y:r.top+r.height/2,
              pull:Math.max(75,t.clientHeight*.58),
              focus:focusActive,threshold:Math.max(42,t.clientHeight*.4)};
    }""")

def touch(cdp,kind,points):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,
      'touchPoints':[{'x':p['x'],'y':p['y'],'id':i} for i,p in points]})

def state(page):
    return page.evaluate("""()=>({
      aim,aimPointer,dragAim,power,powerDrag,powerPointer,
      queued:pendingAimReleaseShot,shooting,shot:shot!==null,
      breakShot,turn,ballInHand,gameOver,
      x:balls[0].x,y:balls[0].y,vx:balls[0].vx,vy:balls[0].vy
    })""")

def reset(page):
    page.evaluate("""()=>{rack();showPower(45)}""")

def clear(page, tag, expected):
    s=state(page)
    check(tag+' all old input owners and queued shot cleared',
          s['aimPointer'] is None and not s['dragAim'] and
          s['powerPointer'] is None and not s['powerDrag'] and
          not s['queued'],s)
    check(tag+' no unsolicited shot and preserved match state',
          not s['shooting'] and not s['shot'] and
          s['breakShot']==expected['breakShot'] and
          s['turn']==expected['turn'] and
          abs(s['aim']-expected['aim'])<1e-8 and
          abs(s['power']-expected['power'])<1e-8 and
          abs(s['vx'])<1e-8 and abs(s['vy'])<1e-8,s)
    return s

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
            aimStart=screen(page,680,280)
            aimEnd=screen(page,680,350)
            # A captured aiming finger must not rotate a new rack after reset.
            reset(page)
            touch(cdp,'touchStart',[(1,aimStart)])
            touch(cdp,'touchMove',[(1,aimEnd)])
            before=state(page)
            check(tag+' reset aim fixture owns touch',
                  before['aimPointer'] is not None and before['dragAim'],before)
            page.locator('#reset').click()
            fresh=state(page)
            touch(cdp,'touchMove',[(1,screen(page,680,385))])
            touch(cdp,'touchEnd',[])
            clear(page,tag+' reset during aim',fresh)

            # UNDO must restore exact aim, not accept the old finger's release.
            reset(page)
            page.evaluate('aim=.34;history=snapshot();')
            touch(cdp,'touchStart',[(1,aimStart)])
            touch(cdp,'touchMove',[(1,aimEnd)])
            check(tag+' undo aim fixture owns touch',state(page)['aimPointer'] is not None)
            page.locator('#undo').click()
            restored=state(page)
            touch(cdp,'touchMove',[(1,screen(page,680,385))])
            touch(cdp,'touchEnd',[])
            check(tag+' undo restored saved aim',abs(restored['aim']-.34)<1e-8,restored)
            clear(page,tag+' undo during aim',restored)

            # A half-finished power pull can auto-shoot on pointerup; a new
            # rack must cancel it even if the old finger is still down.
            reset(page)
            h0=handle(page)
            end={'x':h0['x']-(h0['pull'] if h0['focus'] else 0),
                 'y':h0['y']+(0 if h0['focus'] else h0['pull'])}
            check(tag+' power fixture exceeds release threshold',
                  h0['pull']>h0['threshold'],h0)
            touch(cdp,'touchStart',[(1,h0)])
            touch(cdp,'touchMove',[(1,end)])
            check(tag+' reset power fixture owns touch',state(page)['powerDrag'])
            page.locator('#reset').click()
            fresh=state(page)
            touch(cdp,'touchEnd',[])
            clear(page,tag+' reset during power',fresh)

            # UNDO during a power pull must not fire the restored position.
            reset(page)
            page.evaluate('showPower(72);history=snapshot()')
            h0=handle(page)
            end={'x':h0['x']-(h0['pull'] if h0['focus'] else 0),
                 'y':h0['y']+(0 if h0['focus'] else h0['pull'])}
            touch(cdp,'touchStart',[(1,h0)])
            touch(cdp,'touchMove',[(1,end)])
            check(tag+' undo power fixture owns touch',state(page)['powerDrag'])
            page.locator('#undo').click()
            restored=state(page)
            touch(cdp,'touchEnd',[])
            check(tag+' undo restored selected power',abs(restored['power']-72)<1e-8,restored)
            clear(page,tag+' undo during power',restored)

            # A two-finger queued shot must not survive NEW RACK.
            reset(page)
            a0=screen(page,680,280)
            h0=handle(page)
            end={'x':h0['x']-(h0['pull'] if h0['focus'] else 0),
                 'y':h0['y']+(0 if h0['focus'] else h0['pull'])}
            touch(cdp,'touchStart',[(1,a0)])
            touch(cdp,'touchStart',[(1,a0),(2,h0)])
            touch(cdp,'touchMove',[(1,a0),(2,end)])
            touch(cdp,'touchEnd',[(2,end)])
            queued=state(page)
            check(tag+' two-finger fixture queued before reset',
                  queued['queued'] and not queued['shooting'],queued)
            page.locator('#reset').click()
            fresh=state(page)
            touch(cdp,'touchEnd',[])
            clear(page,tag+' reset queued two-finger shot',fresh)

            # Following a cancellation, the fresh rack remains playable.
            page.locator('#shoot').click()
            fired=state(page)
            check(tag+' new rack still accepts deliberate SHOOT',
                  fired['shooting'] and fired['shot'] and
                  math.hypot(fired['vx'],fired['vy'])>0,fired)
            check(tag+' no browser exceptions',not errors,errors)
            if mode=='big':page.locator('#exitFocus').click()
        page.close()
    browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,
        'limits':'Real Chromium touch tests; no physical Samsung Galaxy A37 or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_GESTURE_TRANSITION_RESULTS.json').write_text(json.dumps(result,indent=2))
print('GESTURE TRANSITION SAFETY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
