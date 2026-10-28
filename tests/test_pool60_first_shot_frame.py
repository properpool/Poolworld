"""Prevent pre-shot animation-frame time from advancing a newly fired ball.

An input event may arrive near the end of a 120-320ms rAF gap. Only time
AFTER SHOOT belongs to the new shot. Otherwise the first frame advances up
to eight stale ticks, creating a visibly jerky first-ball jump. Chromium
synthetic timestamps only; physical Samsung and human acceptance are required.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,details):
    checks.append({'name':name,'passed':bool(passed),'details':details})
    if not passed: print('FAIL',name,json.dumps(details),flush=True)

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
        for gap in (120,180,240,320):
            for power in (25,75):
                data=page.evaluate("""({gap,power})=>{
                    const oldPhysics=physics,oldRender=render,oldSound=sound;
                    let ticks=0;
                    render=()=>{};sound=()=>{};
                    try{
                        rack();balls=[makeBall(0,320,285)];
                        breakShot=false;aim=0;spin=0;follow=0;
                        gameOver=false;ballInHand=false;showPower(power);
                        physics=(dt)=>{ticks++;oldPhysics(dt)};
                        const fired=shoot(),impulse=Math.hypot(balls[0].vx,balls[0].vy);
                        const startX=balls[0].x;
                        // Last rAF at 1000ms, but the user's SHOOT event
                        // happened only 28ms before the next callback.
                        last=1000;accumulator=0;slowFrameStreak=0;
                        shotStartAt=1000+gap-28;
                        shotFirstFramePending=true;
                        frame(1000+gap);
                        const firstTicks=ticks,firstX=balls[0].x;
                        const firstDebt=accumulator;
                        const liveBalls=balls;
                        balls=[makeBall(0,startX,285)];
                        balls[0].vx=impulse;
                        for(let i=0;i<3;i++)oldPhysics(STEP);
                        const referenceX=balls[0].x;
                        balls=liveBalls;
                        const beforeNext=ticks;
                        frame(1000+gap+1000/60);
                        return {fired,impulse,expected:shotSpeed(power,false),
                            firstTicks,firstTravel:firstX-startX,
                            expectedTravel:referenceX-startX,
                            firstError:Math.abs(firstX-referenceX),
                            firstDebt,nextTicks:ticks-beforeNext,
                            nextTravel:balls[0].x-firstX,shooting};
                    }finally{
                        physics=oldPhysics;render=oldRender;sound=oldSound;
                        rack();last=0;accumulator=0;slowFrameStreak=0;
                    }
                }""",{'gap':gap,'power':power})
                tag=f'{width}x{height} {gap}ms {power}%'
                check(tag+' retains calibrated shot impulse',
                    data['fired'] and abs(data['impulse']-data['expected'])<1e-7,data)
                check(tag+' first frame advances only three post-input ticks',
                    data['firstTicks']==3,data)
                check(tag+' first-ball displacement matches 28ms shot time',
                    data['firstError']<.02 and data['firstTravel']>0,data)
                check(tag+' no pre-shot physics debt reaches following frame',
                    data['firstDebt']<1/120+1e-6 and
                    1<=data['nextTicks']<=3 and data['nextTravel']>0 and
                    data['shooting'],data)
        check(f'{width}x{height} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_FIRST_SHOT_FRAME_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Synthetic Chromium timestamps only. Samsung A37 physical and human acceptance release-blocking.'},indent=2))
print('FIRST SHOT FRAME',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
