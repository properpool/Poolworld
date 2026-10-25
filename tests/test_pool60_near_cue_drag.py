"""Regression: touch gestures starting on the cue ball remain relative fine aim.

Uses Chromium CDP touch events on four form factors; this is NOT physical
Samsung or independent human playability testing.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import math, json, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, ok, detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    print(('PASS' if ok else 'FAIL'),name,detail,flush=True)

def touch(cdp,kind,x,y):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[] if kind in ('touchEnd','touchCancel') else [{'x':x,'y':y,'id':1}]})

def difference(a,b):
    return abs(math.atan2(math.sin(a-b),math.cos(a-b)))

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        page.evaluate('rack();aim=Math.PI/3')
        box=page.locator('#table').bounding_box()
        cue=page.evaluate('({x:balls[0].x,y:balls[0].y})')
        x=box['x']+cue['x']*box['width']/1100
        y=box['y']+cue['y']*box['height']/570
        cdp=page.context.new_cdp_session(page)
        start=math.pi/3
        touch(cdp,'touchStart',x+8,y+4)
        check(f'{w} cue landing preserves original aim',difference(page.evaluate('aim'),start)<1e-8)
        check(f'{w} cue landing activates fine drag',page.evaluate('aimFineDrag && dragAim && aimPointer!==null'))
        touch(cdp,'touchMove',x+63,y+4)
        mid=page.evaluate('aim')
        expected=start+55*.13*math.pi/180
        check(f'{w} crossing cue guard produces relative 55px rotation',difference(mid,expected)<.002,{'actual':mid,'expected':expected})
        touch(cdp,'touchMove',x+93,y+4)
        end=page.evaluate('aim')
        expected=start+85*.13*math.pi/180
        check(f'{w} extended 85px gesture stays smooth',difference(end,expected)<.002,{'actual':end,'expected':expected})
        touch(cdp,'touchEnd',x+93,y+4)
        check(f'{w} release clears fine drag state',page.evaluate('!aimFineDrag && !dragAim && aimPointer===null'))
        check(f'{w} release commits intended direction',difference(page.evaluate('aim'),expected)<.002)
        page.evaluate('aim=Math.PI/3')
        touch(cdp,'touchStart',x+9,y+5)
        touch(cdp,'touchMove',x+61,y+5)
        changed=page.evaluate('aim')
        touch(cdp,'touchCancel',x+61,y+5)
        check(f'{w} cancellation restores aim',difference(changed,start)>.03 and difference(page.evaluate('aim'),start)<1e-8)
        check(f'{w} cancellation clears pointer',page.evaluate('!aimFineDrag && !dragAim && aimPointer===null'))
        page.evaluate('aim=0')
        farx=box['x']+box['width']*.8
        fary=box['y']+box['height']*.25
        touch(cdp,'touchStart',farx,fary)
        touch(cdp,'touchEnd',farx,fary)
        check(f'{w} distant finger still supports absolute aim',difference(page.evaluate('aim'),0)>.15)
        page.evaluate('showPower(65)')
        b=page.locator('#shoot').bounding_box()
        page.touchscreen.tap(b['x']+b['width']/2,b['y']+b['height']/2)
        check(f'{w} shot control fires after fine aiming',page.evaluate('shooting && Math.hypot(balls[0].vx,balls[0].vy)>3'))
        check(f'{w} no browser exceptions',not errors,errors)
        page.close()
    browser.close()
summary={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'limits':'Chromium touch emulation only; no physical Samsung or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_NEAR_CUE_DRAG_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)
