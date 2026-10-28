"""Cue/object contact preceding cue scratch must transfer momentum before the
cue enters a side-pocket well in the SAME 120Hz tick. An earlier cue pocket
must still suppress later contacts. Browser fixtures are not physical Samsung
Galaxy A37 or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, ok, detail):
    checks.append({'name':name,'passed':bool(ok),'details':detail})
    if not ok: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=width<1100)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for top in (True,False):
            for horizontal in (-1,1):
                for level in (75,90):
                    for scenario in ('contact-before-scratch','scratch-before-contact','wide-miss'):
                        result=page.evaluate("""([top,horizontal,level,scenario])=>{
                          const dir=top?1:-1,cy=top?92:478;
                          const speed=shotSpeed(level,false);
                          const offset=scenario==='contact-before-scratch'?23.5:
                                       scenario==='scratch-before-contact'?23.9:40;
                          const cue=makeBall(0,W/2,cy);
                          const object=makeBall(1,W/2+horizontal*offset,cy+dir*7);
                          cue.vx=horizontal*.5*speed;
                          cue.vy=-dir*Math.sqrt(3)/2*speed;
                          balls=[cue,object];turn=1;groups={1:'solids',2:'stripes'};
                          breakShot=false;ballInHand=false;gameOver=false;winner=null;
                          shot={player:1,breakShot:false,firstHit:null,
                            railAfterContact:false,pocketed:[],scratch:false,
                            targetEight:false};
                          shooting=true;events.length=0;pocketVisuals.length=0;
                          const initialSpeed=Math.hypot(cue.vx,cue.vy);
                          physics(STEP);
                          const beforeResolve={firstHit:shot.firstHit,
                            cuePotted:cue.potted,objectPotted:object.potted,
                            objectSpeed:Math.hypot(object.vx,object.vy),
                            pocketed:shot.pocketed.slice(),scratch:shot.scratch,
                            ghosts:pocketVisuals.map(g=>g.id),
                            soundTypes:events.map(e=>e[0]),
                            state:balls.flatMap(b=>[b.x,b.y,b.vx,b.vy]),
                            initialSpeed,calibration:shotSpeed(level,false)};
                          resolveShot();
                          return {...beforeResolve,turn,ballInHand,gameOver,
                            cueRestored:!balls[0].potted};
                        }""",[top,horizontal,level,scenario])
                        tag=f'{width}x{height} {"top" if top else "bottom"} xdir={horizontal} power={level} {scenario}'
                        early=scenario=='contact-before-scratch'
                        check(tag+' chronological cue first hit',
                              result['firstHit']==(1 if early else None),result)
                        check(tag+' momentum transferred only before scratch',
                              result['objectSpeed']>.12 if early else result['objectSpeed']<1e-8,result)
                        check(tag+' cue scratch captured exactly once',
                              result['cuePotted'] and result['scratch'] and
                              result['pocketed']==[0] and result['ghosts']==[0],result)
                        check(tag+' object never falsely pocketed',
                              not result['objectPotted'],result)
                        check(tag+' collision sound chronological',
                              ('ball' in result['soundTypes']) if early else
                              ('ball' not in result['soundTypes']),result)
                        check(tag+' foul awards opponent ball in hand',
                              result['ballInHand'] and result['turn']==2 and
                              result['cueRestored'] and not result['gameOver'],result)
                        check(tag+' unchanged calibrated impulse and finite state',
                              abs(result['calibration']-result['initialSpeed'])<1e-10
                              and all(math.isfinite(x) for x in result['state']),result)
        check(f'{width}x{height} no browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_CUE_SCRATCH_CHRONOLOGY_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium only. Physical Samsung Galaxy A37 shot feel, FPS and human acceptance remain release-blocking.'},indent=2))
print('CUE SCRATCH CHRONOLOGY SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
