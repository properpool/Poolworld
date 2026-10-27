"""Sustained 10/12fps shot-motion slowdown regression.

120Hz physics must advance ~one wall-second per wall-second at 10-12fps,
without an unbounded burst for a one-off 150ms hitch. Real ball travel
must match the same number of fixed-step physics updates. Synthetic
Chromium timestamps do NOT measure physical Samsung FPS or acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, ok, detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,json.dumps(detail),flush=True)

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
        label=f'{w}x{h}'
        for fps in (10,12,15,60):
            data=page.evaluate("""fps=>{
                const oldPhysics=physics,oldRender=render,oldSettled=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;
                    let t=1000,maxTicks=0,minTicks=100;
                    for(let i=0;i<20;i++){
                        const prior=ticks;t+=1000/fps;frame(t);
                        maxTicks=Math.max(maxTicks,ticks-prior);
                        minTicks=Math.min(minTicks,ticks-prior);
                    }
                    return {fps,ticks,maxTicks,minTicks,debt:accumulator,
                        expected:20*120/fps,shooting};
                }finally{
                    physics=oldPhysics;render=oldRender;settled=oldSettled;
                    shooting=false;accumulator=0;
                }
            }""",fps)
            check(f'{label} {fps}fps advances 120Hz physics in real time',
                abs(data['ticks']-data['expected'])<=2,data)
            check(f'{label} {fps}fps no sustained stale physics debt',
                data['debt']<2/120,data)
            check(f'{label} {fps}fps bounded work per callback',
                data['maxTicks']<=15 and data['minTicks']>=0,data)
        # A single 150ms hitch should still be amortised, not forced
        # through all 18 simulation steps in one rendering callback.
        hitch=page.evaluate("""()=>{
            const oldPhysics=physics,oldRender=render,oldSettled=settled;
            let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
            try{
                rack();shooting=true;last=1000;accumulator=0;
                frame(1150);const first=ticks;
                frame(1150+1000/60);frame(1150+2000/60);
                return {first,total:ticks,debt:accumulator};
            }finally{
                physics=oldPhysics;render=oldRender;settled=oldSettled;
                shooting=false;accumulator=0;
            }
        }""")
        check(f'{label} isolated 150ms hitch stays within eight-tick burst',
            6<=hitch['first']<=8,hitch)
        check(f'{label} hitch debt drains across later callbacks',
            hitch['total']>=20 and hitch['debt']<2/120,hitch)
        # Use actual physics, not just an instrumented tick counter:
        # a one-second, 10fps free cue shot must finish at the same
        # state as 120 manually executed fixed-step physics ticks.
        motion=page.evaluate("""()=>{
            const oldRender=render,oldSound=sound;
            render=()=>{};sound=()=>{};
            function start(){
                rack();balls=balls.slice(0,1);breakShot=false;
                aim=0;spin=0;follow=0;showPower(100);shoot();
                last=1000;accumulator=0;
            }
            try{
                start();
                for(let i=1;i<=10;i++)frame(1000+i*100);
                const actual={x:balls[0].x,y:balls[0].y,
                    vx:balls[0].vx,vy:balls[0].vy,debt:accumulator};
                start();
                for(let i=0;i<120;i++)physics(STEP);
                const reference={x:balls[0].x,y:balls[0].y,
                    vx:balls[0].vx,vy:balls[0].vy};
                return {actual,reference};
            }finally{render=oldRender;sound=oldSound}
        }""")
        a=motion['actual'];r=motion['reference']
        check(f'{label} 10fps cue-ball travel matches 120Hz reference',
            math.hypot(a['x']-r['x'],a['y']-r['y'])<2.0,motion)
        check(f'{label} 10fps cue-ball velocity matches 120Hz reference',
            math.hypot(a['vx']-r['vx'],a['vy']-r['vy'])<.15,motion)
        check(f'{label} browser JavaScript error-free',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_LOWFPS_MOTION_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Synthetic Chromium timestamps, not physical Samsung device FPS or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
