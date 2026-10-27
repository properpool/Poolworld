"""Regression for a finger dragging the power handle from a chosen strength.

The original pull mapping discarded the existing 25/45/75% selection and
jumped to a near-minimum value after a 12px movement. This is an actual
weak-shot input defect, not a benchmark of physical-device performance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label, ok, detail):
    checks.append({'name':label,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',label,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        box=page.locator('#track').bounding_box()
        x=box['x']+box['width']*.5
        y=box['y']+box['height']*.50
        distance=max(65,box['height']*.65)
        for initial in (25,45,75):
            for dy in (-24,-12,12,24):
                page.evaluate('(p)=>{rack();showPower(p)}',initial)
                page.mouse.move(x,y)
                page.mouse.down()
                page.mouse.move(x,y+dy,steps=2)
                moving=page.evaluate('''()=>({
                    power,shooting,powerDrag,powerPointer,
                    value:document.querySelector('#powerValue')?.textContent
                })''')
                fraction=min(1,abs(dy)/distance)
                expected=(initial+(100-initial)*fraction if dy>0
                          else initial-(initial-5)*fraction)
                label=f'{w}x{h} start {initial}% drag {dy:+}px'
                check(label+' retains relative selected power',
                      abs(moving['power']-expected)<.03,
                      {'expected':expected,'moving':moving,'trackHeight':box['height']})
                check(label+' moves strength in intended direction',
                      (moving['power']>initial if dy>0 else moving['power']<initial),
                      moving)
                check(label+' does not fire while dragging',
                      not moving['shooting'] and moving['powerDrag'],moving)
                page.mouse.up()
                released=page.evaluate('''()=>({
                    power,shooting,powerDrag,powerPointer
                })''')
                check(label+' release retains selection without shooting',
                      abs(released['power']-expected)<.03 and
                      not released['shooting'] and not released['powerDrag'] and
                      released['powerPointer'] is None,
                      {'expected':expected,'released':released})
                if (initial,dy) in ((45,24),(75,-24)):
                    page.locator('#shoot').click()
                    actual=page.evaluate('''()=>({
                        shooting,speed:Math.hypot(balls[0].vx,balls[0].vy),
                        expected:shotSpeed(power,breakShot)
                    })''')
                    check(label+' SHOOT uses selected physical impulse',
                          actual['shooting'] and abs(actual['speed']-actual['expected'])<.001,
                          actual)
        check(f'{w}x{h} no JS exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_RELATIVE_POWER_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Chromium pointer tests only; not physical Samsung/human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks): sys.exit(1)
