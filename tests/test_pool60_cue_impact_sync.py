"""Cue/ball impact synchronisation in the live shot renderer.

The shot impulse is applied immediately in shoot(). The visual cue must therefore
be at its contact point on the FIRST shot frame, not spend ~104ms travelling
toward a ball that has already moved away. Verify actual rendered cue geometry
and authoritative cue-ball movement across portrait, landscape and tablet.
Chromium only: this is not physical Samsung or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 if not ok:print('FAIL',name,detail,flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,
  executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
  args=['--no-sandbox'])
 for w,h in ((360,800),(390,844),(844,390),(768,1024)):
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  page.evaluate('window.requestAnimationFrame=()=>0')
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(HTML,wait_until='load')
  for level in (15,45,90):
   data=page.evaluate("""level=>{
    rack();balls=[makeBall(0,320,285)];breakShot=false;aim=0;
    gameOver=false;ballInHand=false;showPower(level);
    const expected=shotSpeed(level,false);
    const original=drawCue,frames=[];
    drawCue=function(x,y,a,p,phase){
     frames.push({x,y,level:p,phase,tip:cueTipOffset(p,phase)});
     return original.apply(this,arguments);
    };
    const fired=shoot(),velocity=Math.hypot(balls[0].vx,balls[0].vy);
    render();const first=frames.at(-1);
    last=1000;frame(1016.6666667);
    const moving=frames.at(-1),x1=balls[0].x;
    frame(1033.3333333);
    const later=frames.at(-1),x2=balls[0].x;
    drawCue=original;
    return {fired,expected,velocity,first,moving,later,x1,x2,
      power,shooting,remaining:cueStrike&&cueStrike.elapsed};
   }""",level)
   tag=f'{w}x{h} {level}%'
   check(tag+' fires with unchanged calibrated cue impulse',
    data['fired'] and abs(data['velocity']-data['expected'])<1e-8,data)
   first=data['first'];moving=data['moving'];later=data['later']
   check(tag+' first visual frame shows cue at impact, not far behind',
    first is not None and first['phase']>=.64 and
    -29<first['tip']< -12.2,first)
   check(tag+' cue retreats as the ball moves away',
    moving is not None and later is not None and
    moving['tip']<=first['tip']+1e-8 and
    later['tip']<moving['tip']-0.01 and
    data['x1']>320 and data['x2']>data['x1'],
    {'first':first,'moving':moving,'later':later,'x1':data['x1'],'x2':data['x2']})
   check(tag+' impact drawing preserves selected power and shot state',
    data['shooting'] and data['power']==level and
    first is not None and first['level']==level and
    math.isfinite(data['x2']),data)
  check(f'{w}x{h} no JavaScript errors',not errors,errors)
  page.close()
 browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
 'checks':checks,'limits':'Chromium cue/ball visual impact timing; physical Samsung and human acceptance remain release-blocking.'}
(ROOT/'POOL_WORLD_6.0_CUE_IMPACT_SYNC_RESULTS.json').write_text(json.dumps(result,indent=2))
print('CUE IMPACT SYNC',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
