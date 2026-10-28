"""An isolated Android-style 180-340ms animation interruption followed by one
85-175ms callback must not create a multi-tick visual burst on the next
ordinary 60Hz callback. Two genuinely slow follow-up callbacks must still
enable sustained low-FPS catch-up. Synthetic Chromium timing, not Samsung
physical FPS, responsiveness or independent human release acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

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
        for gap in (180,220,280,340):
            for tail in (85,110,145,175):
                for strength in (25,75):
                    result=page.evaluate("""({gap,tail,strength})=>{
                      const oldPhysics=physics,oldSound=sound,oldSettled=settled;
                      let ticks=0;
                      physics=dt=>{ticks++;oldPhysics(dt)};
                      sound=()=>{};settled=()=>false;
                      try{
                        rack();balls=[makeBall(0,400,285)];breakShot=false;
                        aim=0;spin=0;follow=0;showPower(strength);shoot();
                        shotFirstFramePending=false;last=1000;accumulator=0;
                        slowFrameStreak=0;recentNormalFrame=false;deferredSlowGap=0;
                        let t=1000;
                        for(let i=0;i<5;i++){t+=1000/60;frame(t)}
                        const initial={power,vx:balls[0].vx,impulse:shotSpeed(strength,false)};
                        const beforePause=ticks;t+=gap;frame(t);
                        const pause={ticks:ticks-beforePause,debt:accumulator};
                        const beforeTail=ticks,tailX=balls[0].x;
                        t+=tail;frame(t);
                        const tailFrame={ticks:ticks-beforeTail,
                          travel:balls[0].x-tailX,debt:accumulator};
                        const beforeNormal=ticks,normalX=balls[0].x;
                        t+=1000/60;frame(t);
                        const normal={ticks:ticks-beforeNormal,
                          travel:balls[0].x-normalX,debt:accumulator,
                          active:shooting,finite:balls.every(b=>
                            [b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                        // Repeat the same pause and tail, but follow with a
                        // second genuinely slow callback. It must retain the
                        // sustained-low-FPS recovery path, not discard debt.
                        rack();balls=[makeBall(0,400,285)];breakShot=false;
                        aim=0;spin=0;follow=0;showPower(strength);shoot();
                        shotFirstFramePending=false;last=1000;accumulator=0;
                        slowFrameStreak=0;recentNormalFrame=false;deferredSlowGap=0;
                        t=1000;
                        for(let i=0;i<5;i++){t+=1000/60;frame(t)}
                        t+=gap;frame(t);t+=tail;frame(t);
                        const beforeSustained=ticks;
                        t+=tail;frame(t);
                        const sustained={ticks:ticks-beforeSustained,
                          active:shooting,finite:balls.every(b=>
                            [b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                        return {initial,pause,tailFrame,normal,sustained};
                      }finally{
                        physics=oldPhysics;sound=oldSound;settled=oldSettled;
                        rack();last=0;accumulator=0;slowFrameStreak=0;
                        recentNormalFrame=false;deferredSlowGap=0;
                      }
                    }""",{'gap':gap,'tail':tail,'strength':strength})
                    tag=f'{width}x{height} {gap}ms pause + {tail}ms tail {strength}%'
                    i=result['initial'];p=result['pause']
                    r=result['tailFrame'];n=result['normal'];s=result['sustained']
                    check(tag+' frozen interruption does not move physics',
                        p['ticks']==0 and abs(p['debt'])<1e-9,result)
                    check(tag+' slower callback has bounded movement',
                        1<=r['ticks']<=8 and
                        0<r['travel']<i['vx']*4.1,result)
                    check(tag+' returning 60Hz frame does not fast-forward',
                        1<=n['ticks']<=3 and
                        0<n['travel']<i['vx']*1.7,result)
                    check(tag+' interrupted pause carries no next-frame debt',
                        0<=n['debt']<.009 and n['active'] and n['finite'],result)
                    check(tag+' genuine sustained low FPS still catches up',
                        s['active'] and s['finite'] and s['ticks']>=9
                        and i['power']==strength and
                        abs(i['impulse']-page.evaluate('(v)=>shotSpeed(v,false)',strength))<1e-9,result)
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_HITCH_TAIL_RECOVERY_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium synthetic rAF; physical Samsung A37 and human acceptance required.'},indent=2))
print('HITCH TAIL RECOVERY SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
