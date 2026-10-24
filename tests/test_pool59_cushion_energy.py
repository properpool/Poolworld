"""v5.9 measured cushion/jaw contact dissipation in actual Chromium engine."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_5.9_STAGING_MATCH.html'
checks=[]
def check(name,passed,details=None):
 checks.append({'name':name,'passed':bool(passed),'details':details})
 print(('PASS' if passed else 'FAIL'),name,str(details)[:300],flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(P.read_text(),wait_until='load')
 measurements=page.evaluate('''() => {
  const out={};const energy=b=>b.vx*b.vx+b.vy*b.vy+.4*b.spin*b.spin;
  let maxRatio=0,worst=null,nonfinite=0,contacts=0,reversals=0;
  for(let i=0;i<3600;i++){
   const angle=i*.0323, nx=Math.cos(angle),ny=Math.sin(angle),tx=-ny,ty=nx;
   const vn=-.2+(i%47)*(-.12), vt=((i%59)-29)*.16, spin=((i%67)-33)*.17;
   const b={vx:vn*nx+vt*tx,vy:vn*ny+vt*ty,spin};
   const before=energy(b), jaw=i%2===0, e=jaw?.76:.78,mu=.04;
   const changed=reflectCushion(b,nx,ny,e,mu);
   const after=energy(b),ratio=after/before;
   if(ratio>maxRatio){maxRatio=ratio;worst={i,ratio,before,after,vn,vt,spin,jaw}}
   if(![b.vx,b.vy,b.spin].every(Number.isFinite))nonfinite++;
   if(changed)contacts++;
   if(b.vx*nx+b.vy*ny>0)reversals++;
  }
  out.stress={cases:3600,contacts,reversals,nonfinite,maxRatio,worst};
  const sample=(spin)=>{const b={vx:3,vy:0,spin};const before=energy(b);reflectCushion(b,-1,0,.78,.04);return {...b,before,after:energy(b)}};
  out.english={negative:sample(-1.5),neutral:sample(0),positive:sample(1.5)};
  // The actual physics() path, not just the impulse helper.
  let maxPhysicalRatio=0,physicalContacts=0,physicalNonfinite=0;
  for(let i=0;i<600;i++){
   rack();for(const b of balls)if(b.id!==1)b.potted=true;
   const b=balls[1];b.x=300+(i%3)*200;b.y=T+rad+.02;b.vx=((i%29)-14)*.12;b.vy=-.25-(i%37)*.13;b.spin=((i%43)-21)*.15;b.follow=0;
   const before=energy(b);shot={player:1,firstHit:1,pocketed:[],scratch:false,railAfterContact:false};
   physics(STEP);const after=energy(b);
   if(shot.railAfterContact)physicalContacts++;
   if(before>0)maxPhysicalRatio=Math.max(maxPhysicalRatio,after/before);
   if(![b.x,b.y,b.vx,b.vy,b.spin].every(Number.isFinite))physicalNonfinite++;
  }
  out.physical={cases:600,contacts:physicalContacts,maxRatio:maxPhysicalRatio,nonfinite:physicalNonfinite};
  // Exact coincidence with a jaw must be separated without NaN.
  rack();for(const b of balls)if(b.id!==1)b.potted=true;
  const b=balls[1];b.x=jaws[0][0];b.y=jaws[0][1];b.vx=b.vy=0;b.spin=0;collideJaw(b);
  out.coincidentJaw={distance:Math.hypot(b.x-jaws[0][0],b.y-jaws[0][1]),finite:[b.x,b.y,b.vx,b.vy].every(Number.isFinite)};
  return out;
 }''')
 stress=measurements['stress'];en=measurements['english'];phys=measurements['physical']
 check('3600 varied wall/jaw impulses are finite',stress['nonfinite']==0,stress)
 check('3600 impacts reverse normal velocity inward',stress['contacts']==3600 and stress['reversals']==3600,stress)
 check('3600 wall/jaw impacts do not increase tracked energy',stress['maxRatio']<=1.000001,stress['worst'])
 check('English produces signed cushion throw',en['negative']['vy']>.1 and en['positive']['vy']<-.1,en)
 check('neutral straight rebound has no tangent drift',abs(en['neutral']['vy'])<1e-8,en['neutral'])
 check('signed English is dissipative',all(v['after']<=v['before']+1e-8 for v in en.values()),en)
 check('600 physical wall approaches include impacts',phys['contacts']>500,phys)
 check('600 physical approaches have no NaN',phys['nonfinite']==0,phys)
 check('600 physical approaches have no energy growth',phys['maxRatio']<=1.000001,phys)
 jaw=measurements['coincidentJaw'];check('exact jaw coincidence separates safely',jaw['finite'] and jaw['distance']>=19.2,jaw)
 check('no browser JavaScript errors',not errors,errors)
 browser.close()
res={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'measurements':measurements,'limitations':'Rubber restitution/friction constants remain estimates; not measured on physical table or Samsung.'}
(P.parent/'POOL_WORLD_5.9_CUSHION_ENERGY_RESULTS.json').write_text(json.dumps(res,indent=2))
print('SUMMARY',res['passed'],'/',res['total'],flush=True)
if res['passed']!=res['total']:raise SystemExit(1)
