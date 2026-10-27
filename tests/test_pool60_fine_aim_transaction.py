"""Regression: an old held fine-aim button must not rotate a reset or
restored match, or continue changing a subsequent turn after SHOOT.
Real Chromium mouse/touch across four viewports. Not physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details=None):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok: print('FAIL',name,details,flush=True)
def angle(page): return page.evaluate('aim')
def target(page,selector):
    box=page.locator(selector).bounding_box()
    return box['x']+box['width']/2,box['y']+box['height']/2
def down(page,cdp,x,y):
    if cdp:
        cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y,'id':9}]})
    else:
        page.mouse.move(x,y)
        page.mouse.down()
def up(page,cdp):
    if cdp:
        cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    else: page.mouse.up()
def reset(page):
    page.evaluate('''()=>{rack();aim=0;showPower(65);renderDirty=true}''')

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(844,390),(768,1024)):
        for mode in ('mouse','touch'):
            page=browser.new_page(viewport={'width':w,'height':h},
                is_mobile=mode=='touch',has_touch=mode=='touch')
            page.evaluate('window.requestAnimationFrame=()=>0')
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content(HTML,wait_until='load')
            cdp=page.context.new_cdp_session(page) if mode=='touch' else None
            for selector,sign in (('#aimLeft',-1),('#aimRight',1)):
                x,y=target(page,selector)
                label=f'{w}x{h} {mode} {selector}'
                for action in ('rack','restore','shoot'):
                    reset(page)
                    if action=='restore':
                        page.evaluate('''()=>{aim=.7;window.savedFineAimSnapshot=snapshot();aim=0}''')
                    down(page,cdp,x,y)
                    page.wait_for_timeout(360)
                    held=angle(page)
                    check(label+' '+action+' held repeat actually started',
                        sign*held>=math.pi/360*.8,held)
                    if action=='rack':
                        page.evaluate('rack()')
                        expected=0
                    elif action=='restore':
                        page.evaluate('restore(window.savedFineAimSnapshot)')
                        expected=.7
                    else:
                        page.evaluate('''()=>{shoot();shooting=false;shot=null;cueStrike=null;aim=.7}''')
                        expected=.7
                    page.wait_for_timeout(240)
                    during=angle(page)
                    check(label+' '+action+' retired hold before changing new match',
                        abs(during-expected)<.0001,{'expected':expected,'actual':during})
                    up(page,cdp)
                    page.wait_for_timeout(190)
                    after=angle(page)
                    check(label+' '+action+' late release cannot change aim',
                        abs(after-expected)<.0001,{'expected':expected,'actual':after})
                    check(label+' '+action+' strength and no unintended shot',
                        page.evaluate('''()=>Math.abs(power-65)<1e-8&&!shooting&&
                            (shot===null)&&!pendingAimReleaseShot'''))
                    # The next deliberate short tap must remain functional.
                    down(page,cdp,x,y)
                    up(page,cdp)
                    fresh=angle(page)
                    check(label+' '+action+' next deliberate tap works',
                        abs(fresh-after-sign*math.pi/360)<.001,
                        {'before':after,'after':fresh})
                check(label+' no browser errors',not errors,list(errors))
            page.close()
    browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,'limitations':'Browser mouse/touch only; independent physical Samsung and human acceptance still required.'}
(ROOT/'POOL_WORLD_6.0_FINE_AIM_TRANSACTION_RESULTS.json').write_text(json.dumps(result,indent=2))
print('FINE AIM TRANSACTION',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
