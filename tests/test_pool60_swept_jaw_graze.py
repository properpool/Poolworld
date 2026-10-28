"""A fast grazing ball crossing a rubber pocket-jaw contact circle must
rebound even if both 120Hz endpoint samples lie outside it. The matched
near-miss must NOT bounce. These Chromium fixtures are not physical Samsung
Galaxy A37 or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'details':detail})
    if not ok: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=width<1100)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for top in (True,False):
            for left in (True,False):
                for direction in (-1,1):
                    for level in (75,90):
                        for scenario in ('swept-graze','clean-miss','endpoint-overlap'):
                            result=page.evaluate("""([top,left,direction,level,scenario])=>{
                              const jx=W/2+(left?-mouth:mouth);
                              const jy=top?T:B, inward=top?1:-1;
                              const radius=rad+jawRadius;
                              const offset=scenario==='clean-miss'?radius+.5:
                                           scenario==='endpoint-overlap'?radius-3.5:
                                           radius-.02;
                              const speed=shotSpeed(level,false);
                              const cue=makeBall(0,300,285);
                              const startX=scenario==='endpoint-overlap'?jx-direction*(speed*.5+8):
                                           jx-direction*speed*.25;
                              const b=makeBall(1,startX,jy+inward*offset);
                              b.vx=direction*speed;
                              balls=[cue,b];turn=1;groups={1:'solids',2:'stripes'};
                              breakShot=false;ballInHand=false;gameOver=false;
                              shot={player:1,breakShot:false,firstHit:1,
                                railAfterContact:false,pocketed:[],scratch:false,
                                targetEight:false};
                              shooting=true;events.length=0;pocketVisuals.length=0;
                              const initial={x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                                speed:Math.hypot(b.vx,b.vy),
                                entryDistance:Math.hypot(b.x-jx,b.y-jy),
                                calibration:shotSpeed(level,false)};
                              physics(STEP);
                              return {initial,final:{x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                                speed:Math.hypot(b.vx,b.vy),
                                distance:Math.hypot(b.x-jx,b.y-jy)},
                                potted:b.potted,rail:shot.railAfterContact,
                                pocketed:shot.pocketed.slice(),
                                sounds:events.map(e=>e[0]),
                                cue:[cue.x,cue.y,cue.vx,cue.vy],
                                calibration:shotSpeed(level,false),
                                state:balls.flatMap(x=>[x.x,x.y,x.vx,x.vy])};
                            }""",[top,left,direction,level,scenario])
                            tag=f'{width}x{height} {"top" if top else "bottom"} {"left" if left else "right"} dir={direction} power={level} {scenario}'
                            graze=scenario=='swept-graze'
                            miss=scenario=='clean-miss'
                            check(tag+' physical jaw contact and legal rail',
                                  (result['rail'] if not miss else not result['rail']),result)
                            check(tag+' correct inward rebound or clear travel',
                                  (result['final']['vy']*(1 if top else -1)>.10
                                   if not miss else abs(result['final']['vy'])<1e-9),result)
                            check(tag+' no phantom pocket or cue movement',
                                  not result['potted'] and not result['pocketed']
                                  and result['cue']==[300,285,0,0],result)
                            check(tag+' collision dissipates rather than adds energy',
                                  result['final']['speed']<=result['initial']['speed']+1e-8,
                                  result)
                            check(tag+' swept start outside jaw' if graze else tag+' finite coordinates',
                                  (result['initial']['entryDistance']>19.2 and
                                   result['final']['distance']>19.2)
                                  if graze else all(math.isfinite(x) for x in result['state']),
                                  result)
                            check(tag+' calibrated shot strength remains unchanged',
                                  abs(result['calibration']-result['initial']['calibration'])<1e-10,
                                  result)
        check(f'{width}x{height} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_SWEPT_JAW_GRAZE_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium physics only; physical Samsung and human acceptance remain release-blocking.'},indent=2))
print('SWEPT JAW GRAZE SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
