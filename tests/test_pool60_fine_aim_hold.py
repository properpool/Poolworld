"""Hold-to-repeat fine aim on real Chromium mouse and touch pointers.

A press longer than 550ms must rotate the cue more than a single 0.5-degree
tap, then stop promptly when released or cancelled. Short taps, keyboard
activation, calibrated impulse and match state must remain unchanged.
Browser-only checks: not physical Galaxy A37 or independent acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,ok,details=None):
    checks.append({'name':label,'passed':bool(ok),'details':details})
    if not ok: print('FAIL',label,details,flush=True)
def angle(page):
    return page.evaluate('aim')
def target(page,button):
    b=page.locator(button).bounding_box()
    return b['x']+b['width']/2,b['y']+b['height']/2
def press(page,cdp,x,y,hold_ms=0,cancel=False):
    if cdp:
        cdp.send('Input.dispatchTouchEvent',{'type':'touchStart',
            'touchPoints':[{'x':x,'y':y,'id':4}]})
        if hold_ms: page.wait_for_timeout(hold_ms)
        cdp.send('Input.dispatchTouchEvent',{'type':'touchCancel' if cancel else 'touchEnd',
            'touchPoints':[]})
    else:
        page.mouse.move(x,y)
        page.mouse.down()
        if hold_ms: page.wait_for_timeout(hold_ms)
        if cancel:
            page.evaluate('''()=>{const el=document.activeElement;
              if(el)el.dispatchEvent(new PointerEvent('pointercancel',{bubbles:true,pointerId:1,pointerType:'mouse'}))}''')
        else: page.mouse.up()
def reset(page):
    page.evaluate('''()=>{rack();aim=0;showPower(75);renderDirty=true;}''')
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        for mode in ('mouse','touch'):
            page=browser.new_page(viewport={'width':w,'height':h},
                is_mobile=(mode=='touch'),has_touch=(mode=='touch'))
            page.evaluate('window.requestAnimationFrame=()=>0')
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content(HTML,wait_until='load')
            cdp=page.context.new_cdp_session(page) if mode=='touch' else None
            label=f'{w}x{h} {mode}'
            for button,sign in (('#aimLeft',-1),('#aimRight',1)):
                x,y=target(page,button)
                reset(page)
                press(page,cdp,x,y,0)
                single=angle(page)*180/math.pi
                check(label+button+' short tap is exactly half a degree',
                    abs(single-sign*.5)<.08,single)
                reset(page)
                press(page,cdp,x,y,620)
                held=angle(page)*180/math.pi
                check(label+button+' 620ms hold repeats fine aiming',
                    sign*held>=1.45 and sign*held<=8.0,held)
                page.wait_for_timeout(240)
                stopped=angle(page)*180/math.pi
                check(label+button+' release stops further rotation',
                    abs(stopped-held)<.08,{'released':held,'later':stopped})
                check(label+button+' no shot and preserved strength',
                    page.evaluate('''()=>!shooting&&!gameOver&&Math.abs(power-75)<1e-8
                        &&Math.abs(shotSpeed(power,false)-shotSpeed(75,false))<1e-8'''))
            reset(page)
            page.locator('#aimRight').focus()
            page.keyboard.press('Enter')
            keyboard=angle(page)*180/math.pi
            check(label+' keyboard activation remains one half-degree',
                  abs(keyboard-.5)<.08,keyboard)
            check(label+' no browser errors',not errors,errors)
            page.close()
    browser.close()
result={'passed':sum(x['passed'] for x in checks),'total':len(checks),
        'checks':checks,'limits':'Chromium mouse/touch regression only, not physical Samsung or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_FINE_AIM_HOLD_RESULTS.json').write_text(json.dumps(result,indent=2))
print('FINE AIM HOLD',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
