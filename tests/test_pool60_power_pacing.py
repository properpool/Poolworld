"""Browser-input shot strength, short-pull safety and low-FPS simulation pacing.

Measures actual cue-ball travel and actual pointer-triggered break velocity.
Emulated Chromium, not physical Samsung or human acceptance.
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
def touch(cdp,kind,x,y):
 cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[] if kind=='touchEnd' else [{'x':x,'y':y,'id':1}]})
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
  mobile=w<1000
  def page_new():
   pg=browser.new_page(viewport={'width':w,'height':h},is_mobile=mobile,has_touch=mobile)
   pg.evaluate('window.requestAnimationFrame=()=>0')
   pg.set_content(HTML,wait_until='load')
   return pg
  page=page_new()
  for fps in (60,30,20,15):
   result=page.evaluate('''fps=>{
    const oldPhysics=physics,oldRender=render,oldSettled=settled;
    let ticks=0;
    physics=()=>{ticks++};render=()=>{};settled=()=>false;
    shooting=true;last=1000;accumulator=0;
    for(let i=1;i<=20;i++)frame(1000+i*1000/fps);
    const result={ticks,expected:Math.floor(20*120/fps),fps};
    physics=oldPhysics;render=oldRender;settled=oldSettled;shooting=false;
    return result;
   }''',fps)
   check(f'{w}x{h} {fps}fps maintains real-time simulation',abs(result['ticks']-result['expected'])<=2,result)
  page.close()
  page=page_new()
  page.locator('details summary').click()
  distances=[]
  for level in (10,25,50,75,100):
   page.evaluate('''()=>{rack();balls=balls.slice(0,1);breakShot=false;aim=0;spin=0;follow=0;}''')
   page.locator('#strength').fill(str(level))
   selected=page.evaluate('power')
   page.locator('#shoot').click()
   movement=page.evaluate('''()=>{const x=balls[0].x;const v=Math.hypot(balls[0].vx,balls[0].vy);
     for(let i=0;i<24;i++)physics(STEP);
     return {travel:balls[0].x-x,initialSpeed:v,selected:power};}''')
   distances.append(movement['travel'])
   check(f'{w}x{h} {level}% UI selection yields ball travel',selected==level and movement['travel']>level*.65,movement)
  check(f'{w}x{h} increasing power increases actual travel',all(a<b for a,b in zip(distances,distances[1:])),distances)
  page.close()
  if mobile:
   page=page_new()
   cdp=page.context.new_cdp_session(page)
   box=page.locator('#track').bounding_box();x=box['x']+box['width']*.5;y=box['y']+box['height']*.12
   touch(cdp,'touchStart',x,y)
   touch(cdp,'touchMove',x,y+32)
   touch(cdp,'touchEnd',x,y+32)
   state=page.evaluate('''()=>({shooting,power,powerDrag})''')
   check(f'{w}x{h} 32px partial finger pull does not fire weak shot',not state['shooting'] and not state['powerDrag'],state)
   page.evaluate('rack()')
   box=page.locator('#track').bounding_box();x=box['x']+box['width']*.5;y=box['y']+box['height']*.12
   touch(cdp,'touchStart',x,y)
   for i in range(1,9):touch(cdp,'touchMove',x,y+box['height']*.63*i/8)
   touch(cdp,'touchEnd',x,y+box['height']*.63)
   state=page.evaluate('''()=>({shooting,speed:Math.hypot(balls[0].vx,balls[0].vy),power})''')
   check(f'{w}x{h} deliberate 63%-height finger pull gives powerful break',state['shooting'] and state['speed']>=9.0,state)
   page.close()
 browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POWER_PACING_RESULTS.json').write_text(json.dumps({'passed':passed,'total':len(checks),'checks':checks,'limits':'Chromium browser input and simulated low FPS, not physical Samsung or human testing.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
