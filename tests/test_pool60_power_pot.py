"""Regression for weak shots and pocket failures reported during physical phone play."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(P.read_text(),wait_until='load')
  check(f'{w} power percentage shown',page.locator('#powerValue').inner_text()=='45%',page.locator('#powerValue').inner_text())
  page.locator('#shoot').click()
  res=page.evaluate("""() => {let n=0;while(!settled()&&n++<3000)physics(STEP);return {firstHit:shot.firstHit,steps:n,settled:settled()}}""")
  check(f'{w} default 45% break reaches rack',res['firstHit'] is not None and res['settled'],res)
  page.evaluate('rack()')
  page.evaluate('showPower(100)')
  check(f'{w} max power percentage shown',page.locator('#powerValue').inner_text()=='100%',page.locator('#powerValue').inner_text())
  page.evaluate('rack()')
  tr=page.locator('#track').bounding_box()
  x=tr['x']+tr['width']/2
  page.mouse.move(x,tr['y']+tr['height']*.12)
  page.mouse.down()
  page.mouse.move(x,tr['y']+tr['height']*.95,steps=6)
  page.mouse.up()
  result=page.evaluate('() => ({shooting,power,speed:shotSpeed(45,true)})')
  check(f'{w} downward power pull fires',result['shooting'] and result['speed']>4.5,result)
  speeds=page.evaluate('() => [shotSpeed(25,false),shotSpeed(45,false),shotSpeed(85,false)]')
  check(f'{w} distinct 25/45/85 shot velocities',speeds[0]<speeds[1]<speeds[2] and speeds[2]>speeds[0]*2,speeds)
  fixtures=[('top-left',210,170,79,78),('top-middle',550,200,550,70),('top-right',920,170,1021,78),('bottom-left',210,400,79,492),('bottom-middle',550,365,550,500),('bottom-right',920,400,1021,492)]
  for name,ox,oy,hx,hy in fixtures:
   res=page.evaluate("""([ox,oy,hx,hy]) => {rack();balls=balls.slice(0,2);const obj=balls[1],cue=balls[0];obj.x=ox;obj.y=oy;const a=Math.atan2(hy-oy,hx-ox);cue.x=ox-Math.cos(a)*90;cue.y=oy-Math.sin(a)*90;aim=a;showPower(55);shoot();let n=0;while(!settled()&&n++<4000)physics(STEP);return {potted:obj.potted,firstHit:shot.firstHit,steps:n,settled:settled()}}""",[ox,oy,hx,hy])
   check(f'{w} {name} aligned pot',res['potted'] and res['settled'] and res['firstHit']==1,res)
  check(f'{w} no browser exceptions',not errors,errors)
  page.close()
 browser.close()
summary={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'limits':'Chromium mobile emulation, not physical Samsung or human acceptance.'}
(P.parent/'POOL_WORLD_6.0_POWER_POT_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)
