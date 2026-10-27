"""Swept pocket-well capture: shallow fast shots must not tunnel through a pocket.

Uses the real Chromium 120 Hz physics() and six physical pocket wells.
Endpoints outside a well can still cross its capture circle within one tick.
Headless browser evidence is NOT physical Samsung/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok:print('FAIL',name,details,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for hole in range(6):
            for miss in (False,True):
                d=page.evaluate("""([hole,miss])=>{
                  const [hx,hy]=holes[hole],capture=pocket*.74;
                  const corner=hole===0||hole===2||hole===3||hole===5;
                  const offset=miss?capture+.25:capture-.08;
                  let x,y,vx,vy;
                  if(corner){
                    x=hx+(hole===0||hole===3?offset:-offset);
                    y=hy-2.2;vx=0;vy=8.8;
                  }else{
                    x=hx-2.2;y=hy+(hole===1?offset:-offset);
                    vx=8.8;vy=0;
                  }
                  const b=makeBall(1,x,y);b.vx=vx;b.vy=vy;
                  balls=[b];shot={player:1,breakShot:false,firstHit:null,
                    railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                  shooting=true;breakShot=false;events.length=0;
                  const startDist=Math.hypot(x-hx,y-hy);
                  physics(STEP);
                  const endDist=Math.hypot(b.x-hx,b.y-hy);
                  return {startDist,endDist,capture,potted:b.potted,
                    pocketed:shot.pocketed.slice(),pos:[b.x,b.y],
                    velocity:[b.vx,b.vy],soundCount:events.filter(e=>e[0]==='pocket').length};
                }""",[hole,miss])
                name=f'{w}x{h} pocket {hole} '+('near miss' if miss else 'swept shallow entry')
                check(name+' start outside capture well',
                    d['startDist']>d['capture'],d)
                if miss:
                    check(name+' stays unpotted',not d['potted'] and d['pocketed']==[],d)
                else:
                    check(name+' real crossing is potted once',
                        d['potted'] and d['pocketed']==[1] and d['soundCount']==1,d)
                    check(name+' crossing endpoint outside well',
                        d['endDist']>d['capture'],d)
                check(name+' finite coordinates',
                    all(math.isfinite(v) for v in d['pos']+d['velocity']),d)
        # Cue-ball crossing is a scratch, not an object pocket.
        d=page.evaluate("""()=>{
          const b=makeBall(0,550-2.2,70+pocket*.74-.08);
          b.vx=8.8;balls=[b];
          shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
            pocketed:[],scratch:false,targetEight:false};
          shooting=true;events.length=0;physics(STEP);
          return {potted:b.potted,scratch:shot.scratch,pocketed:shot.pocketed.slice()};
        }""")
        check(f'{w}x{h} cue ball crossing is a scratch',
            d['potted'] and d['scratch'] and d['pocketed']==[0],d)
        check(f'{w}x{h} no browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SWEPT_POCKET_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limitations':'Real Chromium physics ticks only; no physical Samsung/human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
