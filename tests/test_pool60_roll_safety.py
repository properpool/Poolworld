"""Staging regression: cue-ball roll marker and real mobile touch-pull safety."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import math
P=Path(__file__).resolve().parents[1]/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def test(name,ok):
 checks.append((name,bool(ok)));print(('PASS' if ok else 'FAIL'),name,flush=True)
def touch(cdp,kind,x,y):
 cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[] if kind=='touchEnd' else [{'x':x,'y':y,'id':1}]})
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(P.read_text(),wait_until='load')
  test(f'{w} new cue orientation identity',page.evaluate('JSON.stringify(balls[0].rollQ)===JSON.stringify([1,0,0,0])'))
  page.evaluate('''() => {balls[0].vx=3;balls[0].vy=0;for(let i=0;i<35;i++)physics(STEP)}''')
  q=page.evaluate('balls[0].rollQ')
  test(f'{w} rolling cue orientation changes and stays unit length',q is not None and abs(q[2])>.01 and abs(math.hypot(*q)-1)<1e-10)
  page.evaluate('rack()')
  test(f'{w} rerack resets roll',page.evaluate('JSON.stringify(balls[0].rollQ)===JSON.stringify([1,0,0,0])'))
  tr=page.locator('#track').bounding_box();x=tr['x']+tr['width']/2;y=tr['y']+tr['height']*.25
  cdp=page.context.new_cdp_session(page)
  touch(cdp,'touchStart',x,y);touch(cdp,'touchMove',x,y+13);touch(cdp,'touchEnd',x,y+13)
  test(f'{w} short touch wobble cannot shoot',page.evaluate('!shooting && !powerDrag && shot===null'))
  y=tr['y']+tr['height']*.14;end=tr['y']+tr['height']*.89
  touch(cdp,'touchStart',x,y)
  for i in range(1,8):touch(cdp,'touchMove',x,y+(end-y)*i/7)
  touch(cdp,'touchEnd',x,end)
  test(f'{w} deliberate touch pull fires with real power',page.evaluate('shooting && Math.hypot(balls[0].vx,balls[0].vy)>4 && power===45'))
  page.evaluate('''() => {let n=0;while(!settled()&&n++<4500)physics(STEP);if(settled())resolveShot()}''')
  test(f'{w} touch shot completes',page.evaluate('!shooting'))
  test(f'{w} no browser errors',not errors)
  page.close()
 browser.close()
passed=sum(ok for _,ok in checks)
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):raise SystemExit(1)
