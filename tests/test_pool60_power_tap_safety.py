"""Prevent unintended shot-strength changes from tapping the power handle or
its enlarged side margins. Deliberate bare-track taps must still select power.

Actual browser pointer/touch events on four viewport sizes; these tests do
not establish physical Samsung touchscreen or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(label,condition,detail):
    checks.append({'name':label,'passed':bool(condition),'details':detail})
    if not condition:print('FAIL',label,detail,flush=True)

def tap(page,cdp,x,y):
    if cdp:
        cdp.send('Input.dispatchTouchEvent',{'type':'touchStart',
          'touchPoints':[{'x':x,'y':y,'id':1}]})
        cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    else:
        page.mouse.move(x,y)
        page.mouse.down()
        page.mouse.up()

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
      executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
      args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
          is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        cdp=page.context.new_cdp_session(page) if w<1000 else None
        track=page.locator('#track').bounding_box()
        panel=page.locator('#powerControl').bounding_box()
        left=(panel['x']+track['x'])/2
        right=(track['x']+track['width']+panel['x']+panel['width'])/2
        for initial in (25,45,75):
            for target in ('handle','left margin','right margin'):
                page.evaluate('(v)=>{rack();showPower(v)}',initial)
                handle=page.locator('#handle').bounding_box()
                y=handle['y']+handle['height']/2
                x=handle['x']+handle['width']/2 if target=='handle' else (
                  left if target=='left margin' else right)
                check(f'{w}x{h} {initial}% {target} target inside expected element',
                  (handle['x']<=x<=handle['x']+handle['width'] if target=='handle'
                   else panel['x']<x<panel['x']+panel['width'] and
                        (x<track['x'] or x>track['x']+track['width']) and
                        track['y']<y<track['y']+track['height']),
                  {'x':x,'y':y,'handle':handle,'track':track,'panel':panel})
                tap(page,cdp,x,y)
                state=page.evaluate('''()=>({
                  power,shooting,powerDrag,powerPointer,
                  label:document.getElementById('powerValue').textContent,
                  impulse:shotSpeed(power,false)
                })''')
                expected_impulse=page.evaluate('(v)=>shotSpeed(v,false)',initial)
                check(f'{w}x{h} {initial}% {target} tap preserves selected impulse',
                  abs(state['power']-initial)<.001 and
                  abs(state['impulse']-expected_impulse)<1e-8 and
                  state['label']==str(initial)+'%',state)
                check(f'{w}x{h} {initial}% {target} tap does not shoot or stick',
                  not state['shooting'] and not state['powerDrag'] and
                  state['powerPointer'] is None,state)
        # Preserve the intentional bare-track tap-to-select shortcut. Pick a
        # point well away from the handle and inside the actual slider.
        page.evaluate('rack();showPower(45)')
        ty=track['y']+track['height']*.9
        tx=track['x']+track['width']/2
        tap(page,cdp,tx,ty)
        result=page.evaluate('''()=>({power,shooting,powerDrag,powerPointer})''')
        desired=5+.9*95
        check(f'{w}x{h} bare-track tap intentionally selects power',
          abs(result['power']-desired)<.1 and not result['shooting'] and
          not result['powerDrag'] and result['powerPointer'] is None,
          {'desired':desired,'result':result})
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POWER_TAP_SAFETY_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Real Chromium touch/mouse events, not physical Samsung acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
