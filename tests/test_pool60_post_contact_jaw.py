"""Rail-side object collisions must not push balls through rubber pocket jaws.

Two-ball impact fixtures are positioned adjacent to each of the twelve jaw
noses, with incoming shots directed into the jaw. Checks after one and 24
120Hz ticks cover residual jaw penetration, legal states and energy.
Browser simulation is not real Samsung or human playability acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',name,detail,flush=True)
FIXTURE=r"""(speed) => {
  const out=[];
  for(let i=0;i<jaws.length;i++){
    rack();balls=balls.slice(0,3);balls[0].potted=true;
    shooting=false;shot=null;events.length=0;
    const [jx,jy]=jaws[i],nx=jy===T?0:jy===B?0:jx===L?1:-1,
          ny=jy===T?1:jy===B?-1:0;
    const near=rad+jawRadius+.15;
    const a=balls[1],b=balls[2];
    a.x=jx+nx*near;a.y=jy+ny*near;a.vx=a.vy=a.spin=a.follow=0;
    b.x=a.x+nx*(2*rad+.1);b.y=a.y+ny*(2*rad+.1);
    b.vx=-nx*speed;b.vy=-ny*speed;b.spin=b.follow=0;
    const initial=speed*speed;
    const measure=()=>{
      const jawClear=balls.slice(1).every(q=>jaws.every(([x,y])=>
        Math.hypot(q.x-x,q.y-y)>=rad+jawRadius-.05));
      const legal=balls.slice(1).every(q=>q.x>=L+rad-.01&&q.x<=R-rad+.01&&
        q.y>=T+rad-.01&&q.y<=B-rad+.01);
      const finite=balls.slice(1).every(q=>[q.x,q.y,q.vx,q.vy,q.spin,q.follow].every(Number.isFinite));
      const energy=balls.slice(1).reduce((v,q)=>v+q.vx*q.vx+q.vy*q.vy+
        .4*(q.spin*q.spin+q.follow*q.follow),0);
      return {jawClear,legal,finite,energy,notPotted:balls.slice(1).every(q=>!q.potted),
        jawDistances:balls.slice(1).map(q=>Math.min(...jaws.map(([x,y])=>Math.hypot(q.x-x,q.y-y))))};
    };
    physics(STEP);const first=measure();
    for(let tick=1;tick<24;tick++)physics(STEP);
    const later=measure();
    out.push({jaw:i,speed,initial,first,later});
  }
  return out;
}"""
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
      executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
      args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},
          is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML.read_text(),wait_until='load')
        for speed in (7,9):
            for item in page.evaluate(FIXTURE,speed):
                name=f'{w}x{h} jaw{item["jaw"]} speed{speed}'
                first,later=item['first'],item['later']
                check(name+' immediate jaw clearance',first['jawClear'],item)
                check(name+' 24-tick jaw clearance',later['jawClear'],item)
                check(name+' cloth bounds',first['legal'] and later['legal'],item)
                check(name+' no false pocket',first['notPotted'] and later['notPotted'],item)
                check(name+' finite dissipative motion',first['finite'] and later['finite'] and
                  first['energy']<=item['initial']+1e-5 and later['energy']<=item['initial']+1e-5,item)
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POST_CONTACT_JAW_RESULTS.json').write_text(
  json.dumps({'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Chromium physics only, not physical Samsung/human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
