"""An isolated 180-240ms Android animation gap must not lurch a moving cue ball.

A normal 60Hz frame immediately before the hitch establishes that this is
not already sustained low-FPS play. Preserve genuine sustained 5-5.5fps
physics by deferring the first slow frame only until the next callback.
Synthetic Chromium timing, NOT physical Samsung/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name,ok,data):
    checks.append({'name':name,'passed':bool(ok),'details':data})
    if not ok:print('FAIL',name,json.dumps(data),flush=True)

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
        prefix=f'{width}x{height}'
        for gap in (180,200,220,240):
            for strength in (25,75):
                for warmup in (2,5):
                    data=page.evaluate("""({gap,strength,warmup})=>{
                      const op=physics,os=sound,ost=settled,odb=drawBall;
                      let ticks=0,drawnCue=null;
                      physics=dt=>{ticks++;op(dt)};
                      sound=()=>{};settled=()=>false;
                      drawBall=(b,q)=>{if(b.id===0)drawnCue=b.x};
                      try{
                        rack();balls=[makeBall(0,400,285)];breakShot=false;
                        aim=0;spin=0;follow=0;showPower(strength);shoot();
                        shotFirstFramePending=false;last=1000;
                        accumulator=0;slowFrameStreak=0;
                        let t=1000;
                        for(let i=0;i<warmup;i++){t+=1000/60;frame(t)}
                        const before={x:balls[0].x,vx:balls[0].vx,
                          power,impulse:shotSpeed(strength,false)};
                        const old=ticks;t+=gap;frame(t);
                        const paused={ticks:ticks-old,travel:balls[0].x-before.x,
                          debt:accumulator,drawnCue,vx:balls[0].vx};
                        const old2=ticks,x2=balls[0].x;
                        t+=1000/60;frame(t);
                        const resumed={ticks:ticks-old2,travel:balls[0].x-x2,
                          debt:accumulator,active:shooting};
                        return {before,paused,resumed};
                      }finally{
                        physics=op;sound=os;settled=ost;drawBall=odb;
                        rack();last=0;accumulator=0;slowFrameStreak=0;
                      }
                    }""",{'gap':gap,'strength':strength,'warmup':warmup})
                    tag=f'{prefix} {gap}ms {strength}% warmup={warmup}'
                    b,p,r=data['before'],data['paused'],data['resumed']
                    check(tag+' no fast-forward on isolated hitch',p['ticks']==0 and abs(p['travel'])<1e-8,data)
                    check(tag+' no hidden time debt',abs(p['debt'])<1e-8,data)
                    check(tag+' rendered cue does not jump',p['drawnCue'] is not None and abs(p['drawnCue']-b['x'])<.02,data)
                    check(tag+' impulse and selected power unchanged',b['power']==strength and
                        abs(p['vx']-b['vx'])<1e-8 and
                        abs(b['impulse']-(.45+7.9*(strength/100)**.92))<1e-8,data)
                    check(tag+' next 60Hz frame resumes naturally',r['active'] and
                        1<=r['ticks']<=3 and 0<r['travel']<b['vx']*2 and
                        0<=r['debt']<1/120+1e-5,data)
        for fps in (5,5.5):
            data=page.evaluate("""fps=>{
              const op=physics,os=sound,ost=settled,orr=render;
              let ticks=0;physics=dt=>{ticks++};sound=()=>{};
              settled=()=>false;render=()=>{};
              try{
                rack();balls=[makeBall(0,400,285)];breakShot=false;
                aim=0;showPower(75);shoot();
                shotFirstFramePending=false;last=1000;
                accumulator=0;slowFrameStreak=0;
                let t=1000;
                for(let i=0;i<5;i++){t+=1000/60;frame(t)}
                const startTicks=ticks,steps=[];
                for(let i=0;i<24;i++){
                  const old=ticks;t+=1000/fps;frame(t);
                  steps.push(ticks-old);
                }
                return {steps,simulated:ticks-startTicks,
                  expected:24*120/fps,debt:accumulator,active:shooting};
              }finally{
                physics=op;sound=os;settled=ost;render=orr;
                rack();last=0;accumulator=0;slowFrameStreak=0;
              }
            }""",fps)
            tag=f'{prefix} {fps}fps after normal frames'
            check(tag+' first isolated slow frame defers motion',data['steps'][0]==0,data)
            check(tag+' sustained callbacks catch up to real time',
                abs(data['simulated']-data['expected'])<=2,data)
            check(tag+' sustained work bounded and debt recovered',
                max(data['steps'])<=44 and data['active'] and
                0<=data['debt']<2/120,data)
        # An actual new shot fired 28ms before the returning callback must
        # receive the genuine 28ms of post-input physics, not be frozen.
        for gap in (180,200,220,240):
            for strength in (25,75):
                result=page.evaluate("""({gap,strength})=>{
                    const op=physics,os=sound,ost=settled,orr=render;
                    let ticks=0;
                    physics=dt=>{ticks++;op(dt)};
                    sound=()=>{};settled=()=>false;render=()=>{};
                    try{
                        rack();balls=[makeBall(0,400,285)];breakShot=false;
                        aim=0;spin=0;follow=0;showPower(strength);shoot();
                        last=1000;accumulator=0;slowFrameStreak=0;
                        recentNormalFrame=true;
                        shotStartAt=1000+gap-28;shotFirstFramePending=true;
                        const x=balls[0].x;
                        frame(1000+gap);
                        return {ticks,travel:balls[0].x-x,debt:accumulator,
                            active:shooting,power,impulse:shotSpeed(strength,false)};
                    }finally{
                        physics=op;sound=os;settled=ost;render=orr;
                        rack();last=0;accumulator=0;slowFrameStreak=0;
                    }
                }""",{'gap':gap,'strength':strength})
                tag=f'{prefix} {gap}ms newly fired {strength}%'
                check(tag+' preserves genuine post-input motion',
                    result['ticks']==3 and result['travel']>0 and
                    result['active'] and result['debt']<1/120+1e-5,result)
                check(tag+' keeps original impulse and selection',
                    result['power']==strength and
                    abs(result['impulse']-(.45+7.9*(strength/100)**.92))<1e-8,result)
        check(prefix+' no browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SHORT_GAP_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Chromium synthetic frames only. Physical Samsung Galaxy A37 and human acceptance remain release-blocking.'
},indent=2))
print('180-240MS MOBILE GAP',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
