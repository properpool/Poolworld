"""Jaw collision broad-phase regression under real 120Hz gameplay.

The rubber noses are all on the four cushion edges. Balls whose centres
are farther than ball+jaw radius from every edge cannot touch any nose,
so scanning all 12 noses on every tick wastes work during full-rack play.
Chromium counts do not constitute physical Samsung/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, passed, detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed:
        print('FAIL',name,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        data=page.evaluate("""() => {
            const originalIterator=jaws[Symbol.iterator];
            const originalCollide=collideJaw;
            let scans=0,calls=0;
            jaws[Symbol.iterator]=function*(){
                scans++;
                yield* originalIterator.call(this);
            };
            collideJaw=function(b){calls++;return originalCollide(b)};
            const measure=()=>({scans,calls});
            let interior,near,full;
            try {
                const inset=rad+jawRadius+.2;
                const points=[
                    [W/2,H/2],[L+inset,T+inset],[R-inset,B-inset],
                    [L+inset,B-inset],[R-inset,T+inset],
                    [(L+R)/2,T+inset],[(L+R)/2,B-inset]
                ];
                const b=makeBall(1,0,0);
                for(const [x,y] of points){
                    b.x=x;b.y=y;b.vx=0;b.vy=0;
                    for(let i=0;i<24;i++)collideJaw(b);
                }
                interior={...measure(),positionsSafe:points.every(([x,y])=>
                    x>=L+rad+jawRadius&&x<=R-rad-jawRadius&&
                    y>=T+rad+jawRadius&&y<=B-rad-jawRadius),
                    finite:Number.isFinite(b.x)&&Number.isFinite(b.y)};
                scans=0;calls=0;
                const results=[];
                for(let i=0;i<jaws.length;i++){
                    const [jx,jy]=jaws[i],nx=jy===T?0:jy===B?0:jx===L?1:-1,
                          ny=jy===T?1:jy===B?-1:0;
                    const q=makeBall(1,jx+nx*(rad+jawRadius-.3),
                                      jy+ny*(rad+jawRadius-.3));
                    q.vx=-nx*4;q.vy=-ny*4;
                    collideJaw(q);
                    results.push({jaw:i,dist:Math.hypot(q.x-jx,q.y-jy),
                        speed:Math.hypot(q.vx,q.vy),
                        finite:[q.x,q.y,q.vx,q.vy,q.spin].every(Number.isFinite)});
                }
                near={...measure(),results};
                scans=0;calls=0;
                rack();aim=0;showPower(100);shoot();
                last=0;accumulator=0;
                for(let i=1;i<=72;i++)frame(1000+i*1000/60);
                full={...measure(),moving:balls.some(q=>q.id>0&&
                    (q.potted||Math.hypot(q.vx,q.vy)>.02)),
                    finite:balls.every(q=>[q.x,q.y,q.vx,q.vy].every(Number.isFinite))};
            }finally{
                jaws[Symbol.iterator]=originalIterator;
                collideJaw=originalCollide;
            }
            return {interior,near,full};
        }""")
        label=f'{width}x{height}'
        inside,near,full=data['interior'],data['near'],data['full']
        check(label+' safe interior fixture geometry',inside['positionsSafe'],inside)
        check(label+' interior avoids all jaw iterator scans',inside['scans']==0,inside)
        check(label+' interior collision routine exercised',inside['calls']==168,inside)
        check(label+' interior remains finite',inside['finite'],inside)
        check(label+' all twelve jaw fixtures were tested',len(near['results'])==12,near)
        check(label+' jaw-adjacent balls still scan noses',near['scans']>=12,near)
        check(label+' jaw contact clearance preserved',
            all(q['dist']>=12.2+7-.02 for q in near['results']),near)
        check(label+' jaw contact dissipative and finite',
            all(q['finite'] and q['speed']<=4+1e-8 for q in near['results']),near)
        check(label+' full-rack active physics exercised',
            full['calls']>=100 and full['moving'],full)
        check(label+' full-rack jaw scans below 80 percent of calls',
            full['scans']<full['calls']*.8,full)
        check(label+' full-rack positions and velocities finite',full['finite'],full)
        check(label+' no browser exceptions',not errors,errors)
        print('JAW_BROADPHASE_PROFILE',label,json.dumps(data),flush=True)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_JAW_BROADPHASE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Headless Chromium scan counts, not physical Samsung frame rate or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
