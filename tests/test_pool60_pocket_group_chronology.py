"""Open-table group assignment must follow the actual pocket-entry chronology,
not rack/array order when a solid and stripe fall in the same 120Hz tick.
Browser physics/rules regression only; physical Samsung acceptance is separate.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':None if ok else details})
    if not ok:print('FAIL',name,json.dumps(details),flush=True)

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
        for first in ('solid','stripe'):
            for arrayFirst in ('solid','stripe'):
                for factor in (.85,1,1.15):
                    for strength in (25,75,95):
                        result=page.evaluate("""({first,arrayFirst,factor,strength})=>{
                          rack();
                          const cue=makeBall(0,250,285);
                          const capture=pocket*.74;
                          // Each ball starts OUTSIDE its own side-pocket well.
                          // The first enters at ~0.15 of a tick, the second
                          // at ~0.6-0.8. Their storage order is independent.
                          const sd=first==='solid'?.35:1.4;
                          const td=first==='stripe'?.35:1.4;
                          const solid=makeBall(1,W/2,B+8-capture-sd);
                          const stripe=makeBall(9,W/2,T-8+capture+td);
                          solid.vx=stripe.vx=0;
                          solid.vy=5*factor;stripe.vy=-4.5*factor;
                          balls=arrayFirst==='solid'?[cue,solid,stripe]:[cue,stripe,solid];
                          turn=1;groups={1:null,2:null};breakShot=false;
                          gameOver=false;winner=null;ballInHand=false;shooting=true;
                          showPower(strength);
                          shot={player:1,breakShot:false,firstHit:9,
                            railAfterContact:true,pocketed:[],scratch:false,targetEight:false};
                          const entry=(b,d)=>{
                            const speed=Math.abs(b.vy);
                            const decel=(.012+.0016*Math.min(speed,4))*(STEP*60);
                            return d/((speed-decel)*(STEP*60));
                          };
                          const solidT=entry(solid,sd),stripeT=entry(stripe,td);
                          const initialOutside=sd>0&&td>0&&
                            Math.hypot(solid.x-W/2,solid.y-(B+8))>capture&&
                            Math.hypot(stripe.x-W/2,stripe.y-(T-8))>capture;
                          physics(STEP);
                          const pocketed=[...shot.pocketed];
                          const both=solid.potted&&stripe.potted&&!cue.potted;
                          resolveShot();
                          return {first,arrayFirst,factor,strength,solidT,stripeT,
                            initialOutside,both,pocketed,group:groups[1],
                            otherGroup:groups[2],turn,ballInHand,gameOver,
                            power,impulse:shotSpeed(power,false),
                            finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                        }""",{'first':first,'arrayFirst':arrayFirst,'factor':factor,'strength':strength})
                        expected='solids' if first=='solid' else 'stripes'
                        other='stripes' if first=='solid' else 'solids'
                        tag=f'{width}x{height} first={first} arrayFirst={arrayFirst} speed={factor} power={strength}'
                        check(tag+' distinct in-tick entry times',result['initialOutside'] and
                            0<result['solidT']<1 and 0<result['stripeT']<1 and
                            (result['solidT']<result['stripeT'])==(first=='solid'),result)
                        check(tag+' both legal objects pocketed in one physics tick',
                            result['both'] and sorted(result['pocketed'])==[1,9],result)
                        check(tag+' first physical pot determines open-table group',
                            result['group']==expected and result['otherGroup']==other,result)
                        check(tag+' legal turn retained without ball in hand',
                            result['turn']==1 and not result['ballInHand'] and
                            not result['gameOver'],result)
                        check(tag+' calibrated shot power and finite physics preserved',
                            result['finite'] and result['power']==strength and
                            result['impulse']>0,result)
        check(f'{width}x{height} browser exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POCKET_GROUP_CHRONOLOGY_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium physics/rules only; physical Samsung and human acceptance release-blocking.'},indent=2))
print('POCKET GROUP CHRONOLOGY SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
