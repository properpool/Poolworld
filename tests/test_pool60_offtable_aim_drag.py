"""Off-table pointer capture must not steer direct cue aim.

On a narrow phone table, a finger can leave the cloth during a drag while
the canvas retains pointer capture. Its out-of-bounds coordinate must not
overwrite the last valid direction. Relative cue-side fine aiming is allowed
to continue beyond the table. Chromium input tests, not Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)
def diff(a,b):
    return abs(math.atan2(math.sin(a-b),math.cos(a-b)))
def touch(cdp,kind,x,y):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,
        'touchPoints':[] if kind in ('touchEnd','touchCancel')
        else [{'x':x,'y':y,'id':1}]})

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
                              is_mobile=w<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        box=page.locator('#table').bounding_box()
        label=f'{w}x{h}'
        x0=box['x']+box['width']*.76
        y0=box['y']+box['height']*.26
        xi=box['x']+box['width']*.68
        yi=box['y']+box['height']*.74
        xo=box['x']+box['width']+42
        yo=box['y']+box['height']*.72
        # Real mouse events: pointer capture keeps dispatching moves to the
        # table even after the cursor crosses the cloth's right boundary.
        page.evaluate('rack();aim=0;renderDirty=false')
        page.mouse.move(x0,y0)
        page.mouse.down()
        page.mouse.move(xi,yi)
        inside=page.evaluate('aim')
        check(label+' mouse direct drag establishes inside aim',
              diff(inside,0)>.1,inside)
        page.mouse.move(xo,yo)
        outside=page.evaluate('aim')
        check(label+' mouse outside drag preserves last inside aim',
              diff(outside,inside)<1e-8,
              {'inside':inside,'outside':outside})
        page.mouse.up()
        ended=page.evaluate('({aim,dragAim,aimPointer})')
        check(label+' mouse outside release preserves last inside aim',
              diff(ended['aim'],inside)<1e-8,ended)
        check(label+' mouse outside release unlocks input',
              not ended['dragAim'] and ended['aimPointer'] is None,ended)
        # Actual Chromium touch events, not synthetic JS-only dispatch.
        cdp=page.context.new_cdp_session(page)
        page.evaluate('rack();aim=0;renderDirty=false')
        touch(cdp,'touchStart',x0,y0)
        touch(cdp,'touchMove',xi,yi)
        inside=page.evaluate('aim')
        check(label+' touch direct drag establishes inside aim',
              diff(inside,0)>.1,inside)
        touch(cdp,'touchMove',xo,yo)
        outside=page.evaluate('aim')
        check(label+' touch outside drag preserves last inside aim',
              diff(outside,inside)<1e-8,
              {'inside':inside,'outside':outside})
        touch(cdp,'touchEnd',xo,yo)
        ended=page.evaluate('({aim,dragAim,aimPointer,shooting})')
        check(label+' touch outside release retains inside aim',
              diff(ended['aim'],inside)<1e-8,ended)
        check(label+' touch outside release does not shoot or stick',
              not ended['dragAim'] and ended['aimPointer'] is None
              and not ended['shooting'],ended)
        # Crossing the top edge is also out of bounds; direct aim must
        # ignore that move, independently of the right-edge scenario.
        page.evaluate('rack();aim=0')
        page.mouse.move(x0,y0)
        page.mouse.down()
        page.mouse.move(xi,yi)
        inside=page.evaluate('aim')
        page.mouse.move(xi,box['y']-24)
        check(label+' top-edge direct drag preserves aim',
              diff(page.evaluate('aim'),inside)<1e-8)
        page.mouse.up()
        check(label+' no browser errors',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,'limits':'Chromium mouse/touch input, not physical Samsung FPS or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_OFFTABLE_AIM_RESULTS.json').write_text(json.dumps(result,indent=2))
print('OFFTABLE AIM',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
