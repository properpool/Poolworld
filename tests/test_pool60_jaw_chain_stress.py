"""Seeded six-ball cue/object chains against all twelve pocket-jaw noses.

Covers staggered jaw-side multi-contact with English and follow/draw on
phone, tablet and laptop viewports. The test is deterministic; it does not
establish real-device playability or experimentally calibrated billiards.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)
FIXTURE=r"""([speed,english,draw])=>{
 const cases=[];
 for(let jaw=0;jaw<jaws.length;jaw++){
  rack();balls=balls.slice(0,6);breakShot=false;
  shooting=false;shot=null;events.length=0;
  const [jx,jy]=jaws[jaw];
  const nx=jy===T?0:jy===B?0:jx===L?1:-1;
  const ny=jy===T?1:jy===B?-1:0;
  const tx=-ny,ty=nx,near=rad+jawRadius+.15;
  // Five objects between the jaw and the approaching cue ball.
  // Small stagger avoids an artificially exact one-dimensional rack.
  for(let i=1;i<=5;i++){
   const b=balls[i],d=near+(i-1)*(2*rad+.15),side=(i%2?0:2.4);
   Object.assign(b,{x:jx+nx*d+tx*side,y:jy+ny*d+ty*side,
     vx:0,vy:0,spin:0,follow:0,potted:false});
  }
  const cue=balls[0],distance=near+5*(2*rad+.15);
  Object.assign(cue,{x:jx+nx*distance+tx*1.2,
    y:jy+ny*distance+ty*1.2,vx:-nx*speed,vy:-ny*speed,
    spin:english,follow:draw,potted:false});
  shot={player:1,breakShot:false,firstHit:null,
    railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
  const energy=()=>balls.reduce((sum,b)=>sum+b.vx*b.vx+b.vy*b.vy+
    .4*(b.spin*b.spin+b.follow*b.follow),0);
  const initial=energy();
  const measure=()=>{
   let jawPen=0,pairPen=0,legal=true,finite=true,notPotted=true;
   for(let i=0;i<balls.length;i++){
    const b=balls[i];notPotted=notPotted&&!b.potted;
    finite=finite&&[b.x,b.y,b.vx,b.vy,b.spin,b.follow].every(Number.isFinite);
    legal=legal&&b.x>=L+rad-.02&&b.x<=R-rad+.02&&
      b.y>=T+rad-.02&&b.y<=B-rad+.02;
    for(const [x,y] of jaws)jawPen=Math.max(jawPen,rad+jawRadius-Math.hypot(b.x-x,b.y-y));
    for(let j=i+1;j<balls.length;j++)pairPen=Math.max(pairPen,
      2*rad-Math.hypot(b.x-balls[j].x,b.y-balls[j].y));
   }
   return {jawPen,pairPen,legal,finite,notPotted,energy:energy()};
  };
  physics(STEP);const first=measure();
  for(let k=1;k<48;k++)physics(STEP);
  const later=measure();
  cases.push({jaw,speed,english,draw,initial,first,later});
 }
 return cases;
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
            for english,draw in [(-1.1,-1.5),(0,0),(1.1,1.5)]:
                for item in page.evaluate(FIXTURE,[speed,english,draw]):
                    key=f'{w}x{h} jaw{item["jaw"]} speed{speed} eng{english} draw{draw}'
                    a,b=item['first'],item['later']
                    check(key+' jaw clearance',a['jawPen']<=.05 and b['jawPen']<=.05,item)
                    check(key+' pair separation',a['pairPen']<=.05 and b['pairPen']<=.05,item)
                    check(key+' legal finite cloth',a['legal'] and b['legal'] and a['finite'] and b['finite'],item)
                    check(key+' no false pot',a['notPotted'] and b['notPotted'],item)
                    check(key+' bounded energy',a['energy']<=item['initial']+1e-4 and
                        b['energy']<=item['initial']+1e-4,item)
        check(f'{w}x{h} no JS exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_JAW_CHAIN_STRESS_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Deterministic Chromium fixtures only; no real Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
