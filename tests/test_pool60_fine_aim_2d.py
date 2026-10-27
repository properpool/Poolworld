"""2D cue-side fine aiming: vertical thumb drags must not be ignored.

Chromium CDP touch events across four viewports; no physical Samsung
or independent human acceptance is implied. Existing horizontal sensitivity
and direct far-table aim are protected.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,detail,flush=True)
def err(a,b):
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
        cue=page.evaluate('({x:balls[0].x,y:balls[0].y})')
        cx=box['x']+cue['x']*box['width']/1100
        cy=box['y']+cue['y']*box['height']/570
        cdp=page.context.new_cdp_session(page)
        label=f'{w}x{h}'
        # A horizontal cue direction requires a vertical thumb movement
        # to rotate the cue. Former code read only clientX and ignored it.
        page.evaluate('rack();aim=0;renderDirty=false')
        touch(cdp,'touchStart',cx+6,cy+4)
        check(label+' near-cue touch preserves aim',
              err(page.evaluate('aim'),0)<1e-9)
        check(label+' touch enters fine drag',page.evaluate(
              'aimFineDrag && dragAim && aimPointer!==null'))
        touch(cdp,'touchMove',cx+6,cy+44)
        angle=page.evaluate('aim')
        expected=40*.13*math.pi/180
        check(label+' vertical thumb drag rotates horizontal cue',
              err(angle,expected)<.002,{'actual':angle,'expected':expected})
        touch(cdp,'touchEnd',cx+6,cy+44)
        check(label+' vertical release retains aim and clears capture',
              err(page.evaluate('aim'),expected)<.002 and page.evaluate(
              '!dragAim && !aimFineDrag && aimPointer===null'))
        # Separate upward gesture avoids a CDP synthetic touchMove jumping
        # through the initial touch point, which can suppress a move event.
        page.evaluate('rack();aim=0')
        touch(cdp,'touchStart',cx+6,cy+4)
        touch(cdp,'touchMove',cx+6,cy-32)
        angle=page.evaluate('aim')
        expected=-36*.13*math.pi/180
        check(label+' opposite vertical drag reverses cue rotation',
              err(angle,expected)<.002,{'actual':angle,'expected':expected})
        touch(cdp,'touchEnd',cx+6,cy-32)
        check(label+' vertical aim controls actual shot direction',
              page.evaluate('''() => {
                breakShot=false;showPower(75);shoot();
                return Math.hypot(balls[0].vx,balls[0].vy)>4 &&
                Math.abs(Math.atan2(balls[0].vy,balls[0].vx)-aim)<.002
              }'''))
        # Diagonal near-cue drags must preserve BOTH finger axes.
        page.evaluate('rack();aim=0')
        touch(cdp,'touchStart',cx+6,cy+4)
        touch(cdp,'touchMove',cx+31,cy+34)
        expected=(25+30)*.13*math.pi/180
        check(label+' diagonal drag includes both axes',
              err(page.evaluate('aim'),expected)<.002,
              {'actual':page.evaluate('aim'),'expected':expected})
        touch(cdp,'touchCancel',cx+31,cy+34)
        check(label+' cancelled diagonal drag restores initial aim',
              err(page.evaluate('aim'),0)<1e-9 and page.evaluate(
              '!dragAim && aimPointer===null'))
        # A vertically aimed cue must not rotate when thumb slides
        # along its axis. Horizontal fine aim remains backward-compatible.
        page.evaluate('rack();aim=-Math.PI/2')
        touch(cdp,'touchStart',cx+6,cy+4)
        touch(cdp,'touchMove',cx+6,cy+44)
        check(label+' along-cue vertical movement stays stable',
              err(page.evaluate('aim'),-math.pi/2)<.002)
        touch(cdp,'touchEnd',cx+6,cy+44)
        page.evaluate('rack();aim=-Math.PI/2')
        touch(cdp,'touchStart',cx+6,cy+4)
        touch(cdp,'touchMove',cx+46,cy+4)
        expected=-math.pi/2+40*.13*math.pi/180
        check(label+' perpendicular horizontal fine drag preserved',
              err(page.evaluate('aim'),expected)<.002,
              {'actual':page.evaluate('aim'),'expected':expected})
        touch(cdp,'touchEnd',cx+46,cy+4)
        # Far-table touches must retain direct absolute pointing.
        page.evaluate('rack();aim=0')
        x=box['x']+box['width']*.8
        y=box['y']+box['height']*.25
        touch(cdp,'touchStart',x,y)
        touch(cdp,'touchEnd',x,y)
        check(label+' distant tap still uses direct aiming',
              err(page.evaluate('aim'),0)>.1)
        check(label+' no browser errors',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,'limits':'Emulated Chromium touch, not physical Samsung/human acceptance.'}
(ROOT/'POOL_WORLD_6.0_FINE_AIM_2D_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
