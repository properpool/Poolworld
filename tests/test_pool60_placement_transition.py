"""Real Chromium regression: a foul placement drag must not survive a
new rack, UNDO, or explicit PLACE CUE confirmation.

Previously pointerup from the OLD captured gesture could move the cue ball
in a freshly reset match, overwrite an undone state, or reposition a cue
ball after the player had explicitly confirmed its placement. This tests
actual touchscreen input on four viewports and portrait BIG TABLE mode.
Physical Samsung/human acceptance remains mandatory.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)

def state(page):
    return page.evaluate("""() => ({
        x:balls[0].x,y:balls[0].y,ballInHand,turn,breakShot,shooting,
        gameOver,shot:shot!==null,placementActive:placementPointer!==null,
        power,aim,label:document.getElementById('shoot').textContent,
        valid:canPlace(balls[0].x,balls[0].y)
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

def begin_drag(page,cdp,xy=(430,230)):
    s=state(page)
    touch(cdp,'touchStart',screen(page,s['x'],s['y']))
    touch(cdp,'touchMove',screen(page,*xy))
    return state(page)

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
        for mode in (['normal','big'] if w<=600 and h>w else ['normal']):
            if mode=='big':page.locator('#focusMode').click()
            tag=f'{w}x{h} {mode}'
            check(tag+' legal destination',page.evaluate('canPlace(430,230)'))
            check(tag+' second legal destination',page.evaluate('canPlace(475,250)'))

            # RESET while a captured foul-placement touch is down.
            foul(page)
            preview=begin_drag(page,cdp)
            check(tag+' reset fixture has active foul drag',
                  preview['ballInHand'] and preview['placementActive'],preview)
            page.locator('#reset').click()
            reset=state(page)
            touch(cdp,'touchMove',screen(page,475,250))
            touch(cdp,'touchEnd')
            after=state(page)
            check(tag+' reset immediately cancels old placement capture',
                  not reset['placementActive'] and not reset['ballInHand'],reset)
            check(tag+' stale touch release cannot move new rack cue ball',
                  after['breakShot'] and after['turn']==1 and
                  not after['ballInHand'] and not after['placementActive'] and
                  abs(after['x']-reset['x'])<1e-7 and
                  abs(after['y']-reset['y'])<1e-7 and
                  not after['shooting'] and not after['shot'],after)

            # PLACE CUE explicitly confirms the current preview. The old
            # finger may continue to move but must not reposition afterwards.
            foul(page)
            preview=begin_drag(page,cdp)
            check(tag+' confirm fixture previews legal position',
                  preview['ballInHand'] and preview['placementActive'] and
                  abs(preview['x']-430)<1.5 and abs(preview['y']-230)<1.5,preview)
            page.locator('#shoot').click()
            confirmed=state(page)
            touch(cdp,'touchMove',screen(page,475,250))
            touch(cdp,'touchEnd')
            after=state(page)
            check(tag+' PLACE CUE clears pending placement gesture',
                  not confirmed['ballInHand'] and not confirmed['placementActive'] and
                  confirmed['label']=='SHOOT',confirmed)
            check(tag+' stale release cannot override confirmed cue placement',
                  not after['ballInHand'] and not after['placementActive'] and
                  abs(after['x']-confirmed['x'])<1e-7 and
                  abs(after['y']-confirmed['y'])<1e-7 and
                  not after['shooting'] and not after['shot'],after)

            # UNDO during a drag restores the exact saved ball-in-hand state.
            foul(page)
            origin=state(page)
            page.evaluate('history=snapshot()')
            preview=begin_drag(page,cdp)
            check(tag+' undo fixture has active drag',
                  preview['ballInHand'] and preview['placementActive'],preview)
            page.locator('#undo').click()
            restored=state(page)
            touch(cdp,'touchMove',screen(page,475,250))
            touch(cdp,'touchEnd')
            after=state(page)
            check(tag+' UNDO clears old placement capture',
                  restored['ballInHand'] and not restored['placementActive'] and
                  abs(restored['x']-origin['x'])<1e-7 and
                  abs(restored['y']-origin['y'])<1e-7,restored)
            check(tag+' stale release cannot overwrite UNDO match state',
                  after['ballInHand'] and not after['placementActive'] and
                  after['turn']==origin['turn'] and after['label']=='PLACE CUE' and
                  abs(after['x']-origin['x'])<1e-7 and
                  abs(after['y']-origin['y'])<1e-7 and
                  not after['shooting'] and not after['shot'],after)
            check(tag+' no browser exceptions',not errors,errors)
            if mode=='big':page.locator('#exitFocus').click()
        page.close()
    browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,
        'limits':'Chromium touchscreen regression, not independent physical Samsung A37/human acceptance.'}
(ROOT/'POOL_WORLD_6.0_PLACEMENT_TRANSITION_RESULTS.json').write_text(json.dumps(result,indent=2))
print('PLACEMENT TRANSITIONS',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
