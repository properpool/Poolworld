"""Pool World v10.43: no shot fast-forward or reverse interpolation after mobile tab suspension.

A >1s rAF silence is consistent with backgrounding, screen locking or OS
suspension, not a normal moving-shot frame. The existing code charges 250ms
to the active shot, renders an eight-tick jump, and then spends several
60Hz callbacks catching up. This test exercises actual cue-ball travel,
physics-step counts, and rendered position. Chromium synthetic timing only:
NOT Samsung A37 FPS, touch latency, or human acceptance.
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
    for width,height in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for gap in (1200,3000,10000):
            for power in (25,75):
                for warmup in (1,12):
                    result=page.evaluate("""({gap,power,warmup})=>{
                        const op=physics,orr=render,os=sound,ost=settled,odb=drawBall;
                        let ticks=0,drawnCue=null;
                        physics=(dt)=>{ticks++;op(dt)};
                        sound=()=>{};settled=()=>false;
                        drawBall=(b,q)=>{if(b.id===0)drawnCue=b.x};
                        try{
                            rack();balls=[makeBall(0,400,285)];
                            breakShot=false;aim=0;spin=0;follow=0;showPower(power);
                            if(!shoot())throw Error('shot failed');
                            shotFirstFramePending=false;
                            let t=1000;last=t;accumulator=0;slowFrameStreak=0;
                            for(let i=0;i<warmup;i++){t+=1000/60;frame(t)}
                            const prior={x:balls[0].x,vx:balls[0].vx,
                                impulse:shotSpeed(power,false),selected:power};
                            const before=ticks;
                            t+=gap;frame(t);
                            const pause={ticks:ticks-before,travel:balls[0].x-prior.x,
                                debt:accumulator,drawnCue,active:shooting,
                                vx:balls[0].vx};
                            const beforeRecovery=ticks,afterPauseX=balls[0].x;
                            t+=1000/60;frame(t);
                            const recovery={ticks:ticks-beforeRecovery,
                                travel:balls[0].x-afterPauseX,debt:accumulator,
                                active:shooting,drawnCue};
                            return {prior,pause,recovery};
                        }finally{
                            physics=op;render=orr;sound=os;settled=ost;drawBall=odb;
                            rack();last=0;accumulator=0;slowFrameStreak=0;
                        }
                    }""",{'gap':gap,'power':power,'warmup':warmup})
                    tag=f'{width}x{height} {gap}ms {power}% {warmup} prior frames'
                    prior,pause,recovery=result['prior'],result['pause'],result['recovery']
                    check(tag+' no suspended-time physics fast-forward',
                        pause['ticks']==0 and abs(pause['travel'])<1e-8,result)
                    check(tag+' no stale simulation debt after resume',
                        abs(pause['debt'])<1e-8 and pause['active'],result)
                    check(tag+' first resumed render stays at last real position',
                        pause['drawnCue'] is not None and
                        abs(pause['drawnCue']-prior['x'])<.02,result)
                    check(tag+' normal 60Hz movement resumes without burst',
                        1<=recovery['ticks']<=3 and
                        0<recovery['travel']<prior['vx']*2.0 and
                        recovery['debt']<1/120+1e-5 and recovery['active'],result)
                    check(tag+' selected power and impulse preserved',
                        prior['selected']==power and
                        abs(prior['impulse']-(.45+7.9*(power/100)**.92))<1e-7,result)
        # A NEW shot fired near the end of a long rAF silence must still
        # advance its own 28ms of legitimate post-input time (not freeze).
        for power in (25,75):
            data=page.evaluate("""power=>{
                const op=physics,orr=render,os=sound,ost=settled;
                let ticks=0;physics=(dt)=>{ticks++;op(dt)};
                render=()=>{};sound=()=>{};settled=()=>false;
                try{
                    rack();balls=[makeBall(0,400,285)];breakShot=false;
                    aim=0;showPower(power);shoot();
                    last=1000;accumulator=0;slowFrameStreak=0;
                    shotStartAt=1000+3000-28;shotFirstFramePending=true;
                    const start=balls[0].x;
                    frame(4000);
                    return {ticks,travel:balls[0].x-start,debt:accumulator,
                        active:shooting,impulse:shotSpeed(power,false)};
                }finally{
                    physics=op;render=orr;sound=os;settled=ost;
                    rack();last=0;accumulator=0;slowFrameStreak=0;
                }
            }""",power)
            check(f'{width}x{height} {power}% post-suspend new shot keeps 28ms physics',
                data['ticks']==3 and data['travel']>0 and
                data['debt']<1/120+1e-5 and data['active'],data)
        check(f'{width}x{height} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_RESUME_PAUSE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Synthetic Chromium frame timestamps; no physical Samsung or human acceptance.'
},indent=2))
print('RESUME PAUSE MOTION',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
