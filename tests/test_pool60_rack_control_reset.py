"""New rack must not inherit weak power or unwanted English from the previous game.

A 5% finesse shot followed by NEW RACK currently leaves the next break at 5%,
and prior side/follow settings also persist. Test the real controls and physical
break impulse in Chromium; Samsung Galaxy A37/human acceptance remains blocking.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,data):
    checks.append({'name':name,'passed':bool(ok),'data':data})
    if not ok: print('FAIL',name,json.dumps(data),flush=True)

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
        for strength,english,draw in ((5,85,-90),(100,-80,95),(75,50,70)):
            for mode in ('new-rack-button','eight-on-break-rerack'):
                data=page.evaluate("""({strength,english,draw,mode})=>{
                    rack();showPower(strength);
                    spin=english;follow=draw;
                    document.getElementById('spin').value=spin;
                    document.getElementById('follow').value=follow;
                    if(mode==='new-rack-button'){
                        document.getElementById('reset').click();
                    }else{
                        const fired=shoot();
                        if(!fired)throw Error('break shot failed');
                        shot.pocketed=[8];
                        resolveShot();
                    }
                    const state={
                        power,spin,follow,
                        strengthValue:Number(document.getElementById('strength').value),
                        spinValue:Number(document.getElementById('spin').value),
                        followValue:Number(document.getElementById('follow').value),
                        powerText:document.getElementById('powerValue').textContent,
                        breakShot,shooting,ballInHand,gameOver,turn,ballCount:balls.length
                    };
                    const fired=shoot();
                    state.fired=fired;
                    state.impulse=Math.hypot(balls[0].vx,balls[0].vy);
                    state.expectedImpulse=shotSpeed(45,true);
                    state.actualSpin=balls[0].spin;
                    state.actualFollow=balls[0].follow;
                    rack();
                    return state;
                }""",{'strength':strength,'english':english,'draw':draw,'mode':mode})
                tag=f'{width}x{height} {mode} previous {strength}% spin {english} follow {draw}'
                check(tag+' starts a fresh default 45% break',
                      data['power']==45 and data['strengthValue']==45 and
                      data['powerText']=='45%',data)
                check(tag+' clears old side-spin and follow controls',
                      data['spin']==0 and data['follow']==0 and
                      data['spinValue']==0 and data['followValue']==0,data)
                check(tag+' resets full-match break state',
                      data['breakShot'] and not data['shooting'] and
                      not data['ballInHand'] and not data['gameOver'] and
                      data['turn']==1 and data['ballCount']==16,data)
                check(tag+' applies default calibrated break impulse',
                      data['fired'] and
                      abs(data['impulse']-data['expectedImpulse'])<1e-7,data)
                check(tag+' break contains no inherited spin or follow',
                      abs(data['actualSpin'])<1e-8 and
                      abs(data['actualFollow'])<1e-8,data)
        check(f'{width}x{height} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_RACK_CONTROL_RESET_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium browser checks only; physical Samsung and independent human acceptance release-blocking.'},indent=2))
print('RACK CONTROL RESET',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
