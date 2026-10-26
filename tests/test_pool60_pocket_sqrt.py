"""Pool World v10.1: pocket capture avoids redundant square roots at 120 Hz.

Each ball checks six pockets on every active physics tick. Compare squared
distance against the identical capture radius, retaining all six mouths.
The Chromium fixtures are not Samsung device/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys, math

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        label=f'{width}x{height}'
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        static=page.evaluate("""() => {
            const saved=Math.hypot;
            const points=[];
            for(let j=0;j<4;j++)for(let i=0;i<4;i++)
                points.push(makeBall(j*4+i,205+i*175,175+j*92));
            balls=points;shot=null;shooting=false;events.length=0;
            let calls=0;
            Math.hypot=function(...args){calls++;return saved(...args)};
            try {
                physics(STEP);
                const first=calls;
                for(let i=0;i<23;i++)physics(STEP);
                return {first,total:calls,
                    finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite)),
                    potted:balls.filter(b=>b.potted).length,
                    moved:balls.some((b,i)=>Math.abs(b.x-(205+i%4*175))>.001)};
            }finally{Math.hypot=saved}
        }""")
        check(label+' pocket broadphase avoids six sqrt calls per interior ball',
            static['first']<=48,static)
        check(label+' 24 idle physics ticks avoid repeated pocket sqrt work',
            static['total']<=1152,static)
        check(label+' static rack remains finite, unpotted and stationary',
            static['finite'] and static['potted']==0 and not static['moved'],static)

        fixtures=page.evaluate("""() => {
            const out=[];
            const threshold=pocket*.74;
            for(let i=0;i<holes.length;i++){
                const [hx,hy]=holes[i];
                // Point into the cloth, away from the outer table boundary.
                const dx=hx===L?1:hx===R?-1:0;
                const dy=dx?0:hy<T?1:-1;
                const probe=(distance)=>{
                    balls=[makeBall(0,hx+dx*distance,hy+dy*distance)];
                    shot=null;shooting=false;events.length=0;
                    physics(STEP);
                    return {potted:balls[0].potted,
                        finite:[balls[0].x,balls[0].y,balls[0].vx,balls[0].vy]
                            .every(Number.isFinite)};
                };
                out.push({id:i,center:probe(0),
                    inside:probe(threshold-.08),
                    outside:probe(threshold+.08)});
            }
            return out;
        }""")
        for fixture in fixtures:
            k=fixture['id']
            check(label+f' pocket {k} centre captured',
                fixture['center']['potted'] and fixture['center']['finite'],fixture)
            check(label+f' pocket {k} just-inside threshold captured',
                fixture['inside']['potted'] and fixture['inside']['finite'],fixture)
            check(label+f' pocket {k} just-outside threshold stays in play',
                not fixture['outside']['potted'] and fixture['outside']['finite'],fixture)
        check(label+' no JavaScript errors',not errors,errors)
        print('POCKET_SQRT_DIAGNOSTIC',label,json.dumps({
            'stationary':static,'pockets':fixtures}),flush=True)
        page.close()
    browser.close()

result={'passed':sum(x['passed'] for x in checks),'total':len(checks),
    'checks':checks,
    'limitations':'Headless Chromium numerical/CPU-path tests; no physical Samsung frame-rate or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_POCKET_SQRT_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
