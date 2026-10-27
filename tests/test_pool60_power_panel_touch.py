"""Real pointer regression: finger can start within the visible power panel,
not just the narrow 44px slider. This affects thumb use on small screens.
Automated Chromium touch emulation is not physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details):
 checks.append({'name':name,'passed':bool(ok),'details':details})
 if not ok:print('FAIL',name,details,flush=True)
def touch(cdp,kind,x,y):
 cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[] if kind=='touchEnd' else [{'x':x,'y':y,'id':1}]})
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,
  executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
  args=['--no-sandbox'])
 for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1000,has_touch=w<1000)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.evaluate('window.requestAnimationFrame=()=>0')
  page.set_content(HTML,wait_until='load')
  track=page.locator('#track').bounding_box()
  panel=page.locator('#powerControl').bounding_box()
  left=(panel['x']+track['x'])/2
  right=(track['x']+track['width']+panel['x']+panel['width'])/2
  y=track['y']+track['height']*.5
  cdp=page.context.new_cdp_session(page) if w<1000 else None
  for side,x in [('left',left),('right',right)]:
   for dy in (-20,20):
    page.evaluate('rack();showPower(45)')
    # The test deliberately starts OUTSIDE #track but INSIDE #powerControl.
    check(f'{w}x{h} {side} target is inside power panel outside track',
      panel['x']<x<panel['x']+panel['width'] and
      (x<track['x'] or x>track['x']+track['width']),
      {'x':x,'track':track,'panel':panel})
    if cdp:
     touch(cdp,'touchStart',x,y)
    else:
     page.mouse.move(x,y);page.mouse.down()
    start=page.evaluate('''()=>({powerDrag,powerPointer})''')
    check(f'{w}x{h} {side} {dy:+} captures thumb touch',
      start['powerDrag'] and start['powerPointer'] is not None,start)
    if cdp:touch(cdp,'touchMove',x,y+dy)
    else:page.mouse.move(x,y+dy,steps=2)
    moving=page.evaluate('''()=>({power,shooting,powerDrag})''')
    fraction=min(1,abs(dy)/max(65,track['height']*.65))
    expected=45+(55*fraction) if dy>0 else 45-(40*fraction)
    check(f'{w}x{h} {side} {dy:+} adjusts selected power',
      abs(moving['power']-expected)<.05 and not moving['shooting'] and moving['powerDrag'],
      {'expected':expected,'actual':moving})
    if cdp:touch(cdp,'touchEnd',x,y+dy)
    else:page.mouse.up()
    end=page.evaluate('''()=>({power,shooting,powerDrag,powerPointer})''')
    check(f'{w}x{h} {side} {dy:+} release retains power without firing',
      abs(end['power']-expected)<.05 and not end['shooting'] and
      not end['powerDrag'] and end['powerPointer'] is None,
      {'expected':expected,'actual':end})
  check(f'{w}x{h} no JavaScript exceptions',not errors,errors)
  page.close()
 browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POWER_PANEL_TOUCH_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Chromium touch/pointer simulation only; no physical Samsung or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
