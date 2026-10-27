"""Regression: portrait BIG TABLE must never lie about selected shot power.
A resized/reparented slider can show its thumb at the wrong percentage while
the actual cue impulse remains unchanged. Chromium only; Samsung/human release
acceptance remains mandatory.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys, math

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks = []
def check(name, passed, detail=None):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',name,detail,flush=True)

def measure(page):
    return page.evaluate("""() => {
      const h=track.clientHeight;
      const expected=(power-5)/95*(h-22)+11;
      return {focus:focusActive, power, h, expected,
        top:parseFloat($('handle').style.top),
        fill:parseFloat($('fill').style.height),
        output:$('powerValue').textContent,
        slider:Number($('strength').value),
        impulse:shotSpeed(power,false), shooting, gameOver, ballInHand,
        balls:balls.map(b=>[b.id,b.x,b.y,b.vx,b.vy,b.potted])};
    }""")

def aligned(s):
    return s['h']>0 and abs(s['top']-s['expected'])<1.1 and abs(s['fill']-s['expected'])<1.1

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(412,915),(375,667)):
        page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        tag=f'{w}x{h}'
        for selected in (25,45,75,95):
            page.evaluate('(p)=>showPower(p)',selected)
            initial=measure(page)
            check(f'{tag} {selected}% normal handle aligned',aligned(initial),initial)
            page.locator('#focusMode').click()
            focused=measure(page)
            check(f'{tag} {selected}% BIG TABLE handle aligned',aligned(focused),focused)
            check(f'{tag} {selected}% BIG TABLE retains actual power and displayed percentage',
                  focused['focus'] and abs(focused['power']-selected)<.001 and
                  focused['output']==str(selected)+'%' and focused['slider']==selected,focused)
            check(f'{tag} {selected}% BIG TABLE retains calibrated impulse',
                  abs(focused['impulse']-initial['impulse'])<1e-10,focused)
            check(f'{tag} {selected}% BIG TABLE preserves match and does not shoot',
                  not focused['shooting'] and not focused['gameOver'] and
                  not focused['ballInHand'] and focused['balls']==initial['balls'],focused)
            page.locator('#exitFocus').click()
            restored=measure(page)
            check(f'{tag} {selected}% exit BIG TABLE restores thumb position',aligned(restored),restored)
            check(f'{tag} {selected}% exit preserves selected power and impulse',
                  not restored['focus'] and restored['power']==selected and
                  abs(restored['impulse']-initial['impulse'])<1e-10,restored)
        # The power slider can change dimensions without changing the value
        # when the browser UI or orientation/layout alters available space.
        page.evaluate('showPower(75)')
        page.locator('#focusMode').click()
        prior=measure(page)
        page.evaluate("track.style.height='145px'")
        try:
            page.wait_for_function("""() => {
              const h=track.clientHeight,expected=(power-5)/95*(h-22)+11;
              return h>0 && Math.abs(parseFloat($('handle').style.top)-expected)<1.1
                && Math.abs(parseFloat($('fill').style.height)-expected)<1.1;
            }""",timeout=1500)
        except Exception:
            pass
        resized=measure(page)
        check(f'{tag} live focused track resize recalculates handle and fill',aligned(resized),{'before':prior,'after':resized})
        check(f'{tag} live focused track resize changes height',abs(resized['h']-prior['h'])>5,{'before':prior['h'],'after':resized['h']})
        check(f'{tag} live focused resize preserves 75% calibrated shot strength',
              resized['power']==75 and abs(resized['impulse']-prior['impulse'])<1e-10,resized)
        page.locator('#exitFocus').click()
        page.evaluate("track.style.height=''")
        check(f'{tag} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

result={'passed':sum(x['passed'] for x in checks),'total':len(checks),
    'checks':checks,'limits':'Chromium only; physical Samsung A37 and independent human acceptance remain release-blocking.'}
(ROOT/'POOL_WORLD_6.0_FOCUS_POWER_REFLOW_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
