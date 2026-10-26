"""Real Chromium quick-release power input regression.

A fast pointer release may reach the slider without any intermediate pointermove.
The release coordinate must determine actual shot velocity; otherwise a strong
pull fires at the stale 45% default. Browser emulation is not physical Samsung QA.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys, math

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok: print('FAIL',name,details,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        cdp=page.context.new_cdp_session(page)
        for fraction in (.45,.60):
            page.evaluate('rack();showPower(45)')
            box=page.locator('#track').bounding_box()
            x=box['x']+box['width']*.5
            y=box['y']+box['height']*.10
            end=y+box['height']*fraction
            # Intentionally NO mouseMoved between mousePressed and mouseReleased.
            # This exposes stale power on a rapid gesture with a coalesced move.
            page.mouse.move(x,y)
            page.mouse.down()
            cdp.send('Input.dispatchMouseEvent',{
                'type':'mouseReleased','x':x,'y':end,'button':'left','buttons':0
            })
            state=page.evaluate('''() => ({
                shooting, speed:Math.hypot(balls[0].vx,balls[0].vy),
                powerDrag,powerPointer,power,
                breakShot:shot?.breakShot
            })''')
            expected_level=5+95*min(1,(box['height']*fraction)/max(65,box['height']*.65))
            expected_speed=(.45+7.9*(expected_level/100)**.92)*1.17
            label=f'{w}x{h} {int(fraction*100)}%-track immediate release'
            check(label+' starts break',state['shooting'] and state['breakShot'] is True,state)
            check(label+' uses release-coordinate power',
                abs(state['speed']-expected_speed)<.02,
                {'actual':state['speed'],'expected':expected_speed,'state':state})
            check(label+' releases pointer',not state['powerDrag'] and state['powerPointer'] is None,state)
        # If the finger pulls down and returns to the start, it must not
        # leave an unintended maximum-power selection or release a shot.
        page.evaluate('rack();showPower(45)')
        box=page.locator('#track').bounding_box()
        x=box['x']+box['width']*.5
        y=box['y']+box['height']*.1
        page.mouse.move(x,y);page.mouse.down()
        page.mouse.move(x,y+box['height']*.60,steps=4)
        page.mouse.move(x,y,steps=4);page.mouse.up()
        state=page.evaluate('''() => ({shooting,power,powerDrag})''')
        check(f'{w}x{h} reversed pull restores initial 45% without shot',
            not state['shooting'] and not state['powerDrag'] and abs(state['power']-45)<.01,state)
        check(f'{w}x{h} no JS exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(item['passed'] for item in checks)
(ROOT/'POOL_WORLD_6.0_QUICK_RELEASE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Real Chromium pointer dispatch, not physical Samsung/human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
