"""Chromium real-touch pocket tolerance at all six pockets (±1 degree).
Isolated object-ball fixtures, not a human-play or physical Samsung acceptance test.
"""
from pathlib import Path
from math import atan2,cos,sin,pi
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
P=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
fixtures=[('top-left',210,170,79,78),('top-middle',550,200,550,70),('top-right',920,170,1021,78),('bottom-left',210,400,79,492),('bottom-middle',550,365,550,500),('bottom-right',920,400,1021,492)]
checks=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(P.read_text(),wait_until='load')
  for name,ox,oy,hx,hy in fixtures:
   a=atan2(hy-oy,hx-ox)
   for error in [-1,0,1]:
    page.evaluate("""([ox,oy,a])=>{rack();balls=balls.slice(0,2);balls[1].x=ox;balls[1].y=oy;balls[0].x=ox-Math.cos(a)*90;balls[0].y=oy-Math.sin(a)*90;showPower(55)}""",[ox,oy,a])
    cue=page.evaluate('() => ({x:balls[0].x,y:balls[0].y})')
    target_angle=a+error*pi/180
    target_x=cue['x']+cos(target_angle)*90;target_y=cue['y']+sin(target_angle)*90
    box=page.locator('#table').bounding_box()
    page.touchscreen.tap(box['x']+target_x/1100*box['width'],box['y']+target_y/570*box['height'])
    page.locator('#shoot').click()
    r=page.evaluate("""() => {let n=0;while(!settled()&&n++<4000)physics(STEP);return {potted:balls[1].potted,firstHit:shot.firstHit,settled:settled(),steps:n}}""")
    passed=r['potted'] and r['firstHit']==1 and r['settled']
    checks.append({'viewport':f'{w}x{h}','pocket':name,'aim_error_degrees':error,'passed':passed,'result':r})
    print('PASS' if passed else 'FAIL',w,name,error,r,flush=True)
  checks.append({'viewport':f'{w}x{h}','check':'no JavaScript errors','passed':not errors,'errors':errors})
  page.close()
 browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'limits':'Isolated balls and Chromium touchscreen taps; not physical Samsung or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_CORNER_JAW_TOUCH_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'])
if result['passed']!=result['total']:sys.exit(1)
