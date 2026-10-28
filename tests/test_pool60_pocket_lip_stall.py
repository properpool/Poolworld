"""Slow near-miss shots must not strand balls outside the playing cloth at a
side-pocket mouth. Chromium deterministic 120Hz physics; not physical Samsung
Galaxy A37 FPS, visual smoothness, shot feel or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,ok,data):
    checks.append({'name':label,'passed':bool(ok),'detail':data})
    if not ok:print('FAIL',label,json.dumps(data),flush=True)

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
        for edge in ('top','bottom'):
            for side in (-1,1):
                for speed in (.14,.22):
                    data=page.evaluate("""({edge,side,speed})=>{
                      rack();events.length=0;
                      const cy=edge==='top'?T+rad+.02:B-rad-.02;
                      const outward=edge==='top'?-1:1;
                      const ball=makeBall(1,W/2+side*13,cy);
                      ball.vy=outward*speed;
                      balls=[makeBall(0,400,285),ball];balls[0].potted=true;
                      turn=1;groups={1:'solids',2:'stripes'};breakShot=false;
                      shot={player:1,breakShot:false,firstHit:1,
                        railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                      shooting=true;
                      const impulse=shotSpeed(75,false);
                      let ticks=0;
                      while(!settled()&&ticks<200){physics(STEP);ticks++}
                      return {x:ball.x,y:ball.y,vx:ball.vx,vy:ball.vy,
                        potted:ball.potted,rail:shot.railAfterContact,
                        ticks,settled:settled(),inside:ball.y>=T+rad-1e-4&&
                          ball.y<=B-rad+1e-4,impulse,
                        calibrated:shotSpeed(75,false)===impulse,
                        sounds:events.map(e=>e[0])};
                    }""",{'edge':edge,'side':side,'speed':speed})
                    tag=f'{width}x{height} {edge} side={side} speed={speed}'
                    check(tag+' ball naturally settles',data['settled'] and data['ticks']<200,data)
                    check(tag+' missed pocket is not a phantom pot',not data['potted'],data)
                    check(tag+' missed pocket cannot strand ball beyond cushion',data['inside'],data)
                    check(tag+' actual lip rebound satisfies no-rail foul rule',data['rail'],data)
                    check(tag+' calibrated shot impulse unchanged',data['calibrated'],data)
            control=page.evaluate("""edge=>{
                rack();events.length=0;
                const ball=makeBall(1,W/2,edge==='top'?T+rad+.02:B-rad-.02);
                ball.vy=(edge==='top'?-1:1)*.25;
                balls=[makeBall(0,400,285),ball];balls[0].potted=true;
                shot={player:1,breakShot:false,firstHit:1,
                  railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                let ticks=0;
                while(!ball.potted&&ticks<100){physics(STEP);ticks++}
                return {potted:ball.potted,ticks,pocketed:shot.pocketed,
                  scratch:shot.scratch};
            }""",edge)
            check(f'{width}x{height} {edge} gentle centred pocket still captures',
                  control['potted'] and control['pocketed']==[1] and
                  not control['scratch'],control)
        check(f'{width}x{height} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POCKET_LIP_STALL_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Controlled Chromium physics; physical Samsung and human acceptance release-blocking.'
},indent=2))
print('POCKET LIP STALL',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
