"""Sustained 3-4fps shot pacing: real physics wall time, bounded hitches and cue travel.
Synthetic Chromium rAF timing only; NOT Samsung A37 acceptance or visual FPS.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed:print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        tag=f'{width}x{height}'
        for fps in (3,3.5,4,4.5,5,6,15,60):
            data=page.evaluate("""fps=>{
                const op=physics,orr=render,os=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    let t=1000,minTicks=100,maxTicks=0;
                    for(let i=0;i<24;i++){
                        const before=ticks;t+=1000/fps;frame(t);
                        minTicks=Math.min(minTicks,ticks-before);
                        maxTicks=Math.max(maxTicks,ticks-before);
                    }
                    return {fps,ticks,expected:24*120/fps,minTicks,maxTicks,debt:accumulator};
                }finally{
                    physics=op;render=orr;settled=os;shooting=false;
                    accumulator=0;slowFrameStreak=0;
                }
            }""",fps)
            check(f'{tag} {fps}fps no slow-motion physics',
                abs(data['ticks']-data['expected'])<=2,data)
            check(f'{tag} {fps}fps no accumulated time debt',
                0<=data['debt']<2/120,data)
            check(f'{tag} {fps}fps bounded per-frame work',
                data['minTicks']>0 and data['maxTicks']<=(44 if fps<=4.5 else 28 if fps<=5 else 22),data)
        for ms in (180,240,320,400):
            data=page.evaluate("""ms=>{
                const op=physics,orr=render,os=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    frame(1000+ms);const first=ticks;
                    frame(1000+ms+1000/60);
                    return {ms,first,second:ticks-first,debt:accumulator};
                }finally{
                    physics=op;render=orr;settled=os;shooting=false;
                    accumulator=0;slowFrameStreak=0;
                }
            }""",ms)
            check(f'{tag} isolated {ms}ms hitch keeps 8-tick CPU guard',
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
                for(let i=1;i<=14;i++)frame(1000+i*1000/3.5);
                const actual={x:balls[0].x,y:balls[0].y,
                    vx:balls[0].vx,vy:balls[0].vy,debt:accumulator};
                start();
                for(let i=0;i<480;i++)physics(STEP);
                const reference={x:balls[0].x,y:balls[0].y,
                    vx:balls[0].vx,vy:balls[0].vy};
                return {actual,reference};
            }finally{render=oldRender;sound=oldSound}
        }""")
        a,b=motion['actual'],motion['reference']
        check(f'{tag} 3.5fps real cue travel matches 120Hz reference',
            math.hypot(a['x']-b['x'],a['y']-b['y'])<2.0,motion)
        check(f'{tag} 3.5fps real cue velocity matches reference',
            math.hypot(a['vx']-b['vx'],a['vy']-b['vy'])<.15,motion)
        check(f'{tag} no browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_THREEFPS_MOTION_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Synthetic Chromium rAF, not measured Samsung FPS or human shot feel.'
},indent=2))
print('THREEFPS MOTION',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
