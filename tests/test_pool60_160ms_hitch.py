"""A single 160-175ms Android animation callback after smooth 60Hz play
must not throw the cue ball forward and then repay stale debt in normal frames.
Sustained 6fps after smooth play must still retain wall-time shot progression.
Synthetic Chromium timing only; NOT physical Samsung A37 acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

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
        for gap in (160,165,170,175):
            for strength in (25,75):
                result=page.evaluate("""({gap,strength})=>{
                  const originalPhysics=physics,originalSettled=settled,originalSound=sound;
                  let ticks=0;
                  physics=dt=>{ticks++;originalPhysics(dt)};
                  settled=()=>false;sound=()=>{};
                  const init=()=>{
                    rack();balls=[makeBall(0,400,285)];breakShot=false;
                    aim=0;spin=0;follow=0;showPower(strength);shoot();
                    shotFirstFramePending=false;last=1000;accumulator=0;
                    slowFrameStreak=0;recentNormalFrame=false;
                    deferredSlowGap=0;postHitchTail=false;ticks=0;
                    let t=1000;
                    for(let i=0;i<5;i++){t+=1000/60;frame(t)}
                    return t;
                  };
                  try{
                    let t=init();
                    const selected={power,impulse:shotSpeed(strength,false)};
                    const before=ticks,x=balls[0].x;
                    t+=gap;frame(t);
                    const paused={ticks:ticks-before,travel:balls[0].x-x,
                      debt:accumulator};
                    const afterPause=ticks,afterX=balls[0].x;
                    t+=1000/60;frame(t);
                    const resumed={ticks:ticks-afterPause,
                      travel:balls[0].x-afterX,debt:accumulator};
                    const normal=[];
                    for(let i=0;i<4;i++){
                      const prior=ticks,oldX=balls[0].x;
                      t+=1000/60;frame(t);
                      normal.push({ticks:ticks-prior,travel:balls[0].x-oldX});
                    }
                    t=init();const slowCounts=[],firstX=balls[0].x;
                    const startTicks=ticks;
                    for(let i=0;i<24;i++){
                      const prior=ticks;
                      t+=1000/6;frame(t);
                      slowCounts.push(ticks-prior);
                    }
                    const sustained={ticks:ticks-startTicks,
                      expected:24*120/6,maxTicks:Math.max(...slowCounts),
                      firstTicks:slowCounts[0],secondTicks:slowCounts[1],
                      debt:accumulator,travel:balls[0].x-firstX,
                      active:shooting,finite:balls.every(b=>
                        [b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                    return {selected,paused,resumed,normal,sustained};
                  }finally{
                    physics=originalPhysics;settled=originalSettled;sound=originalSound;
                    rack();last=0;accumulator=0;recentNormalFrame=false;
                    deferredSlowGap=0;postHitchTail=false;
                  }
                }""",{'gap':gap,'strength':strength})
                tag=f'{width}x{height} {gap}ms at {strength}%'
                p=result['paused'];r=result['resumed'];s=result['sustained']
                check(tag+' isolated pause freezes without jumping',
                    p['ticks']==0 and abs(p['travel'])<1e-8 and abs(p['debt'])<1e-8,result)
                check(tag+' returning 60Hz callback moves smoothly',
                    1<=r['ticks']<=3 and r['travel']>0 and r['debt']<.009,result)
                check(tag+' subsequent 60Hz callbacks do not burst',
                    all(1<=n['ticks']<=3 for n in result['normal']),result)
                check(tag+' sustained 6fps catches up without a 40-tick leap',
                    s['firstTicks']==0 and s['secondTicks']<=22 and
                    abs(s['ticks']-s['expected'])<=4 and
                    s['maxTicks']<=22 and s['debt']<.05,result)
                check(tag+' calibrated impulse and valid physics preserved',
                    result['selected']['power']==strength and
                    abs(result['selected']['impulse']-page.evaluate(
                      '(p)=>shotSpeed(p,false)',strength))<1e-9 and
                    s['active'] and s['finite'],result)
        check(f'{width}x{height} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_160MS_HITCH_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium synthetic animation timing only. Independent physical Samsung and human acceptance remain release-blocking.'},indent=2))
print('160MS HITCH SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
