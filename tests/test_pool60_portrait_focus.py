"""Portrait mobile table-size and rotated-focus touch regression.
A narrow 390px portrait screen renders the 1100-unit table too small to aim
comfortably. Optional full-table landscape focus must enlarge balls and retain
accurate touch/power geometry. Chromium only; NOT physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,passed,detail=None):
    checks.append({'name':label,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',label,detail,flush=True)
def touch(cdp,kind,x,y):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,
        'touchPoints':[] if kind in ('touchEnd','touchCancel') else [{'x':x,'y':y,'id':1}]})
def angle_error(a,b):
    return abs(math.atan2(math.sin(a-b),math.cos(a-b)))

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
        label=f'{w}x{h}'
        before=page.locator('#table').bounding_box()
        baseline_diameter=2*12.2*before['width']/1100
        check(label+' portrait ball diameter is initially tiny (<10 CSS px)',
              baseline_diameter<10,baseline_diameter)
        check(label+' focus entry exists',page.locator('#focusMode').count()==1)
        if page.locator('#focusMode').count()!=1:
            page.close()
            continue
        check(label+' focus entry visible',page.locator('#focusMode').is_visible())
        page.locator('#focusMode').click()
        state=page.evaluate("""() => ({
          active:document.getElementById('focusOverlay').classList.contains('active'),
          focus:focusActive,
          rect:(()=>{let r=canvas.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}})(),
          shoot:(()=>{let r=$('shoot').getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom}})(),
          power:(()=>{let r=track.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}})(),
          scrollW:document.documentElement.scrollWidth,scrollH:document.documentElement.scrollHeight,
          powerValue:power
        })""")
        check(label+' focus activates rotated table',state['active'] and state['focus'],state)
        r=state['rect']
        diameter=2*12.2*r['height']/1100
        check(label+' focused balls at least 1.7x larger',diameter>=1.7*baseline_diameter,
              {'before':baseline_diameter,'after':diameter})
        check(label+' focused table entirely on screen',r['left']>=-1 and r['right']<=w+1 and r['top']>=-1 and r['bottom']<=h+1,r)
        check(label+' focused SHOOT visible',state['shoot']['right']<=w+1 and state['shoot']['left']>=-1 and state['shoot']['top']>=-1 and state['shoot']['bottom']<=h+1,state['shoot'])
        check(label+' no horizontal scroll',state['scrollW']<=w+1,state['scrollW'])
        cdp=page.context.new_cdp_session(page)
        cue=page.evaluate('({x:balls[0].x,y:balls[0].y})')
        tx=cue['x']+160
        ty=cue['y']-65
        # CSS 90-degree clockwise transform: screen x decreases with table y.
        sx=r['right']-ty*r['width']/570
        sy=r['top']+tx*r['height']/1100
        touch(cdp,'touchStart',sx,sy)
        touch(cdp,'touchEnd',sx,sy)
        got=page.evaluate('aim')
        expected=math.atan2(ty-cue['y'],tx-cue['x'])
        check(label+' rotated direct touch aims at finger target',
              angle_error(got,expected)<.015,{'got':got,'expected':expected})
        # A relative near-cue drag in table-X must respond to screen-Y.
        page.evaluate('aim=0')
        sx=r['right']-(cue['y']+3)*r['width']/570
        sy=r['top']+(cue['x']+4)*r['height']/1100
        touch(cdp,'touchStart',sx,sy)
        touch(cdp,'touchMove',sx,sy+35)
        got=page.evaluate('aim')
        check(label+' rotated fine-aim drag respects local table axes',
              angle_error(got,35*.13*math.pi/180)<.02,got)
        touch(cdp,'touchEnd',sx,sy+35)
        # A 65px downward local pull corresponds to moving screen-X left.
        page.evaluate('showPower(45)')
        p=state['power']
        start_x=p['right']-p['width']*.25
        start_y=p['top']+p['height']*.5
        touch(cdp,'touchStart',start_x,start_y)
        touch(cdp,'touchMove',start_x-24,start_y)
        touch(cdp,'touchEnd',start_x-24,start_y)
        selected=page.evaluate('power')
        check(label+' rotated power pull increases strength',selected>45+5,selected)
        check(label+' short pull does not accidentally fire',not page.evaluate('shooting'))
        page.locator('#shoot').click()
        check(label+' focused SHOOT launches calibrated impulse',
              page.evaluate('shooting && Math.hypot(balls[0].vx,balls[0].vy)>4'))
        page.locator('#exitFocus').click()
        check(label+' exit restores original table parent and normal mode',
              page.evaluate("!focusActive && !document.getElementById('focusOverlay').classList.contains('active') && canvas.closest('.wrap')!==null"))
        check(label+' exit restores portrait table size',
              abs(page.locator('#table').bounding_box()['width']-before['width'])<2)
        check(label+' no JS errors',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(x['passed'] for x in checks),'total':len(checks),
        'checks':checks,'limits':'Chromium emulation only. Physical Samsung Galaxy A37 and independent human acceptance are release blockers.'}
(ROOT/'POOL_WORLD_6.0_PORTRAIT_FOCUS_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
