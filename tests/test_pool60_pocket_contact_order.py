"""Regression: a cue ball that reaches an object BEFORE that object enters
a side-pocket well in the SAME 120Hz tick must not lose its legal first hit.
The pocket sweep currently runs before ball-ball collision resolution; this
fixture distinguishes the real order using analytic swept times.
Browser physics only; no physical Galaxy A37 or human acceptance.
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
        for direction in (-1,1):
            for level in (75,90):
                for case in ('cue-before-pocket','pocket-before-cue','object-escaping'):
                    result=page.evaluate("""([dir,level,scenario])=>{
                      const speed=shotSpeed(level,false);
                      const gap=scenario==='pocket-before-cue'?28.5:25.5;
                      const cue=makeBall(0,W/2-dir*gap,92);
                      const object=makeBall(1,W/2,92);
                      cue.vx=dir*speed;
                      object.vy=scenario==='object-escaping'?8:-8;
                      balls=[cue,object];turn=1;groups={1:'solids',2:'stripes'};
                      breakShot=false;ballInHand=false;gameOver=false;winner=null;
                      shot={player:1,breakShot:false,firstHit:null,
                        railAfterContact:false,pocketed:[],scratch:false,
                        targetEight:false};
                      shooting=true;events.length=0;accumulator=0;
                      const startSpeed=Math.hypot(cue.vx,cue.vy);
                      physics(STEP);
                      const state={firstHit:shot.firstHit,
                        pocketed:shot.pocketed.slice(),objectPotted:object.potted,
                        cueSpeed:Math.hypot(cue.vx,cue.vy),
                        objectSpeed:Math.hypot(object.vx,object.vy),
                        startSpeed,calibration:shotSpeed(level,false),
                        positions:balls.flatMap(b=>[b.x,b.y,b.vx,b.vy])};
                      resolveShot();
                      return {...state,ballInHand,turn,gameOver};
                    }""",[direction,level,case])
                    tag=f'{width}x{height} dir={direction} power={level} {case}'
                    before=case!='pocket-before-cue'
                    check(tag+' correct chronological first contact',
                          result['firstHit']==(1 if before else None),result)
                    check(tag+' cue impulse occurs before pocket capture',
                          (result['cueSpeed']<result['startSpeed']*.85) if before
                          else abs(result['cueSpeed']-result['startSpeed'])<.2,result)
                    check(tag+' expected pocket or escape outcome',
                          result['objectPotted']==(case!='object-escaping'),result)
                    check(tag+' correct no-hit foul control',
                          (result['ballInHand'] if not before else True),result)
                    check(tag+' unchanged power and finite physics',
                          abs(result['calibration']-result['startSpeed'])<1e-10
                          and all(math.isfinite(x) for x in result['positions']),result)
                    check(tag+' normal turn and no premature match win',
                          result['turn']==(1 if before and result['objectPotted'] else 2)
                          and not result['gameOver'],result)
        check(f'{width}x{height} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_POCKET_CONTACT_ORDER_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium only; physical Samsung and human acceptance remain blocked.'},indent=2))
print('POCKET CONTACT ORDER SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
