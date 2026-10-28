"""Regression: a single 460-580ms phone animation interruption must not fast-forward a moving shot.

A short OS/browser scheduling pause after normal 60Hz motion is not sustained
low-FPS play. The returning callback must retain the cue-ball pose and velocity,
clear stale physics debt, and resume on the next ordinary frame. Conversely,
a NEW shot fired 28ms before the callback must receive its legitimate ticks.
Synthetic Chromium only; Samsung A37 physical/human acceptance remains blocked.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name,passed,details):
    checks.append({'name':name,'passed':bool(passed),'details':details})
    if not passed:
        print('FAIL',name,json.dumps(details),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for gap in (460,520,580):
            for power in (25,75):
                for warmup in (1,8):
                    result=page.evaluate("""({gap,power,warmup})=>{
                        const originalPhysics=physics,originalSound=sound;
                        const originalSettled=settled,originalDrawBall=drawBall;
                        let ticks=0,drawnCue=null;
                        physics=(dt)=>{ticks++;originalPhysics(dt)};
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
                            const after=ticks,x=balls[0].x;
                            t+=1000/60;frame(t);
                            const recovery={ticks:ticks-after,travel:balls[0].x-x,
                                debt:accumulator,active:shooting};
                            return {prior,pause,recovery};
                        }finally{
                            physics=originalPhysics;sound=originalSound;
                            settled=originalSettled;drawBall=originalDrawBall;
                            rack();last=0;accumulator=0;slowFrameStreak=0;
                        }
                    }""",{'gap':gap,'power':power,'warmup':warmup})
                    prior,pause,recovery=result['prior'],result['pause'],result['recovery']
                    tag=f'{width}x{height} {gap}ms {power}% {warmup} warmup'
                    check(tag+' pause does not advance physics',pause['ticks']==0,result)
                    check(tag+' cue remains at last genuine position',
                        abs(pause['travel'])<1e-8,result)
                    check(tag+' no stale physics debt',abs(pause['debt'])<1e-8,result)
                    check(tag+' returning render stays at last cue position',
                        pause['drawnCue'] is not None and
                        abs(pause['drawnCue']-prior['x'])<.02,result)
                    check(tag+' normal next-frame motion and calibrated impulse',
                        pause['active'] and recovery['active'] and
                        1<=recovery['ticks']<=3 and
                        0<recovery['travel']<prior['vx']*2 and
                        recovery['debt']<1/120+1e-5 and
                        abs(pause['vx']-prior['vx'])<1e-8 and
                        prior['selected']==power and prior['impulse']>0,result)
            for power in (25,75):
                result=page.evaluate("""({gap,power})=>{
                    const op=physics,os=sound,ost=settled,orr=render;
                    let ticks=0;physics=(dt)=>{ticks++;op(dt)};
                    sound=()=>{};settled=()=>false;render=()=>{};
                    try{
                        rack();balls=[makeBall(0,400,285)];
                        breakShot=false;aim=0;showPower(power);shoot();
                        last=1000;accumulator=0;slowFrameStreak=0;
                        shotStartAt=1000+gap-28;shotFirstFramePending=true;
                        const x=balls[0].x;
                        frame(1000+gap);
                        return {ticks,travel:balls[0].x-x,debt:accumulator,
                            active:shooting,impulse:shotSpeed(power,false)};
                    }finally{
                        physics=op;sound=os;settled=ost;render=orr;
                        rack();last=0;accumulator=0;slowFrameStreak=0;
                    }
                }""",{'gap':gap,'power':power})
                tag=f'{width}x{height} {gap}ms new {power}% shot'
                check(tag+' genuine 28ms post-input time retained',
                    result['ticks']==3 and result['travel']>0 and
                    result['debt']<1/120+1e-5 and result['active'],result)
                check(tag+' original shot-speed calibration preserved',
                    result['impulse']>0 and
                    abs(result['impulse']-(.45+7.9*(power/100)**.92))<1e-7,
                    result)
        check(f'{width}x{height} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_MIDRANGE_PAUSE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Synthetic Chromium frames only; physical Samsung/human acceptance blocked.'
},indent=2))
print('MIDRANGE PHONE PAUSE',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
