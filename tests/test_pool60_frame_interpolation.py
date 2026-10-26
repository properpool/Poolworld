"""Moving-ball visual pacing at 60/90/144 Hz.

A fixed 120 Hz physics step produces 1/2-tick alternating displacements at
90 Hz and 0/1-tick displacements at 144 Hz if canvas draws raw physics state.
Test actual coordinates passed to drawBall during frame() without touching
physical ball positions. This is synthetic Chromium timing, NOT real Samsung FPS.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, statistics, sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,ok,details):
    checks.append({'name':label,'passed':bool(ok),'details':details})
    if not ok:print('FAIL',label,details,flush=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for hz in (60,90,144):
            data=page.evaluate("""hz=>{
              rack();
              balls=[makeBall(0,400,285)];
              aim=0;breakShot=false;showPower(65);
              shooting=false;gameOver=false;ballInHand=false;
              const positions=[];
              const originalDraw=drawBall;
              drawBall=function(b){if(b.id===0)positions.push(b.x);return originalDraw(b)};
              shoot();last=0;accumulator=0;
              const states=[];
              for(let i=1;i<=72;i++){
                frame(1000+i*1000/hz);
                states.push(balls[0].x);
              }
              drawBall=originalDraw;
              return {positions,states,shooting,remaining:accumulator};
            }""",hz)
            label=f'{w}x{h} {hz}Hz'
            pos=data['positions']
            delta=[pos[i]-pos[i-1] for i in range(7,min(len(pos),64))]
            mean=statistics.mean(delta) if delta else 0
            max_jitter=max((abs(d-mean)/mean for d in delta),default=99) if mean>0 else 99
            check(label+' renders each active frame',len(pos)==72,
                  {'draws':len(pos)})
            check(label+' visual movement is smooth across variable physics ticks',
                  mean>.15 and max_jitter<.23,
                  {'meanDelta':round(mean,4),'maxRelativeJitter':round(max_jitter,4),
                   'firstDeltas':[round(x,3) for x in delta[:12]]})
            state=data['states']
            check(label+' rendering does not alter authoritative physics',
                  all(math.isfinite(x) for x in state)
                  and all(state[i]>=state[i-1]-1e-6 for i in range(1,len(state)))
                  and all(pos[i]<=state[i]+1e-5 for i in range(len(pos)))
                  and max((state[i]-pos[i] for i in range(len(pos))),default=0)<6,
                  {'lastPhysics':state[-1],'lastDraw':pos[-1]})
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_FRAME_INTERPOLATION_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Synthetic 60/90/144 Hz frame timestamps in Chromium; no physical Samsung frame pacing or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
