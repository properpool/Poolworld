"""Regression: a moving object must strike another object before entering a
side-pocket well when the collision occurs earlier in the same 120Hz tick.
The pocket sweep precedes the collision solver, so immediate pocketing can
erase a real object/object impulse. Opposite chronology and lateral near-miss
are essential negative controls. Chromium only, not physical Samsung acceptance.
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
        for side in ('top','bottom'):
            for level in (65,75):
                for scenario in ('contact-before-pocket','pocket-before-contact','lateral-near-miss'):
                    result=page.evaluate("""([side,level,scenario])=>{
                      const top=side==='top',dir=top?1:-1;
                      const holeY=top?T-8:B+8;
                      const factor=shotSpeed(level,false)/shotSpeed(75,false);
                      const initialA=8*factor,initialB=14*factor;
                      const gap=scenario==='pocket-before-contact'?20.4:22;
                      const a=makeBall(1,W/2,holeY+dir*gap);
                      const b=makeBall(9,W/2+(scenario==='lateral-near-miss'?28:0),
                        a.y+dir*(2*rad+.8));
                      const cue=makeBall(0,320,285);
                      a.vy=-dir*initialA;b.vy=-dir*initialB;
                      balls=[cue,a,b];turn=1;groups={1:'solids',2:'stripes'};
                      breakShot=false;ballInHand=false;gameOver=false;winner=null;
                      shot={player:1,breakShot:false,firstHit:null,
                        railAfterContact:false,pocketed:[],scratch:false,
                        targetEight:false};
                      shooting=true;events.length=0;pocketVisuals.length=0;
                      const initial={aY:a.y,bY:b.y,initialA,initialB,
                        speed:shotSpeed(level,false)};
                      physics(STEP);
                      return {initial,firstHit:shot.firstHit,
                        aPotted:a.potted,bPotted:b.potted,
                        bSpeed:Math.hypot(b.vx,b.vy),
                        bVelocity:b.vy,aY:a.y,bY:b.y,
                        pocketed:shot.pocketed.slice(),
                        ghosts:pocketVisuals.map(g=>g.id),
                        sounds:events.map(e=>e[0]),
                        cue:[cue.x,cue.y,cue.vx,cue.vy],
                        speedAfter:shotSpeed(level,false),
                        state:balls.flatMap(x=>[x.x,x.y,x.vx,x.vy])};
                    }""",[side,level,scenario])
                    tag=f'{width}x{height} {side} power={level} {scenario}'
                    early=scenario=='contact-before-pocket'
                    check(tag+' pocket is captured once',
                          result['aPotted'] and not result['bPotted']
                          and result['pocketed']==[1],result)
                    check(tag+' true object impact precedes pocket',
                          (result['bSpeed']<result['initial']['initialB']*.8
                           if early else
                           abs(result['bSpeed']-result['initial']['initialB'])<.15),result)
                    check(tag+' impact sound follows chronological contact',
                          (result['sounds'].count('ball')>=1 if early else
                           result['sounds'].count('ball')==0),result)
                    check(tag+' pocket ghost and sound exactly once',
                          result['ghosts']==[1] and
                          result['sounds'].count('pocket')==1,result)
                    check(tag+' cue untouched and no invented first hit',
                          result['cue']==[320,285,0,0] and
                          result['firstHit'] is None,result)
                    check(tag+' unchanged calibrated power and finite physics',
                          abs(result['speedAfter']-result['initial']['speed'])<1e-10
                          and all(math.isfinite(x) for x in result['state']),result)
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_OBJECT_POCKET_CONTACT_ORDER_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium physics only; physical Samsung and human acceptance remain blocked.'},indent=2))
print('OBJECT POCKET CONTACT ORDER SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
