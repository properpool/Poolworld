"""Pool World v6.0 real Chromium physics invariants, spin transfer and contact stability."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 print(('PASS' if ok else 'FAIL'),name,str(detail)[:350],flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(P.read_text(),wait_until='load')
 data=page.evaluate('''() => {
  const out={};
  const energy=()=>balls.filter(b=>!b.potted).reduce((sum,b)=>sum+b.vx*b.vx+b.vy*b.vy+.4*(b.spin*b.spin+b.follow*b.follow),0);
  const setup=(x,y,vx,vy,spin=0,follow=0)=>{
   rack();for(const b of balls)if(b.id>1)b.potted=true;
   const a=balls[0],b=balls[1];a.x=400;a.y=285;a.vx=vx;a.vy=vy;a.spin=spin;a.follow=follow;
   b.x=x;b.y=y;b.vx=b.vy=b.spin=b.follow=0;
   shot={player:1,breakShot:false,firstHit:null,pocketed:[],scratch:false,railAfterContact:false};
   return [a,b];
  };
  for(const s of [-1.2,0,1.2]){
   const [a,b]=setup(423.8,285,4,0,s);
   const before=energy();physics(STEP);
   out['english_'+s]={firstHit:shot.firstHit,objectVy:b.vy,objectSpin:b.spin,cueVy:a.vy,cueSpin:a.spin,energyBefore:before,energyAfter:energy()};
  }
  for(const f of [-2.5,0,2.5]){
   const [a,b]=setup(423.8,285,4,0,0,f);
   const before=energy();physics(STEP);
   out['follow_'+f]={firstHit:shot.firstHit,cueVx:a.vx,objectVx:b.vx,follow:a.follow,energyBefore:before,energyAfter:energy()};
  }
  {
   const [a,b]=setup(423.1,292,4,0,0,0);
   const before=energy();physics(STEP);
   out.glancing={firstHit:shot.firstHit,objectSpin:b.spin,cueSpin:a.spin,objectVy:b.vy,cueVy:a.vy,energyBefore:before,energyAfter:energy()};
  }
  {
   const [a,b]=setup(400,285,0,0);
   physics(STEP);
   out.coincident={distance:Math.hypot(a.x-b.x,a.y-b.y),finite:[a.x,a.y,b.x,b.y].every(Number.isFinite)};
  }
  {
   const [a,b]=setup(400,285,3,0);
   physics(STEP);
   out.coincidentMoving={distance:Math.hypot(a.x-b.x,a.y-b.y),finite:[a.x,a.y,b.x,b.y,a.vx,b.vx].every(Number.isFinite)};
  }
  // Repeatable deterministic energy stress on actual collision engine.
  let maxRatio=0,worst=null,nonfinite=0,collisions=0;
  for(let i=0;i<1800;i++){
   const ang=(i%49-24)*.017;
   const speed=.6+(i%31)*.18;
   const spin=(i%17-8)*.15;
   const follow=(i%21-10)*.25;
   const [a,b]=setup(423.8,285+Math.sin(ang)*20,speed,0,spin,follow);
   const before=energy();physics(STEP);
   if(shot.firstHit===1)collisions++;
   const after=energy(),ratio=after/before;
   if(ratio>maxRatio){maxRatio=ratio;worst={i,ratio,before,after,spin,follow,ang,speed}}
   if(![a.x,a.y,a.vx,a.vy,a.spin,a.follow,b.x,b.y,b.vx,b.vy,b.spin].every(Number.isFinite))nonfinite++;
  }
  out.stress={maxRatio,worst,nonfinite,collisions,cases:1800};
  return out;
 }''')
 minus,neutral,plus=[data['english_'+str(s)] for s in [-1.2,0,1.2]]
 check('head-on English contacts object ball',all(v['firstHit']==1 for v in [minus,neutral,plus]),[minus,neutral,plus])
 check('opposite English creates opposite object-ball throw',minus['objectVy']<-.01 and plus['objectVy']>.01,[minus['objectVy'],plus['objectVy']])
 check('opposite English transfers opposite object-ball rotation',minus['objectSpin']>.01 and plus['objectSpin']<-.01,[minus['objectSpin'],plus['objectSpin']])
 check('neutral head-on contact has no artificial throw',abs(neutral['objectVy'])<.001 and abs(neutral['objectSpin'])<.001,neutral)
 check('spin transfer is approximately antisymmetric',abs(minus['objectVy']+plus['objectVy'])<.01 and abs(minus['objectSpin']+plus['objectSpin'])<.01,[minus,plus])
 check('English collision total linear+rotational energy does not grow',all(v['energyAfter']<=v['energyBefore']+1e-5 for v in [minus,neutral,plus]),[minus,neutral,plus])
 gl=data['glancing']
 check('glancing collision generates opposite rotational impulses',gl['firstHit']==1 and gl['cueSpin']*gl['objectSpin']>0 and abs(gl['objectSpin'])>.001,gl)
 check('glancing collision energy dissipates',gl['energyAfter']<gl['energyBefore'],gl)
 fm,fn,fp=[data['follow_'+str(s)] for s in [-2.5,0,2.5]]
 check('draw, neutral and follow have distinct longitudinal cue responses',fm['cueVx']<fn['cueVx']<fp['cueVx'],[fm,fn,fp])
 check('draw/follow do not inject energy',all(v['energyAfter']<=v['energyBefore']+1e-5 for v in [fm,fn,fp]),[fm,fn,fp])
 check('cue draw/follow reservoir is consumed on collision',abs(fm['follow'])<.9 and abs(fp['follow'])<.9,[fm['follow'],fp['follow']])
 check('stationary coincident balls separate safely',data['coincident']['finite'] and data['coincident']['distance']>=24.4,data['coincident'])
 check('moving coincident balls separate safely',data['coincidentMoving']['finite'] and data['coincidentMoving']['distance']>=24.4,data['coincidentMoving'])
 stress=data['stress']
 check('1800 varied impacts preserve finite physics',stress['nonfinite']==0 and stress['collisions']>1000,stress)
 check('1800 varied impacts never increase total tracked kinetic energy',stress['maxRatio']<=1.000001,stress)
 check('no browser JavaScript errors',not errors,errors)
 browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'measurements':data,'limitations':'Simplified 2D rigid-sphere spin model with uncalibrated cushion/jaw restitution, not laboratory pool-table measurements.'}
(P.parent/'POOL_WORLD_6.0_COLLISION_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:raise SystemExit(1)
