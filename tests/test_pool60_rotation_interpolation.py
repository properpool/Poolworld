"""Verify visible ball rotation is interpolated alongside position.

Synthetic Chromium 60/90/144Hz timestamps: this does NOT measure physical
Samsung frame pacing, touch latency, or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, statistics, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, ok, detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:
        print('FAIL',name,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for hz in (60,90,144):
            data=page.evaluate("""hz=>{
                rack();
                balls=[makeBall(0,400,285)];
                aim=0;breakShot=false;showPower(55);
                shooting=false;gameOver=false;ballInHand=false;
                const drawn=[],authoritative=[];
                let capture=false,changedByRender=0;
                const originalMarker=rollMarker,originalRender=render;
                rollMarker=function(q,p){
                    if(capture){drawn.push(q.slice());capture=false}
                    return originalMarker(q,p);
                };
                render=function(){
                    const before=balls[0].rollQ.slice();
                    originalRender();
                    if(before.some((v,i)=>Math.abs(v-balls[0].rollQ[i])>1e-12))
                        changedByRender++;
                };
                shoot();last=0;accumulator=0;
                for(let i=1;i<=72;i++){
                    capture=true;
                    frame(1000+i*1000/hz);
                    authoritative.push(balls[0].rollQ.slice());
                }
                rollMarker=originalMarker;render=originalRender;
                return {drawn,authoritative,changedByRender};
            }""",hz)
            tag=f'{width}x{height} {hz}Hz'
            drawn=data['drawn'];actual=data['authoritative']
            delta=[]
            for i in range(7,min(len(drawn),64)):
                a,b=drawn[i-1],drawn[i]
                dot=abs(sum(x*y for x,y in zip(a,b)))
                delta.append(2*math.acos(min(1,max(-1,dot))))
            mean=statistics.mean(delta) if delta else 0
            jitter=max((abs(x-mean)/mean for x in delta),default=99) if mean>0 else 99
            check(tag+' visible cue-ball orientation sampled every frame',
                len(drawn)==72,{'draws':len(drawn)})
            check(tag+' rotating measle dots have smooth angular steps',
                mean>.007 and jitter<.26,
                {'meanAngularStep':round(mean,5),'maxRelativeJitter':round(jitter,4),
                 'firstSteps':[round(x,4) for x in delta[:12]]})
            check(tag+' rendered orientation stays normalized',
                len(drawn)==72 and all(abs(math.hypot(*q)-1)<1e-6 for q in drawn),
                {'maxNormError':max((abs(math.hypot(*q)-1) for q in drawn),default=99)})
            check(tag+' interpolation never changes authoritative orientation',
                data['changedByRender']==0 and len(actual)==72
                and all(abs(math.hypot(*q)-1)<1e-6 for q in actual),
                {'renderMutations':data['changedByRender']})
        # With physics completely stopped between these two renders, only
        # interpolation can rotate the visible marker.
        paused=page.evaluate("""()=>{
            rack();balls=[makeBall(0,400,285)];
            balls[0].vx=8;shooting=true;shot=null;
            physics(STEP);
            const original=rollMarker, captured=[];
            let capture=false;
            rollMarker=function(q,p){
                if(capture){captured.push(q.slice());capture=false}
                return original(q,p);
            };
            const state=balls[0].rollQ.slice();
            interpolateVisual=true;
            accumulator=STEP*.25;capture=true;render();
            accumulator=STEP*.75;capture=true;render();
            interpolateVisual=false;rollMarker=original;
            const unchanged=state.every((v,i)=>Math.abs(v-balls[0].rollQ[i])<1e-12);
            return {captured,unchanged};
        }""")
        q=paused['captured']
        angular=0
        if len(q)==2:
            angular=2*math.acos(min(1,abs(sum(a*b for a,b in zip(q[0],q[1])))))
        check(f'{width}x{height} fractional frame advances visual rotation without physics',
            len(q)==2 and angular>.008 and paused['unchanged'],
            {'angleDifference':round(angular,6),'physicsUnchanged':paused['unchanged']})
        check(f'{width}x{height} browser errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_ROTATION_INTERPOLATION_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Synthetic Chromium frames, not Samsung FPS or physical-device acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
