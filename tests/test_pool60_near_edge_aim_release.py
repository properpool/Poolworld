"""Near-edge final-release precision aiming regression.

When a captured cue-side touch or precision mouse pointer lifts a few CSS pixels
outside the canvas without a pointermove, its last displacement must be used.
A distant off-table release must still be rejected. Browser emulation only.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, ok, detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)

def angle_error(a,b):
    return abs(math.atan2(math.sin(a-b),math.cos(a-b)))

def near_edge(page):
    return page.evaluate("""()=>{
      const r=canvas.getBoundingClientRect(), c=balls[0];
      const start=focusActive
        ?{x:r.right-c.y/H*r.width,y:r.top+c.x/W*r.height}
        :{x:r.left+c.x/W*r.width,y:r.top+c.y/H*r.height};
      const end=focusActive
        ?{x:start.x,y:r.bottom+12}
        :{x:r.right+12,y:start.y};
      return {start,end,delta:focusActive?end.y-start.y:end.x-start.x};
    }""")

def pointer_up(page,kind,x,y):
    page.evaluate("""({kind,x,y})=>{
      canvas.dispatchEvent(new PointerEvent('pointerup',{
        pointerId:aimPointer,pointerType:kind,clientX:x,clientY:y,
        bubbles:true
      }));
    }""",{'kind':kind,'x':x,'y':y})

def setup(page,angle):
    page.evaluate("""a=>{
      rack();balls[0].x=R-rad-26;balls[0].y=(T+B)/2;
      aim=a;lastAim=a;showPower(70);renderDirty=true;
    }""",angle)

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
        cdp=page.context.new_cdp_session(page)
        for mode in (('normal','big') if w<=600 and h>w else ('normal',)):
            if mode=='big': page.locator('#focusMode').click()
            label=f'{w}x{h} {mode}'
            setup(page,.52)
            coords=near_edge(page)
            p=coords['start'];q=coords['end']
            cdp.send('Input.dispatchTouchEvent',{'type':'touchStart',
                'touchPoints':[{'x':p['x'],'y':p['y'],'id':1}]})
            started=page.evaluate('({fine:aimFineDrag,active:dragAim,ptr:aimPointer,aim})')
            check(label+' cue-side touch owns relative aim',
                started['fine'] and started['active'] and started['ptr'] is not None,started)
            check(label+' near-edge release is modest',
                5<coords['delta']<60,coords)
            pointer_up(page,'touch',q['x'],q['y'])
            actual=page.evaluate('({aim,dragAim,aimPointer,power,shooting})')
            expected=.52+coords['delta']*.13*math.pi/180
            check(label+' coalesced cue-side release uses final edge displacement',
                angle_error(actual['aim'],expected)<.002,
                {'actual':actual,'expected':expected,'delta':coords['delta']})
            check(label+' cue-side edge release retires gesture without firing',
                not actual['dragAim'] and actual['aimPointer'] is None
                and not actual['shooting'] and actual['power']==70,actual)
            shot=page.evaluate("""()=>{
                breakShot=false;shoot();
                return {aim:Math.atan2(balls[0].vy,balls[0].vx),
                  speed:Math.hypot(balls[0].vx,balls[0].vy),
                  expected:shotSpeed(70,false)};
            }""")
            check(label+' actual shot follows final edge angle at calibrated power',
                angle_error(shot['aim'],expected)<.002
                and abs(shot['speed']-shot['expected'])<1e-8,shot)
            cdp.send('Input.dispatchTouchEvent',
                     {'type':'touchCancel','touchPoints':[]})

            # Mouse precision drags also have a captured final pointerup.
            setup(page,.34)
            page.evaluate('precisionAim=true')
            coords=near_edge(page);p=coords['start'];q=coords['end']
            cdp.send('Input.dispatchMouseEvent',{'type':'mouseMoved',
                'x':p['x'],'y':p['y'],'buttons':0})
            cdp.send('Input.dispatchMouseEvent',{'type':'mousePressed',
                'x':p['x'],'y':p['y'],'button':'left','buttons':1,'clickCount':1})
            started=page.evaluate('({precisionAim,dragAim,aimPointer})')
            check(label+' precision mouse owns pointer',
                started['precisionAim'] and started['dragAim']
                and started['aimPointer'] is not None,started)
            pointer_up(page,'mouse',q['x'],q['y'])
            actual=page.evaluate('({aim,dragAim,aimPointer,power})')
            expected=.34+coords['delta']*.13*math.pi/180
            check(label+' coalesced precision mouse release uses edge displacement',
                angle_error(actual['aim'],expected)<.002,{'actual':actual,'expected':expected})
            check(label+' precision mouse edge release clears ownership and power stays',
                not actual['dragAim'] and actual['aimPointer'] is None
                and actual['power']==70,actual)
            cdp.send('Input.dispatchMouseEvent',{'type':'mouseReleased',
                'x':q['x'],'y':q['y'],'button':'left','buttons':0,'clickCount':1})
            page.evaluate('precisionAim=false')

            # Extreme off-screen touch is accidental: keep old safety behaviour.
            setup(page,.76)
            coords=near_edge(page);p=coords['start']
            cdp.send('Input.dispatchTouchEvent',{'type':'touchStart',
                'touchPoints':[{'x':p['x'],'y':p['y'],'id':1}]})
            pointer_up(page,'touch',0,0)
            actual=page.evaluate('({aim,dragAim,aimPointer})')
            check(label+' distant off-table release does not whip cue around',
                angle_error(actual['aim'],.76)<1e-8
                and not actual['dragAim'] and actual['aimPointer'] is None,actual)
            cdp.send('Input.dispatchTouchEvent',
                     {'type':'touchCancel','touchPoints':[]})
        check(f'{w}x{h} no browser errors',not errors,errors)
        page.close()
    browser.close()

result={'total':len(checks),'passed':sum(x['passed'] for x in checks),
        'checks':checks,'limits':'Chromium pointer emulation, not Samsung physical acceptance'}
(ROOT/'POOL_WORLD_6.0_NEAR_EDGE_AIM_RESULTS.json').write_text(json.dumps(result,indent=2))
print(f"Near-edge final-release precision aiming: {result['passed']}/{result['total']}",flush=True)
if result['passed']!=result['total']:sys.exit(1)
