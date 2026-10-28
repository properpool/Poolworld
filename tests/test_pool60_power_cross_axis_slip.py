"""Cross-axis thumb slips must not silently replace a calibrated shot strength.

On a narrow power panel, a bare-track touch followed by a sideways swipe
with no travel along the slider is a gesture, not an intentional absolute
power selection. Keep deliberate stationary track taps and handle pulls.
These are Chromium pointer tests, not physical Samsung A37 acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

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
    for w,h in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1100,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        for mode in (('normal','focus') if w<600 and h>w else ('normal',)):
            page.evaluate('freshRack()')
            if mode=='focus':page.locator('#focusMode').click()
            focused=page.evaluate('focusActive')
            check(f'{w}x{h} {mode} mode is active',focused==(mode=='focus'),{'focused':focused})
            for fraction in (.20,.40):
                for direction in (-1,1):
                    page.evaluate('showPower(75)')
                    box=page.locator('#track').bounding_box()
                    if focused:
                        x=box['x']+box['width']*(1-fraction)
                        y=box['y']+box['height']/2
                        release_x,release_y=x,y+direction*64
                    else:
                        x=box['x']+box['width']/2
                        y=box['y']+box['height']*fraction
                        release_x,release_y=x+direction*64,y
                    before=page.evaluate('({power,impulse:shotSpeed(power,false),shooting})')
                    page.mouse.move(x,y)
                    page.mouse.down()
                    page.mouse.move(release_x,release_y,steps=5)
                    page.mouse.up()
                    after=page.evaluate("""() => ({
                        power,impulse:shotSpeed(power,false),shooting,
                        powerDrag,powerPointer,ui:Number(document.getElementById('strength').value)
                    })""")
                    tag=f'{w}x{h} {mode} track={fraction:.0%} cross={direction:+d}'
                    check(tag+' sideways-only swipe preserves selected 75% power',
                        abs(after['power']-75)<.01 and after['ui']==75,
                        {'before':before,'after':after,'box':box})
                    check(tag+' no unintended weak or strong shot impulse',
                        abs(after['impulse']-before['impulse'])<1e-8,
                        {'before':before,'after':after})
                    check(tag+' gesture releases without shooting or stuck capture',
                        not after['shooting'] and not after['powerDrag']
                        and after['powerPointer'] is None,after)
                # An actual stationary bare-track tap must STILL select
                # its absolute location, rather than being disabled entirely.
                page.evaluate('showPower(75)')
                box=page.locator('#track').bounding_box()
                if focused:
                    x=box['x']+box['width']*(1-fraction)
                    y=box['y']+box['height']/2
                else:
                    x=box['x']+box['width']/2
                    y=box['y']+box['height']*fraction
                page.mouse.move(x,y)
                page.mouse.down()
                page.mouse.up()
                tap=page.evaluate('({power,shooting,powerDrag})')
                tag=f'{w}x{h} {mode} {fraction:.0%} stationary track tap'
                check(tag+' still selects intended absolute power',
                    abs(tap['power']-(5+95*fraction))<5 and
                    not tap['shooting'] and not tap['powerDrag'],tap)
            # The handle still supports a genuine along-track pull.
            page.evaluate('showPower(75)')
            handle=page.locator('#handle').bounding_box()
            x=handle['x']+handle['width']/2
            y=handle['y']+handle['height']/2
            page.mouse.move(x,y)
            page.mouse.down()
            if focused:page.mouse.move(x-30,y,steps=5)
            else:page.mouse.move(x,y+30,steps=5)
            page.mouse.up()
            pull=page.evaluate('({power,shooting,powerDrag,powerPointer})')
            check(f'{w}x{h} {mode} intentional handle pull still increases power',
                pull['power']>75 and not pull['shooting'] and
                not pull['powerDrag'] and pull['powerPointer'] is None,pull)
            if focused:page.evaluate('setTableFocus(false)')
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POWER_CROSS_AXIS_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Chromium mouse-pointer and rotated mobile viewport tests; no physical Samsung A37 or independent human acceptance.'
},indent=2))
print('POWER CROSS-AXIS SLIP',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
