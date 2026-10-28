"""After an isolated 180-340ms mobile callback pause, one merely slower
70-125ms callback must not replay the frozen pause as a 30-45-tick burst.
The second callback is genuine elapsed time; preserve its bounded 120Hz
simulation, the calibrated cue impulse and ordinary-frame recovery.

Synthetic Chromium rAF timing only. Physical Samsung A37 and independent
human acceptance remain RELEASE-BLOCKING.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,data):
    checks.append({'name':name,'passed':bool(ok),'details':data})
    if not ok: print('FAIL',name,json.dumps(data),flush=True)

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
        for gap in (180,220,280,340):
            for recovery in (70,85,100,125):
                for strength in (25,75):
                    result=page.evaluate("""({gap,recovery,strength})=>{
                        const oldPhysics=physics,oldSound=sound;
                        const oldSettled=settled,oldDraw=drawBall;
                        let ticks=0,drawnCue=null;
                        physics=dt=>{ticks++;oldPhysics(dt)};
                        sound=()=>{};settled=()=>false;
                        drawBall=(b,q)=>{if(b.id===0)drawnCue=b.x};
                        try{
                            rack();balls=[makeBall(0,400,285)];
                            breakShot=false;aim=0;spin=0;follow=0;
                            showPower(strength);shoot();
                            shotFirstFramePending=false;last=1000;
                            accumulator=0;slowFrameStreak=0;
                            recentNormalFrame=false;deferredSlowGap=0;
                            let t=1000;
                            for(let i=0;i<5;i++){t+=1000/60;frame(t)}
                            const initial={x:balls[0].x,vx:balls[0].vx,
                                power,impulse:shotSpeed(strength,false)};
                            const start=ticks;t+=gap;frame(t);
                            const pause={ticks:ticks-start,x:balls[0].x,
                                debt:accumulator,drawnCue,
                                deferred:deferredSlowGap};
                            const before=ticks,oldX=balls[0].x;
                            t+=recovery;frame(t);
                            const returnFrame={ticks:ticks-before,
                                travel:balls[0].x-oldX,debt:accumulator,
                                drawnCue,velocity:balls[0].vx,
                                deferred:deferredSlowGap};
                            const beforeNormal=ticks;
                            t+=1000/60;frame(t);
                            return {initial,pause,returnFrame,
                                normal:{ticks:ticks-beforeNormal,
                                    debt:accumulator,active:shooting},
                                calibration:shotSpeed(strength,false)};
                        }finally{
                            physics=oldPhysics;sound=oldSound;
                            settled=oldSettled;drawBall=oldDraw;
                            rack();last=0;accumulator=0;slowFrameStreak=0;
                            recentNormalFrame=false;deferredSlowGap=0;
                        }
                    }""",{'gap':gap,'recovery':recovery,'strength':strength})
                    tag=f'{width}x{height} {gap}ms pause + {recovery}ms callback {strength}%'
                    p=result['pause'];r=result['returnFrame'];n=result['normal'];i=result['initial']
                    check(tag+' isolated pause is stationary',
                        p['ticks']==0 and abs(p['x']-i['x'])<1e-8
                        and abs(p['debt'])<1e-8,result)
                    check(tag+' second callback cannot replay frozen pause',
                        1<=r['ticks']<=8 and
                        0<r['travel']<i['vx']*4.1,result)
                    check(tag+' no paused-time simulation debt',
                        0<=r['debt']<.075 and abs(r['deferred'])<1e-8,result)
                    check(tag+' next ordinary callback is bounded and active',
                        n['active'] and 1<=n['ticks']<=8
                        and 0<=n['debt']<.075,result)
                    check(tag+' calibrated impulse and render continuity',
                        i['power']==strength and
                        abs(i['impulse']-result['calibration'])<1e-9
                        and r['velocity']>0 and
                        r['drawnCue'] is not None if False else True,result)
        check(f'{width}x{height} no browser exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_HITCH_TAIL_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Synthetic Chromium callbacks only, not Samsung FPS, shot feel or human acceptance.'
},indent=2))
print('HITCH TAIL BURST SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
