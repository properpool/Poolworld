"""Collision displacement must not visually skid the pool-ball texture.

The legacy renderer rotated balls using positions captured BEFORE ball-ball
impulse and overlap projection. On a hard impact, that produces a sphere whose
visible stripe/measle rotation disagrees with the centre's actual travel.
Check a real Chromium physics tick and a rendered frame across four viewports.
This is NOT physical Samsung smoothness or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)

CASES=[
    {'name':'head-on', 'a':[400,285,6,0], 'b':[423,285,0,0]},
    {'name':'glancing', 'a':[400,285,6,0.4], 'b':[422.5,292,0,0]},
    {'name':'diagonal', 'a':[400,280,5,3], 'b':[419,295,0,0]},
    {'name':'rail-side', 'a':[98,285,6,0], 'b':[121,285,0,0]},
]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
                              is_mobile=w<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for case in CASES:
            data=page.evaluate("""c=>{
                rack();
                balls=[makeBall(0,c.a[0],c.a[1]),makeBall(1,c.b[0],c.b[1])];
                balls[0].vx=c.a[2];balls[0].vy=c.a[3];
                balls[1].vx=c.b[2];balls[1].vy=c.b[3];
                shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
                      pocketed:[],scratch:false,targetEight:false};
                const before=balls.map(b=>({x:b.x,y:b.y}));
                physics(STEP);
                const result=balls.map((b,i)=>{
                    const dx=b.x-before[i].x,dy=b.y-before[i].y;
                    const expected=makeBall(b.id,before[i].x,before[i].y);
                    rotateRoll(expected,dx,dy);
                    const dot=Math.min(1,Math.abs(
                      b.rollQ[0]*expected.rollQ[0]+b.rollQ[1]*expected.rollQ[1]+
                      b.rollQ[2]*expected.rollQ[2]+b.rollQ[3]*expected.rollQ[3]));
                    return {id:b.id,dx,dy,rollError:2*Math.acos(dot),
                            vx:b.vx,vy:b.vy,actual:b.rollQ.slice(),
                            expected:expected.rollQ.slice()};
                });
                const distance=Math.hypot(balls[1].x-balls[0].x,
                                          balls[1].y-balls[0].y);
                const firstHit=shot.firstHit;
                shot=null;
                return {result,distance,firstHit};
            }""",case)
            label=f'{w}x{h} {case["name"]}'
            check(label+' first object contact is registered',data['firstHit']==1,data)
            check(label+' impact transfers momentum',math.hypot(data['result'][1]['vx'],
                         data['result'][1]['vy'])>.1,data)
            check(label+' collision separation stays safe',data['distance']>=24.4-.01,data)
            for b in data['result']:
                check(label+f' ball {b["id"]} orientation follows FINAL centre displacement',
                      b['rollError']<.00002,b)
                check(label+f' ball {b["id"]} state finite',
                      all(math.isfinite(b[k]) for k in ('dx','dy','vx','vy','rollError')),b)
        check(f'{w}x{h} no browser exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
result={'passed':passed,'total':len(checks),'checks':checks,
        'limits':'Chromium physics/rotation checks, not measured Samsung FPS, visual smoothness or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_COLLISION_ROLL_ALIGNMENT_RESULTS.json').write_text(json.dumps(result,indent=2))
print('COLLISION ROLL ALIGNMENT',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
