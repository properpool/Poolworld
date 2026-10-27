"""Sustained 6-9fps physics must not make a shot run in slow motion.

Chromium synthetic rAF timestamps isolate fixed-step physics pacing. This
does not establish physical Samsung A37 FPS, visual smoothness or acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

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
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        label=f'{w}x{h}'
        for fps in (6,7,8,9,15,60):
            data=page.evaluate("""fps=>{
                const oldPhysics=physics,oldRender=render,oldSettled=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    let t=1000,maxTicks=0;
                    for(let i=0;i<20;i++){
                        const prior=ticks;t+=1000/fps;frame(t);
                        maxTicks=Math.max(maxTicks,ticks-prior);
                    }
                    return {fps,ticks,maxTicks,debt:accumulator,expected:20*120/fps};
                }finally{
                    physics=oldPhysics;render=oldRender;settled=oldSettled;
                    shooting=false;accumulator=0;slowFrameStreak=0;
                }
            }""",fps)
            check(f'{label} {fps}fps fixed physics matches wall time',
                abs(data['ticks']-data['expected'])<=2,data)
            check(f'{label} {fps}fps has no persistent backlog',
                data['debt']<2/120,data)
            check(f'{label} {fps}fps bounded per-frame catch-up',
                0<data['maxTicks']<=22,data)
        for hitch_ms in (125,160,200):
            hitch=page.evaluate("""ms=>{
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
            }""",hitch_ms)
            check(f'{label} isolated {hitch_ms}ms stall remains bounded',
                hitch['first']<=8 and hitch['second']<=8,hitch)
        # Genuine physics rather than mocked tick counts: free cue shot at
        # sustained 8fps must track 120 direct physics updates over one second.
        motion=page.evaluate("""()=>{
            const oldRender=render,oldSound=sound;
            render=()=>{};sound=()=>{};
            function start(){
                rack();balls=balls.slice(0,1);breakShot=false;
                aim=0;spin=0;follow=0;showPower(100);shoot();
                last=1000;accumulator=0;slowFrameStreak=0;
            }
            try{
                start();
                for(let i=1;i<=8;i++)frame(1000+i*125);
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
        check(f'{label} 8fps actual shot travel matches 120Hz reference',
            math.hypot(a['x']-r['x'],a['y']-r['y'])<2,motion)
        check(f'{label} 8fps actual cue velocity matches 120Hz reference',
            math.hypot(a['vx']-r['vx'],a['vy']-r['vy'])<.15,motion)
        check(f'{label} no browser exceptions',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
    'checks':checks,'limitations':'Synthetic Chromium rAF timestamps only; no Samsung FPS, smoothness, human acceptance.'}
(ROOT/'POOL_WORLD_6.0_SUB10FPS_MOTION_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUB-10FPS MOTION',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
