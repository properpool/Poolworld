"""A committed SHOOT must retire any earlier held aim/power fingers.

A long-running gesture may outlive a shot on a touchscreen; releasing it after
settlement must not rotate the next turn or fire an unsolicited second shot.
Tests run in Chromium, not on a physical Samsung Galaxy A37.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,detail,flush=True)

def table_point(page,x,y):
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
        pull:Math.max(80,t.clientHeight*.65),focus:focusActive};
    }""")

def send(cdp,kind,points):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,
      'touchPoints':[{'x':p['x'],'y':p['y'],'id':i} for i,p in points]})

def state(page):
    return page.evaluate("""()=>({
      aim,aimPointer,power,powerPointer,dragAim,powerDrag,
      queued:pendingAimReleaseShot,shooting,hasShot:shot!==null,
      speed:Math.hypot(balls[0].vx,balls[0].vy),
      powerHandle:document.getElementById('handle').style.top
    })""")

def fire(page):
    # Actual DOM SHOOT handler without scrolling the table out from under
    # the held touchscreen pointer.
    page.locator('#shoot').evaluate('(b)=>b.click()')

def settle(page):
    # Emulate a fully settled shot without waiting for wall-clock physics.
    # The bug concerns late input ownership, not collision integration.
    page.evaluate("""()=>{
      shooting=false;shot=null;cueStrike=null;
      balls[0].vx=0;balls[0].vy=0;aim=.73;
      showPower(61);renderDirty=true;
    }""")

def clean(page,label,expected_aim=.73,expected_power=61):
    s=state(page)
    check(label+' no second shot',not s['shooting'] and not s['hasShot'] and
          abs(s['speed'])<1e-9,s)
    check(label+' settled aim unchanged',abs(s['aim']-expected_aim)<1e-7,s)
    check(label+' settled power unchanged',abs(s['power']-expected_power)<1e-7,s)
    check(label+' all old gesture owners retired',
          s['aimPointer'] is None and s['powerPointer'] is None and
          not s['dragAim'] and not s['powerDrag'] and not s['queued'],s)

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
        for mode in (['normal','big'] if w<=600 and h>w else ['normal']):
            if mode=='big':page.locator('#focusMode').click()
            label=f'{w}x{h} {mode}'
            # Aiming finger still held when SHOOT is pressed.
            page.evaluate('rack();showPower(58)')
            a=table_point(page,680,280)
            b=table_point(page,680,345)
            c=table_point(page,790,400)
            send(cdp,'touchStart',[(1,a)])
            send(cdp,'touchMove',[(1,b)])
            check(label+' aim fixture owns pointer',state(page)['aimPointer'] is not None)
            fire(page)
            fired=state(page)
            check(label+' held-aim SHOOT starts calibrated shot',
                  fired['shooting'] and fired['hasShot'] and fired['speed']>1,fired)
            check(label+' SHOOT immediately retires held aim',
                  fired['aimPointer'] is None and not fired['dragAim'],fired)
            settle(page)
            send(cdp,'touchMove',[(1,c)])
            send(cdp,'touchEnd',[])
            clean(page,label+' aim late release')

            # Power finger still held after a long pull. The explicit SHOOT
            # must win; a late pointerup must not shoot the next turn.
            page.evaluate('rack();showPower(58)')
            p=handle(page)
            end={'x':p['x']-(p['pull'] if p['focus'] else 0),
                 'y':p['y']+(0 if p['focus'] else p['pull'])}
            send(cdp,'touchStart',[(1,p)])
            send(cdp,'touchMove',[(1,end)])
            held=state(page)
            check(label+' power fixture owns pointer and selects strength',
                  held['powerDrag'] and held['powerPointer'] is not None,held)
            fire(page)
            fired=state(page)
            check(label+' held-power SHOOT starts calibrated shot',
                  fired['shooting'] and fired['hasShot'] and fired['speed']>1,fired)
            check(label+' SHOOT immediately retires held power',
                  fired['powerPointer'] is None and not fired['powerDrag'],fired)
            settle(page)
            send(cdp,'touchEnd',[])
            clean(page,label+' power late release')

            # Two fingers: a completed power pull queues a shot until the
            # aim finger releases. Explicit SHOOT must retire that queue.
            page.evaluate('rack();showPower(58)')
            a=table_point(page,680,280)
            p=handle(page)
            end={'x':p['x']-(p['pull'] if p['focus'] else 0),
                 'y':p['y']+(0 if p['focus'] else p['pull'])}
            send(cdp,'touchStart',[(1,a)])
            send(cdp,'touchStart',[(1,a),(2,p)])
            send(cdp,'touchMove',[(1,a),(2,end)])
            send(cdp,'touchEnd',[(2,end)])
            queued=state(page)
            check(label+' two-finger fixture queues shot',queued['queued'] and
                  not queued['shooting'],queued)
            fire(page)
            fired=state(page)
            check(label+' queued SHOOT starts one shot',
                  fired['shooting'] and fired['hasShot'] and fired['speed']>1,fired)
            check(label+' queued SHOOT retires pending gesture',
                  not fired['queued'] and fired['aimPointer'] is None,fired)
            settle(page)
            send(cdp,'touchEnd',[])
            clean(page,label+' queued late release')
            check(label+' no browser exceptions',not errors,list(errors))
            if mode=='big':page.locator('#exitFocus').click()
        page.close()
    browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,'limitations':'Chromium touch tests only. Physical Samsung Galaxy A37 and independent human acceptance remain required.'}
(ROOT/'POOL_WORLD_6.0_SHOOT_GESTURE_RETIREMENT_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SHOOT GESTURE RETIREMENT',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
