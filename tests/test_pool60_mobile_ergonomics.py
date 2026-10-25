"""End-user facing Samsung-scale touch ergonomics and playable shot acceptance."""
from playwright.sync_api import sync_playwright
from pathlib import Path
import json,math,hashlib,re,sys
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,passed,details=None):
 checks.append({'name':name,'passed':bool(passed),'details':details})
 print(('PASS' if passed else 'FAIL'),name,details,flush=True)
def touch(s,kind,x,y):
 s.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[] if kind=='touchEnd' else [{'x':x,'y':y,'id':1}]})
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(844,390),(915,412),(812,375),(740,360),(667,375),(568,320),(390,844),(360,740)]:
  page=b.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True,device_scale_factor=2)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(SOURCE.read_text(),wait_until='load')
  r=page.evaluate('''() => {const rect=x=>{const a=document.querySelector(x).getBoundingClientRect();return {x:a.x,y:a.y,w:a.width,h:a.height,bottom:a.bottom}};return {shoot:rect('#shoot'),track:rect('#track'),table:rect('.board'),details:rect('details'),scrollH:document.documentElement.scrollHeight,scrollW:document.documentElement.scrollWidth}}''')
  check(f'{w}x{h} shoot 44px touch height',r['shoot']['h']>=44,r['shoot'])
  check(f'{w}x{h} slider 44px touch width',r['track']['w']>=44,r['track'])
  check(f'{w}x{h} no horizontal overflow',r['scrollW']<=w,r['scrollW'])
  check(f'{w}x{h} shoot visible in viewport',r['shoot']['bottom']<=h and r['shoot']['y']>=0,r['shoot'])
  check(f'{w}x{h} no JS exceptions',not errors,errors)
  if w in (844,390,568):
   cdp=page.context.new_cdp_session(page)
   box=page.locator('#track').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']*.15
   touch(cdp,'touchStart',x,y);touch(cdp,'touchMove',x,y+13);touch(cdp,'touchEnd',x,y+13)
   check(f'{w}x{h} 13px finger wobble does not fire',not page.evaluate('shooting'))
   box=page.locator('#track').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']*.14;end=box['y']+box['height']*.9
   touch(cdp,'touchStart',x,y)
   for i in range(1,9):touch(cdp,'touchMove',x,y+(end-y)*i/8)
   touch(cdp,'touchEnd',x,end)
   state=page.evaluate('''() => ({shooting,power,speed:Math.hypot(balls[0].vx,balls[0].vy),hit:shot?.firstHit})''')
   check(f'{w}x{h} real touch pull fires strong break',state['shooting'] and state['speed']>4,state)
   state2=page.evaluate('''() => {let n=0;while(!settled()&&n++<4000)physics(STEP);return {hit:shot?.firstHit,settled:settled(),steps:n}}''')
   check(f'{w}x{h} real touch break contacts rack',state2['hit'] is not None and state2['settled'],state2)
  page.close()
 b.close()
html=SOURCE.read_text()
# Approved sound payload literals remain untouched from the source baseline.
AUDIO_HASHES={'ball':'6e0440053e5859b48fa1','cue':'7e2b39137a6de6afd751','rail':'e405df7c5c3c3937a6e2','pocket':'6931e106287f67f9b771'}
for sound,digest in AUDIO_HASHES.items():
 c=re.search(r'\b'+sound+r':"(data:audio/[^" ]+)"',html)
 got=hashlib.sha256(c.group(1).encode()).hexdigest()[:20] if c else None
 check(f'approved {sound} sound byte-identical',got==digest,got)
summary={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'limits':'Automated Chromium touch emulation; physical Samsung and independent human acceptance not performed.'}
(ROOT/'POOL_WORLD_6.0_MOBILE_ERGONOMICS_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)