"""A rotating phone must not remap an active BIG TABLE touch mid-gesture.

On a portrait phone the expanded table is rotated in CSS. A viewport change
to landscape must wait until an active aim, power or cue-placement gesture
has finished before restoring the normal layout. Otherwise placement can
teleport and an aim/power drag may be interrupted. These are Chromium
pointer/resize tests, not physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(label,ok,detail):
    checks.append({'name':label,'passed':bool(ok),'details':detail})
    if not ok:print('FAIL',label,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((360,800),(390,844),(412,915),(430,932)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=True,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        for gesture in ('aim','power','placement'):
            page.set_viewport_size({'width':width,'height':height})
            page.evaluate('if(focusActive){abandonActiveShotGestures();abandonCuePlacementGesture();setTableFocus(false)}')
            page.evaluate('freshRack()')
            page.locator('#focusMode').click()
            if gesture=='power':
                page.evaluate('showPower(75)')
                box=page.locator('#handle').bounding_box()
            else:
                if gesture=='placement':
                    page.evaluate('ballInHand=true;updateHUD()')
                box=page.locator('#table').bounding_box()
            x=box['x']+box['width']/2
            y=box['y']+box['height']/2
            page.mouse.move(x,y)
            page.mouse.down()
            before=page.evaluate("""() => ({
                focusActive,dragAim,powerDrag,placementPointer,
                aimPointer,ballInHand,power,cueX:balls[0].x,cueY:balls[0].y,
                shooting
            })""")
            active=(before['dragAim'] if gesture=='aim' else
                before['powerDrag'] if gesture=='power' else
                before['placementPointer'] is not None)
            tag=f'{width}x{height} {gesture}'
            check(tag+' captures genuine pointer before rotation',
                before['focusActive'] and active and not before['shooting'],before)
            page.set_viewport_size({'width':height,'height':width})
            page.wait_for_timeout(60)
            during=page.evaluate("""() => ({
                focusActive,dragAim,powerDrag,placementPointer,
                cueX:balls[0].x,cueY:balls[0].y,shooting
            })""")
            check(tag+' retains focus layout while touch is active',
                during['focusActive'],during)
            check(tag+' does not move cue ball during viewport rotation',
                abs(during['cueX']-before['cueX'])<.00001 and
                abs(during['cueY']-before['cueY'])<.00001,during)
            page.mouse.up()
            page.evaluate('frame(performance.now())')
            after=page.evaluate("""() => ({
                focusActive,dragAim,powerDrag,placementPointer,aimPointer,
                power,shooting,ballInHand
            })""")
            check(tag+' restores landscape layout after release',
                not after['focusActive'],after)
            check(tag+' retires pointer without accidental shot',
                not after['dragAim'] and not after['powerDrag'] and
                after['placementPointer'] is None and after['aimPointer'] is None and
                not after['shooting'],after)
            if gesture=='power':
                check(tag+' preserves selected 75% shot strength',
                    abs(after['power']-75)<.01,after)
        page.set_viewport_size({'width':width,'height':height})
        page.evaluate('if(focusActive){abandonActiveShotGestures();abandonCuePlacementGesture();setTableFocus(false)}')
        page.evaluate('freshRack()')
        page.locator('#focusMode').click()
        page.set_viewport_size({'width':height,'height':width})
        page.wait_for_timeout(60)
        idle=page.evaluate('({focusActive,dragAim,powerDrag,placementPointer})')
        check(f'{width}x{height} idle rotation still exits focus',
            not idle['focusActive'],idle)
        check(f'{width}x{height} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_FOCUS_ROTATION_GESTURE_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium resize/pointer tests only; physical Samsung A37 and human acceptance release-blocking.'},indent=2))
print('FOCUS ROTATION GESTURE',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
