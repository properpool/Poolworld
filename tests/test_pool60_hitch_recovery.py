"""Pool World v9.7 transient frame-hitch physics debt and bounded catch-up.

A 150ms browser frame gap must not silently discard ~67ms of shot motion.
Catch-up is bounded per callback so a transient hitch does not create a
single unbounded physics burst. Synthetic timestamps are NOT Samsung FPS.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,detail,flush=True)

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
        label=f'{w}x{h}'
        data=page.evaluate("""() => {
          let ticks=0;
          const oldPhysics=physics;
          physics=function(dt){ticks++;return oldPhysics(dt)};
          const start=()=>{
            rack();showPower(100);aim=0;
            if(!shoot())throw Error('break shot did not start');
            last=1000;accumulator=0;ticks=0;
          };
          start();
          const gaps=[1000/60,150,1000/60,1000/60,1000/60,1000/60];
          let stamp=1000;
          const perFrame=[];
          for(const gap of gaps){
            stamp+=gap;const before=ticks;frame(stamp);
            perFrame.push(ticks-before);
          }
          const hitch={gaps,perFrame,ticks,accumulator,
            wallSeconds:gaps.reduce((a,b)=>a+b,0)/1000,
            moving:shooting,finite:balls.every(b=>
              [b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
          // A resumed idle page must not bank unused physics time and
          // fast-forward the next shot when the user presses SHOOT.
          rack();last=1000;accumulator=0;
          frame(1250);
          const idleDebt=accumulator;
          showPower(100);aim=0;shoot();ticks=0;
          frame(1250+1000/60);
          const idle={debt:idleDebt,firstShotTicks:ticks,
            finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
          const normal={};
          for(const hz of [60,90,144]){
            start();stamp=1000;
            const frameSteps=[];
            for(let i=0;i<72;i++){
              stamp+=1000/hz;const before=ticks;frame(stamp);
              frameSteps.push(ticks-before);
            }
            normal[hz]={ticks,expected:120*72/hz,
              maxSteps:Math.max(...frameSteps),
              accumulator,finite:balls.every(b=>
                [b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
          }
          return {hitch,idle,normal};
        }""")
        hitch=data['hitch'];counts=hitch['perFrame']
        check(label+' hitch break shot remains active and finite',
            hitch['moving'] and hitch['finite'],hitch)
        check(label+' 150ms hitch preserves elapsed physics time',
            abs(hitch['ticks']/120-hitch['wallSeconds'])<1.5/120,hitch)
        check(label+' physics work capped at eight ticks per animation callback',
            max(counts)<=8,hitch)
        check(label+' hitch does not require an unbounded single-frame burst',
            counts[1]<=8 and counts[1]>=6,hitch)
        check(label+' physics catches up across subsequent callbacks',
            sum(counts[2:])>=14 and hitch['accumulator']<1/120+1e-5,hitch)
        idle=data['idle']
        check(label+' idle tab resume never banks stale physics debt',
            idle['debt']<1/120+1e-5,idle)
        check(label+' first shot after idle pause is not fast-forwarded',
            idle['firstShotTicks']<=3 and idle['finite'],idle)
        for hz in (60,90,144):
            normal=data['normal'][hz]
            check(label+f' {hz}Hz normal cadence retains 120Hz physics',
                abs(normal['ticks']-normal['expected'])<=1.5,normal)
            check(label+f' {hz}Hz normal frames avoid catch-up bursts',
                normal['maxSteps']<=3 and normal['finite'],normal)
        check(label+' no browser JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_HITCH_RECOVERY_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Synthetic Chromium rAF timestamps; not physical Samsung frame pacing or acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
