"""Measured, deterministic 2D pocket-jaw/rail physics fixtures in real Chromium."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib,json,math,re
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_5.5_STAGING_MATCH.html'
checks=[]
def record(name,passed,details):
    checks.append({'name':name,'passed':bool(passed),'details':details})
    print(('PASS ' if passed else 'FAIL ')+name+' '+str(details),flush=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(P.read_text(),wait_until='load')
    def case(x,y,vx,vy,steps=75):
        return page.evaluate('''({x,y,vx,vy,steps})=>{
          rack();for(const b of balls)if(b.id!==1)b.potted=true;
          const b=balls.find(v=>v.id===1);Object.assign(b,{x,y,vx,vy,spin:0,follow:0,potted:false});
          shot={player:1,breakShot:false,firstHit:1,railAfterContact:false,pocketed:[],scratch:false};
          let maxEnergy=vx*vx+vy*vy,firstImpact=null;
          for(let i=0;i<steps&&!b.potted;i++){
            const before=b.vx*b.vx+b.vy*b.vy;
            physics(STEP);
            const energy=b.vx*b.vx+b.vy*b.vy;
            if(energy>maxEnergy)maxEnergy=energy;
            if(!firstImpact && shot.railAfterContact)firstImpact={step:i,x:b.x,y:b.y,vx:b.vx,vy:b.vy};
          }
          return {potted:b.potted,x:b.x,y:b.y,vx:b.vx,vy:b.vy,maxEnergy,initialEnergy:vx*vx+vy*vy,rail:shot.railAfterContact,firstImpact};
        }''',{'x':x,'y':y,'vx':vx,'vy':vy,'steps':steps})
    m=550
    # Direct side pocket: must capture ball; shouldn't bounce from invisible full rail.
    center=case(m,78+33,0,-2,60)
    record('straight side-pocket entry',center['potted'],center)
    # At pocket nose, ball must glance off the jaw rather than teleport through cloth edge.
    jaw=case(m+27*1.25,78+12.2+3,0,-2,20)
    record('side-pocket jaw rebounds',not jaw['potted'] and jaw['rail'] and jaw['firstImpact'] is not None and jaw['firstImpact']['vy']>0,jaw)
    record('side-pocket jaw does not add energy',jaw['maxEnergy']<=jaw['initialEnergy']*1.001,jaw)
    # Corner approach on a 45 degree line remains pocketable.
    corner=case(79+34,78+34,-2,-2,70)
    record('corner pocket diagonal entry',corner['potted'],corner)
    cornerjaw=case(79+27*1.25,78+12.2+3,0,-2,30)
    record('corner-pocket jaw rebounds',not cornerjaw['potted'] and cornerjaw['rail'] and cornerjaw['firstImpact'] is not None and cornerjaw['firstImpact']['vy']>0,cornerjaw)
    # Flat long rail still bounces and loses energy.
    rail=case(300,78+12.2+.1,1,-2,10)
    record('long rail rebound',rail['rail'] and rail['firstImpact']['vy']>0 and not rail['potted'],rail)
    record('long rail no energy creation',rail['maxEnergy']<=rail['initialEnergy']*1.001,rail)
    record('no browser JS errors',not errors,errors)
    browser.close()
passed=sum(c['passed'] for c in checks)
(P.parent/'POOL_WORLD_5.5_POCKET_TEST_RESULTS.json').write_text(json.dumps({'passed':passed,'total':len(checks),'checks':checks},indent=2))
print('SUMMARY',passed,'/',len(checks))
if passed!=len(checks):raise SystemExit(1)