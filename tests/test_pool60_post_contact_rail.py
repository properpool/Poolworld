"""Regression: ball-ball separation must not leave a ball embedded outside the cloth.

The ordinary physics pass constrains rail travel before resolving object contacts.
A late object contact can push the rail-side ball back through that rail.
These are deterministic Chromium fixtures, not physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    print(('PASS' if passed else 'FAIL'),name,detail,flush=True)

FIXTURE="""({kind})=>{
 rack();
 const loX=L+rad,hiX=R-rad,loY=T+rad,hiY=B-rad;
 const d=2*rad-.8;
 const setups={
   left:{x:loX+.3,y:285,ix:d,iy:0,vx:-4,vy:0},
   right:{x:hiX-.3,y:285,ix:-d,iy:0,vx:4,vy:0},
   top:{x:400,y:loY+.3,ix:0,iy:d,vx:0,vy:-4},
   bottom:{x:400,y:hiY-.3,ix:0,iy:-d,vx:0,vy:4}
 };
 const s=setups[kind];
 balls=[makeBall(0,900,450),makeBall(1,s.x,s.y),
        makeBall(2,s.x+s.ix,s.y+s.iy)];
 const outer=balls[1],inner=balls[2];
 inner.vx=s.vx;inner.vy=s.vy;
 shot=null;shooting=false;
 const before=inner.vx**2+inner.vy**2;
 physics(STEP);
 const energy=balls.slice(1).reduce((sum,b)=>sum+b.vx*b.vx+b.vy*b.vy+
                                        .4*(b.spin*b.spin+b.follow*b.follow),0);
 const valid=balls.slice(1).every(b=>b.x>=loX-1e-6&&b.x<=hiX+1e-6&&
                                         b.y>=loY-1e-6&&b.y<=hiY+1e-6);
 const finite=balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow,...b.rollQ]
                               .every(Number.isFinite));
 return {valid,finite,energy,before,potted:balls.some(b=>b.potted),
         outer:[outer.x,outer.y,outer.vx,outer.vy],
         inner:[inner.x,inner.y,inner.vx,inner.vy]};
}"""
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML.read_text(),wait_until='load')
        for kind in ('left','right','top','bottom'):
            result=page.evaluate(FIXTURE,{'kind':kind})
            tag=f'{width}x{height} {kind} rail-contact'
            check(tag+' remains within cloth',result['valid'],
                  {'outer':result['outer'],'inner':result['inner']})
            check(tag+' remains finite and unpotted',result['finite'] and not result['potted'],
                  {'finite':result['finite'],'potted':result['potted']})
            check(tag+' collision cannot create kinetic energy',
                  result['energy']<=result['before']+1e-5,
                  {'before':result['before'],'after':result['energy']})
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POST_CONTACT_RAIL_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Deterministic Chromium only; no physical Samsung or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
