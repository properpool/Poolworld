"""Detect wasteful 60Hz idle canvas redraws while retaining instant touch/keyboard response.
Counts actual full 1100x570 canvas renders and samples browser render CPU time.
Headless Chromium measurements are NOT physical Samsung frame-time acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 if not ok: print('FAIL',name,detail,flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1000,has_touch=w<1000)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.evaluate('window.requestAnimationFrame=()=>0')
  page.set_content(HTML,wait_until='load')
  page.evaluate("""() => {
    window.renderStats={calls:0,cpuMs:0};
    const original=render;
    render=function(){const t=performance.now();original();renderStats.calls++;renderStats.cpuMs+=performance.now()-t};
    last=0;accumulator=0;
  }""")
  result=page.evaluate("""() => {
    for(let i=1;i<=120;i++)frame(1000+i*1000/60);
    return {...renderStats,pixel:[...ctx.getImageData(500,285,1,1).data]};
  }""")
  check(f'{w}x{h} stationary rack draws at most twice in 120 frames',result['calls']<=2,result)
  check(f'{w}x{h} first frame paints visible table',result['pixel'][3]==255 and sum(result['pixel'][:3])>0,result)
  page.evaluate('renderStats.calls=0')
  # Real browser pointer event, not direct mutation of aim.
  box=page.locator('#table').bounding_box()
  page.mouse.click(box['x']+box['width']*.58,box['y']+box['height']*.28)
  aimed=page.evaluate("""() => {const a=aim;frame(last+1000/60);return {angle:a,draws:renderStats.calls}}""")
  check(f'{w}x{h} pointer aiming repaints next frame',aimed['draws']>=1 and abs(aimed['angle'])>.01,aimed)
  page.evaluate('renderStats.calls=0')
  page.evaluate('for(let i=0;i<30;i++)frame(last+1000/60)')
  check(f'{w}x{h} stable aim does not redraw needlessly',page.evaluate('renderStats.calls')<=1,page.evaluate('renderStats.calls'))
  page.evaluate('renderStats.calls=0')
  page.keyboard.press('ArrowRight')
  keys=page.evaluate('''() => {frame(last+1000/60);return renderStats.calls}''')
  check(f'{w}x{h} keyboard aim repaints next frame',keys>=1,keys)
  page.evaluate('renderStats.calls=0')
  page.locator('#guide').click()
  guide=page.evaluate('''() => {frame(last+1000/60);return renderStats.calls}''')
  check(f'{w}x{h} aiming guide toggle repaints next frame',guide>=1,guide)
  page.evaluate('renderStats.calls=0')
  page.locator('#reset').click()
  reset=page.evaluate('''() => {frame(last+1000/60);return renderStats.calls}''')
  check(f'{w}x{h} new rack repaints next frame',reset>=1,reset)
  page.evaluate('renderStats.calls=0')
  moving=page.evaluate('''() => {showPower(100);shoot();for(let i=0;i<8;i++)frame(last+1000/60);return {calls:renderStats.calls,shooting}}''')
  check(f'{w}x{h} moving rack renders every frame',moving['calls']>=8,moving)
  check(f'{w}x{h} no JS errors',not errors,errors)
  page.close()
 browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_RENDER_INVALIDATION_RESULTS.json').write_text(json.dumps({'passed':passed,'total':len(checks),'checks':checks,'limits':'Chromium rendering counts/CPU measurements; not physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
