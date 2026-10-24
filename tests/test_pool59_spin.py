"""Measured cue follow/draw and rail English in Chromium, no fixtures during shots."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_5.9_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail):
 checks.append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(P.read_text(),wait_until='load')
 d=page.evaluate('''() => {
  const out={};
  // Same natural collision geometry and incoming speed, with only cue spin varied.
  for(const follow of [-2.5,0,2.5]){
   rack();for(const b of balls)if(b.id>1)b.potted=true;
   const c=balls[0],o=balls[1];c.x=350;c.y=285;o.x=460;o.y=285;
   c.vx=4;c.vy=0;c.follow=follow;c.spin=0;o.vx=o.vy=0;
   shot={player:1,firstHit:null,pocketed:[],scratch:false,railAfterContact:false};
   let steps=0;while(shot.firstHit===null&&steps++<200)physics(STEP);
   out['cue_'+follow]={steps,firstHit:shot.firstHit,cueVX:c.vx,objectVX:o.vx};
  }
  // Side-spin must not produce a curved trajectory on empty cloth.
  for(const english of [-1.2,0,1.2]){
   rack();for(const b of balls)if(b.id>0)b.potted=true;
   const c=balls[0];c.x=350;c.y=285;c.vx=3;c.vy=0;c.spin=english;
   for(let n=0;n<80;n++)physics(STEP);
   out['cloth_'+english]={x:c.x,y:c.y,vx:c.vx,vy:c.vy};
  }
  // A right-cushion strike should show opposite tangential deflections for ± English.
  for(const english of [-1.2,0,1.2]){
   rack();for(const b of balls)if(b.id>1)b.potted=true;
   const c=balls[1];c.x=R-rad-.2;c.y=285;c.vx=2.8;c.vy=0;c.spin=english;
   shot={player:1,firstHit:1,pocketed:[],scratch:false,railAfterContact:false};
   physics(STEP);
   out['rail_'+english]={vx:c.vx,vy:c.vy,spin:c.spin,railAfterContact:shot.railAfterContact};
  }
  return out;
 }''')
 check('draw reverses cue ball after head-on impact',d['cue_-2.5']['cueVX']<-.4,d['cue_-2.5'])
 check('neutral stun mostly stops cue ball',abs(d['cue_0']['cueVX'])<.15,d['cue_0'])
 check('follow drives cue forward after head-on impact',d['cue_2.5']['cueVX']>.4,d['cue_2.5'])
 check('head-on object ball receives near-identical speed across cue spin settings',max(d['cue_'+str(f)]['objectVX'] for f in [-2.5,0,2.5])-min(d['cue_'+str(f)]['objectVX'] for f in [-2.5,0,2.5])<.001,[d['cue_'+str(f)]['objectVX'] for f in [-2.5,0,2.5]])
 check('side spin does not curve free travel',max(abs(d['cloth_'+str(f)]['y']-285) for f in [-1.2,0,1.2])<.01,[d['cloth_'+str(f)] for f in [-1.2,0,1.2]])
 check('spin-free straight cushion rebound remains straight',abs(d['rail_0']['vy'])<.001,d['rail_0'])
 check('opposite English gives opposite rail deflection',d['rail_-1.2']['vy']>.15 and d['rail_1.2']['vy']<-.15,[d['rail_-1.2'],d['rail_1.2']])
 check('English rail impulses dissipate spin and preserve inward rebound',all(d['rail_'+str(f)]['vx']<0 and abs(d['rail_'+str(f)]['spin'])<abs(f) and d['rail_'+str(f)]['railAfterContact'] for f in [-1.2,1.2]),[d['rail_-1.2'],d['rail_1.2']])
 check('no JS exceptions',not errors,errors)
 browser.close()
res={'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'measurements':d,'limits':'Arcade approximation, not calibrated from physical table or Samsung measurements.'}
(P.parent/'POOL_WORLD_5.9_SPIN_RESULTS.json').write_text(json.dumps(res,indent=2))
print('SUMMARY',res['passed'],'/',res['total'])
if res['passed']!=res['total']:raise SystemExit(1)
