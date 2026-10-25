"""All-ball rolling and stripe projection acceptance on mobile Chromium."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from hashlib import sha256
import math,json,sys
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 for w,h in [(844,390),(390,844)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True,device_scale_factor=2)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(SOURCE.read_text(),wait_until='load')
  start=page.evaluate('() => balls.map(b=>b.rollQ)')
  check(f'{w} all 16 balls have orientation',len(start)==16 and all(q==[1,0,0,0] for q in start))
  page.evaluate('''() => {const b=balls.find(b=>b.id===9);for(const other of balls)if(other!==b)other.potted=true;b.x=500;b.y=270;b.vx=0;b.vy=0;b.rollQ=[1,0,0,0];render()}''')
  before=page.locator('#table').screenshot()
  state=page.evaluate('''() => {const b=balls.find(b=>b.id===9);rotateRoll(b,19,27);render();return {q:b.rollQ,axis:rollMarker(b.rollQ,[0,1,0])}}''')
  after=page.locator('#table').screenshot()
  check(f'{w} stripe visibly rotates',sha256(before).digest()!=sha256(after).digest())
  check(f'{w} projected stripe axis rotates',math.dist(state['axis'],[0,1,0])>.1,state['axis'])
  check(f'{w} roll quaternion stays unit length',abs(math.hypot(*state['q'])-1)<1e-10,state['q'])
  page.evaluate('''() => {rack();for(const b of balls)if(b.id!==8)b.potted=true;const b=balls.find(b=>b.id===8);b.x=480;b.y=260;b.vx=2.1;b.vy=1.2}''')
  motion=page.evaluate('''() => {for(let i=0;i<20;i++)physics(STEP);return balls.find(b=>b.id===8).rollQ}''')
  check(f'{w} 8 ball rolls during physics',math.dist(motion,[1,0,0,0])>.05)
  page.evaluate('rack()')
  page.locator('#shoot').click()
  shot=page.evaluate('''() => {let n=0;while(!settled()&&n++<3500)physics(STEP);return {hit:shot?.firstHit,rolled:balls.filter(b=>b.id!==0&&Math.abs(b.rollQ[0]-1)>.0001).length,finite:balls.every(b=>b.rollQ.every(Number.isFinite))}}''')
  check(f'{w} default break contacts rack',shot['hit'] is not None,shot)
  check(f'{w} multiple object balls roll',shot['rolled']>=3 and shot['finite'],shot)
  check(f'{w} no JS errors',not errors,errors)
  page.close()
 browser.close()
summary={'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'limits':'Automated Chromium mobile emulation, not physical Samsung acceptance.'}
(ROOT/'POOL_WORLD_6.0_OBJECT_ROLL_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)
