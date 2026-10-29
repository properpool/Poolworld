"""A real cue impulse into a PRE-TOUCHING ball occurs at t=0 of the 120Hz
physics tick. A separate object ball rebounding from a cushion later in that
same tick must satisfy the post-contact rail rule. The initial cue contact is
recorded by the impulse solver (not the swept first-contact detector), so
deferred rail events must be reconciled there as well. Include symmetric
two-object cue contacts and negative chronology controls. Chromium tests
only: no physical Samsung Galaxy A37 or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,details):
    checks.append({'name':name,'passed':bool(passed),'details':details})
    if not passed:print('FAIL',name,json.dumps(details),flush=True)

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
        for direction in (-1,1):
            for strength in (25,45,75,95):
                for scenario in ('touching-single','touching-double',
                                 'separating','rail-before-contact'):
                    result=page.evaluate("""({direction,strength,scenario})=>{
                      const cue=makeBall(0,400,285);
                      const touching=scenario!=='rail-before-contact';
                      const double=scenario==='touching-double';
                      const distance=2*rad-.001;
                      const offset=double?Math.sqrt(distance*distance-100):distance;
                      const gap=shotSpeed(strength,false)*.5*.75;
                      const obj1=makeBall(1,400+direction*
                        (touching?offset:2*rad+gap),double?295:285);
                      const objects=[obj1];
                      if(double)objects.push(makeBall(2,400+direction*offset,275));
                      const rail=makeBall(9,direction>0?R-rad-.3:L+rad+.3,400);
                      cue.vx=direction*shotSpeed(strength,false)*
                        (scenario==='separating'?-1:1);
                      rail.vx=direction*4;
                      balls=[cue,...objects,rail];
                      turn=1;groups={1:'solids',2:'stripes'};
                      ballInHand=false;gameOver=false;winner=null;breakShot=false;
                      shot={player:1,breakShot:false,firstHit:null,
                        railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                      shooting=true;accumulator=0;events.length=0;
                      showPower(strength);
                      const expectedImpulse=shotSpeed(strength,false);
                      physics(STEP);
                      const state={firstHit:shot.firstHit,
                        railAfterContact:shot.railAfterContact,
                        railVelocity:rail.vx,objectSpeed:Math.hypot(obj1.vx,obj1.vy),
                        allFinite:balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow]
                          .every(Number.isFinite)),
                        power,impulse:shotSpeed(power,false),
                        objectCount:objects.length};
                      resolveShot();
                      return {...state,ballInHand,turn,gameOver,
                        expectedImpulse};
                    }""",{'direction':direction,'strength':strength,
                          'scenario':scenario})
                    tag=f'{width}x{height} direction={direction} power={strength} {scenario}'
                    hit=scenario!='separating'
                    legal=scenario in ('touching-single','touching-double')
                    check(tag+' real cue first contact only',result['firstHit']==(1 if hit else None),result)
                    check(tag+' moving rail ball actually rebounds',
                          result['railVelocity']*direction<0,result)
                    check(tag+' post-contact rail chronology is correct',
                          result['railAfterContact']==legal,result)
                    check(tag+' ball-in-hand awarded only for a genuine foul',
                          result['ballInHand']==(not legal),result)
                    check(tag+' actual touching contact transfers momentum',
                          (result['objectSpeed']>.05) if legal else
                          (result['objectSpeed']<.001 if scenario=='separating'
                           else result['objectSpeed']>.05),result)
                    check(tag+' selected shot strength and impulse unchanged',
                          result['power']==strength and
                          abs(result['impulse']-result['expectedImpulse'])<1e-9,result)
                    check(tag+' match continues to the correct player',
                          result['turn']==2 and not result['gameOver'],result)
                    check(tag+' all physics values finite',result['allFinite'],result)
        check(f'{width}x{height} no Chromium page errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_TOUCHING_RAIL_CHRONOLOGY_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium 120Hz physics only; physical Galaxy A37 and independent human acceptance are release-blocking.'},indent=2))
print('TOUCHING CONTACT RAIL CHRONOLOGY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
