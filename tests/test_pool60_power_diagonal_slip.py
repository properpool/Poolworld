"""A sideways-dominant diagonal thumb slip must not silently weaken a shot.

A touch can travel 14-58px along the narrow power track while moving 100px
sideways. Such a gesture is a sideways slip, not a power pull, and must
neither change the committed shot impulse nor trigger a shot. Intentional
mostly-vertical (or rotated horizontal) pulls remain calibrated.
Chromium pointer regression only, not physical Galaxy A37 acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'details':detail})
    if not ok:print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        modes=('normal','focus') if w==390 else ('normal',)
        for mode in modes:
            page.evaluate('freshRack()')
            if mode=='focus':page.locator('#focusMode').click()
            focused=page.evaluate('focusActive')
            check(f'{w}x{h} {mode} expected orientation',
                  focused==(mode=='focus'),{'focused':focused})
            for target in ('handle','track'):
                for along in (-58,-14,14,58):
                    for cross in (-100,100):
                        page.evaluate('freshRack();showPower(75)')
                        box=page.locator('#handle' if target=='handle' else '#track').bounding_box()
                        x=box['x']+box['width']/2
                        y=box['y']+box['height']/2
                        # Keep track target away from the thumb, including in
                        # rotated focus mode where the slider runs horizontally.
                        if target=='track':
                            if focused:x=box['x']+box['width']*.20
                            else:y=box['y']+box['height']*.20
                        dx,dy=(-along,cross) if focused else (cross,along)
                        page.mouse.move(x,y)
                        page.mouse.down()
                        page.mouse.move(x+dx,y+dy,steps=5)
                        moving=page.evaluate("""() => ({
                            power,shooting,powerDrag,powerPointer,
                            impulse:shotSpeed(power,false)
                        })""")
                        page.mouse.up()
                        after=page.evaluate("""() => ({
                            power,shooting,powerDrag,powerPointer,
                            impulse:shotSpeed(power,false),
                            ui:Number(document.getElementById('strength').value)
                        })""")
                        label=f'{w}x{h} {mode} {target} along={along:+} cross={cross:+}'
                        check(label+' no transient sideways-dominant power drift',
                              abs(moving['power']-75)<.01 and not moving['shooting'],
                              moving)
                        check(label+' selected 75% and physical impulse preserved',
                              abs(after['power']-75)<.01 and after['ui']==75 and
                              abs(after['impulse']-page.evaluate('shotSpeed(75,false)'))<1e-8,
                              after)
                        check(label+' no accidental fire or stuck capture',
                              not after['shooting'] and not after['powerDrag'] and
                              after['powerPointer'] is None,after)
            # A deliberately along-track diagonal pull must remain responsive.
            for along in (-30,30):
                page.evaluate('freshRack();showPower(45)')
                box=page.locator('#handle').bounding_box()
                x=box['x']+box['width']/2;y=box['y']+box['height']/2
                dx,dy=(-along,8) if focused else (8,along)
                page.mouse.move(x,y);page.mouse.down()
                page.mouse.move(x+dx,y+dy,steps=4);page.mouse.up()
                state=page.evaluate('({power,shooting,powerDrag,powerPointer})')
                expected=page.evaluate('([a,b])=>powerFromDrag(a,b,powerTrackLength())',[along,45])
                check(f'{w}x{h} {mode} intentional diagonal pull {along:+} still calibrated',
                      abs(state['power']-expected)<.1 and not state['shooting']
                      and not state['powerDrag'] and state['powerPointer'] is None,
                      {'state':state,'expected':expected})
            if focused:page.evaluate('setTableFocus(false)')
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POWER_DIAGONAL_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Chromium pointer/viewport tests, not physical Samsung or human acceptance.'
},indent=2))
print('POWER DIAGONAL CROSS-AXIS',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
