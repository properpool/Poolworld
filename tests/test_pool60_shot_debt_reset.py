"""A completed shot must not carry slow-frame physics debt into the next shot.

Synthetic Chromium timestamps; NOT physical Samsung A37 frame-rate or human
shot-feel acceptance. Regression targets a visible next-shot fast-forward.
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
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        label=f'{width}x{height}'
        for gap in (120,180,240,320):
            for power in (25,75):
                data=page.evaluate("""({gap,power})=>{
                    const oldPhysics=physics,oldSettled=settled,
                          oldRender=render,oldSound=sound;
                    let ticks=0;
                    render=()=>{};sound=()=>{};
                    try{
                        rack();breakShot=false;aim=0;spin=0;follow=0;
                        showPower(power);
                        document.getElementById('shoot').click();
                        if(!shooting||!shot)throw Error('initial shot did not start');
                        shot.firstHit=1;shot.railAfterContact=true;
                        // A shot can settle on a throttled callback with >8
                        // pending ticks. Its remaining debt belongs ONLY to
                        // the shot that just finished.
                        physics=()=>{ticks++};settled=()=>true;
                        last=1000;accumulator=0;slowFrameStreak=0;
                        frame(1000+gap);
                        const afterSettlement={ticks,debt:accumulator,
                          shooting,ballInHand,turn,shotExists:shot!==null};
                        physics=oldPhysics;settled=()=>false;
                        document.getElementById('shoot').click();
                        const started=shooting&&shot!==null;
                        const impulse=Math.hypot(balls[0].vx,balls[0].vy);
                        const beforeX=balls[0].x;
                        const referenceBalls=balls.map(b=>({
                          ...b,rollQ:[...b.rollQ]}));
                        physics=(dt)=>{ticks++;oldPhysics(dt)};
                        const beforeTicks=ticks;
                        frame(1000+gap+1000/60);
                        const firstTicks=ticks-beforeTicks;
                        const actualX=balls[0].x;
                        balls=referenceBalls;
                        oldPhysics(STEP);oldPhysics(STEP);
                        const referenceX=balls[0].x;
                        return {afterSettlement,started,impulse,
                          expectedImpulse:shotSpeed(power,false),
                          firstTicks,actualX,referenceX,beforeX,
                          displacementError:Math.abs(actualX-referenceX)};
                    }finally{
                        physics=oldPhysics;settled=oldSettled;
                        render=oldRender;sound=oldSound;
                        rack();accumulator=0;slowFrameStreak=0;
                    }
                }""",{'gap':gap,'power':power})
                tag=f'{label} {gap}ms {power}%'
                check(tag+' settled shot retires old physics debt',
                      not data['afterSettlement']['shooting'] and
                      not data['afterSettlement']['shotExists'] and
                      data['afterSettlement']['debt']<1/120+1e-6,data)
                check(tag+' next shot starts at calibrated power',
                      data['started'] and
                      abs(data['impulse']-data['expectedImpulse'])<1e-7,data)
                check(tag+' next 60Hz frame runs at most three ticks',
                      1<=data['firstTicks']<=3,data)
                check(tag+' next shot travel matches two 120Hz steps',
                      data['displacementError']<.2,data)
        check(label+' no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_SHOT_DEBT_RESET_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium synthetic rAF; physical Samsung and human acceptance remain release-blocking.'},indent=2))
print('SHOT DEBT RESET',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
