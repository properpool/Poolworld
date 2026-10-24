"""Chromium mobile pointer regression: precision aiming and safe pullback."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_5.7_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for viewport in [{'width':390,'height':844},{'width':844,'height':390}]:
  page=browser.new_page(viewport=viewport,is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(P.read_text(),wait_until='load')
  w=viewport['width']
  check(f'{w} precision toggle initially off',page.evaluate("!precisionAim && document.querySelector('#precision').getAttribute('aria-pressed')==='false'"))
  page.locator('#precision').click()
  check(f'{w} precision toggle turns on',page.evaluate("precisionAim && document.querySelector('#precision').getAttribute('aria-pressed')==='true'"))
  b=page.locator('#table').bounding_box();x=b['x']+b['width']*.3;y=b['y']+b['height']*.35
  original=page.evaluate('aim')
  page.mouse.move(x,y);page.mouse.down()
  start=page.evaluate('aim')
  check(f'{w} precision pointer down never snaps',abs(start-original)<1e-9,{'start':start,'original':original})
  page.mouse.move(x+40,y,steps=8)
  delta=page.evaluate('aim')-original
  check(f'{w} precision drag is 0.13 degrees per CSS pixel',abs(delta-40*math.pi/180*.13)<1e-6,delta)
  page.mouse.up()
  check(f'{w} pointer capture cleared',page.evaluate('!dragAim && aimPointer===null'))
  page.mouse.move(x+65,y)
  check(f'{w} moving without drag does not change aim',abs(page.evaluate('aim')-original-delta)<1e-9)
  page.locator('#precision').click()
  check(f'{w} direct mode restored',page.evaluate('!precisionAim'))
  p0=page.evaluate('aim');page.touchscreen.tap(b['x']+b['width']*.82,b['y']+b['height']*.66)
  check(f'{w} direct table tap aims',abs(page.evaluate('aim')-p0)>.05)
  track=page.locator('#track').bounding_box();tx=track['x']+track['width']*.5
  page.touchscreen.tap(tx,track['y']+track['height']*.3)
  check(f'{w} power-track tap does not accidentally shoot',page.evaluate('!shooting && shot===null && powerDrag===false'))
  check(f'{w} tap selects power',page.evaluate('power>=5 && power<=100'))
  page.mouse.move(tx,track['y']+track['height']*.78);page.mouse.down()
  page.mouse.move(tx,track['y']+track['height']*.3,steps=6);page.mouse.up()
  check(f'{w} upward pull does not fire',page.evaluate('!shooting'))
  previous=page.evaluate('power')
  page.mouse.move(tx,track['y']+track['height']*.25);page.mouse.down()
  page.mouse.move(tx,track['y']+track['height']*.85,steps=6)
  page.locator('#track').dispatch_event('pointercancel',{'pointerId':1,'clientY':track['y']+track['height']*.85})
  page.mouse.up()
  check(f'{w} cancelled power drag does not fire',page.evaluate('!shooting && !powerDrag'))
  check(f'{w} cancelled power drag restores power',abs(page.evaluate('power')-previous)<1e-6)
  page.mouse.move(tx,track['y']+track['height']*.2);page.mouse.down()
  page.mouse.move(tx,track['y']+track['height']*.85,steps=10);page.mouse.up()
  check(f'{w} deliberate downward pull fires shot',page.evaluate('shooting && shot!==null'))
  check(f'{w} power resets after firing',page.evaluate('power===45'))
  finished=page.evaluate('() => {let n=0;while(!settled()&&n++<5000)physics(STEP);if(settled())resolveShot();return {settled:!shooting,n}}')
  check(f'{w} touch-triggered physical shot completes',finished['settled'] and finished['n']<5000,finished)
  check(f'{w} no JS errors',not errors,errors)
  if w==844:
   check('landscape table, power and shoot visible without scrolling',page.evaluate("() => {const ids=['table','track','shoot'];return ids.every(id=>{const b=document.getElementById(id).getBoundingClientRect();return b.top>=0&&b.bottom<=innerHeight}) && document.documentElement.scrollHeight<=innerHeight}"))
  page.close()
 browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'limits':'Chromium emulation only; no real Samsung hardware or independent human testing.'}
(P.parent/'POOL_WORLD_5.7_TOUCH_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'])
if result['passed']!=result['total']:raise SystemExit(1)
