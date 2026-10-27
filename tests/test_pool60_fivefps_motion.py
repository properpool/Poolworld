"""Sustained 5-5.5fps simulation must not make full-power shots run in slow motion.

Synthetic Chromium requestAnimationFrame timestamps; this is not Samsung A37
performance measurement, smooth visual FPS, or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1100,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        tag=f'{w}x{h}'
        for fps in (5,5.5,6,15,60):
            data=page.evaluate("""fps=>{
                const oldPhysics=physics,oldRender=render,oldSettled=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    let t=1000,maxTicks=0,minTicks=100;
                    for(let i=0;i<24;i++){
                        const prior=ticks;t+=1000/fps;frame(t);
                        maxTicks=Math.max(maxTicks,ticks-prior);
                        minTicks=Math.min(minTicks,ticks-prior);
                    }
                    return {fps,ticks,maxTicks,minTicks,debt:accumulator,
                        expected:24*120/fps};
                }finally{
                    physics=oldPhysics;render=oldRender;settled=oldSettled;
                    shooting=false;accumulator=0;slowFrameStreak=0;
                }
            }""",fps)
            check(f'{tag} {fps}fps physics keeps real wall time',
                abs(data['ticks']-data['expected'])<=2,data)
            check(f'{tag} {fps}fps no persistent stale simulation debt',
                0<=data['debt']<2/120,data)
            check(f'{tag} {fps}fps bounded catch-up budget',
                0<data['minTicks'] and data['maxTicks']<=(28 if fps<=5.5 else 22),data)
        for ms in (180,200,240):
            data=page.evaluate("""ms=>{
                const oldPhysics=physics,oldRender=render,oldSettled=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    frame(1000+ms);const first=ticks;
                    frame(1000+ms+1000/60);
                    return {first,second:ticks-first,debt:accumulator};
                }finally{
                    physics=oldPhysics;render=oldRender;settled=oldSettled;
                    shooting=false;accumulator=0;slowFrameStreak=0;
                }
            }""",ms)
            check(f'{tag} isolated {ms}ms hitch remains CPU-bounded',
                data['first']<=8 and data['second']<=8,data)
        motion=page.evaluate("""()=>{
            const oldRender=render,oldSound=sound;
            render=()=>{};sound=()=>{};
            function start(){
                rack();balls=balls.slice(0,1);breakShot=false;
                aim=0;spin=0;follow=0;showPower(85);shoot();
                last=1000;accumulator=0;slowFrameStreak=0;
            }
            try{
                start();
                for(let i=1;i<=20;i++)frame(1000+i*200);
                const actual={x:balls[0].x,y:balls[0].y,
                    vx:balls[0].vx,vy:balls[0].vy,debt:accumulator};
                start();
                for(let i=0;i<480;i++)physics(STEP);
                const reference={x:balls[0].x,y:balls[0].y,
                    vx:balls[0].vx,vy:balls[0].vy};
                return {actual,reference};
            }finally{render=oldRender;sound=oldSound}
        }""")
        a=motion['actual'];b=motion['reference']
        check(f'{tag} real 5fps cue travel matches 120Hz reference',
            math.hypot(a['x']-b['x'],a['y']-b['y'])<2.0,motion)
        check(f'{tag} real 5fps cue velocity matches reference',
            math.hypot(a['vx']-b['vx'],a['vy']-b['vy'])<.15,motion)
        check(f'{tag} browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_FIVEFPS_MOTION_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Synthetic Chromium pacing, not measured Samsung A37 FPS, smoothness or human acceptance.'
},indent=2))
print('FIVEFPS MOTION',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
