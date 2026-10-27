"""Regression: sustained 13.5–14.5fps must not silently slow actual pool shots.

The previous 75ms low-frame threshold omitted 13.34–15fps: a 14fps
callback needs ~8.57 physics ticks but the ordinary eight-tick budget
processes only eight, accumulating/dropping simulation time. These
synthetic Chromium timestamps are not Samsung A37 acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,details):
    checks.append({'name':name,'passed':bool(passed),'details':details})
    if not passed:print('FAIL',name,json.dumps(details),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        label=f'{w}x{h}'
        for fps in (13.5,14,14.5,15,60):
            result=page.evaluate("""fps=>{
                const oldPhysics=physics,oldRender=render,oldSettled=settled;
                let ticks=0,maxTicks=0;
                physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    let t=1000;
                    for(let i=0;i<30;i++){
                        const before=ticks;t+=1000/fps;frame(t);
                        maxTicks=Math.max(maxTicks,ticks-before);
                    }
                    return {fps,ticks,expected:30*120/fps,debt:accumulator,
                        maxTicks,slowFrameStreak};
                }finally{
                    physics=oldPhysics;render=oldRender;settled=oldSettled;
                    shooting=false;accumulator=0;slowFrameStreak=0;
                }
            }""",fps)
            check(f'{label} {fps}fps advances 120Hz physics in wall time',
                abs(result['ticks']-result['expected'])<=2,result)
            check(f'{label} {fps}fps does not bank stale physics debt',
                result['debt']<2/120,result)
            check(f'{label} {fps}fps bounded physics catch-up',
                0<result['maxTicks']<=22,result)
        # Actual moving cue ball: compare wall-time callbacks against 120Hz
        # reference, not only instrumented tick counts.
        for fps in (13.5,14,14.5):
            result=page.evaluate("""fps=>{
                const oldRender=render,oldSound=sound;
                render=()=>{};sound=()=>{};
                const frames=Math.round(fps*2);
                function start(){
                    rack();balls=[makeBall(0,400,285)];breakShot=false;
                    aim=0;spin=0;follow=0;showPower(65);shoot();
                    last=1000;accumulator=0;slowFrameStreak=0;
                }
                try{
                    start();
                    for(let i=1;i<=frames;i++)frame(1000+i*1000/fps);
                    const actual={x:balls[0].x,y:balls[0].y,
                        vx:balls[0].vx,vy:balls[0].vy,debt:accumulator};
                    start();
                    for(let i=0;i<240;i++)physics(STEP);
                    const reference={x:balls[0].x,y:balls[0].y,
                        vx:balls[0].vx,vy:balls[0].vy};
                    return {fps,frames,actual,reference};
                }finally{render=oldRender;sound=oldSound}
            }""",fps)
            a=result['actual'];r=result['reference']
            check(f'{label} {fps}fps real cue travel agrees with 120Hz reference',
                math.hypot(a['x']-r['x'],a['y']-r['y'])<2,result)
            check(f'{label} {fps}fps cue speed agrees with 120Hz reference',
                math.hypot(a['vx']-r['vx'],a['vy']-r['vy'])<.15,result)
        for hitch in (65,70,74):
            result=page.evaluate("""ms=>{
                const oldPhysics=physics,oldRender=render,oldSettled=settled;
                let ticks=0;physics=()=>{ticks++};render=()=>{};settled=()=>false;
                try{
                    rack();shooting=true;last=1000;accumulator=0;slowFrameStreak=0;
                    frame(1000+ms);const first=ticks;
                    frame(1000+ms+1000/60);
                    return {first,second:ticks-first,streak:slowFrameStreak};
                }finally{
                    physics=oldPhysics;render=oldRender;settled=oldSettled;
                    shooting=false;accumulator=0;slowFrameStreak=0;
                }
            }""",hitch)
            check(f'{label} isolated {hitch}ms hitch retains eight-tick budget',
                result['first']<=8 and result['second']<=8,result)
            check(f'{label} isolated {hitch}ms hitch does not persist as slow FPS',
                result['streak']==0,result)
        check(f'{label} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(x['passed'] for x in checks),'total':len(checks),
    'checks':checks,
    'limitations':'Synthetic Chromium callback timing only. Not Samsung frame pacing, GPU rendering, or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_14FPS_MOTION_RESULTS.json').write_text(json.dumps(result,indent=2))
print('13.5-14.5FPS MOTION',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
