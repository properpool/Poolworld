"""Mandatory regression: a near-simultaneous cue impact on two different
object balls must award the FIRST actual contact, not the lowest ball number.
A legal stripe struck 0.005 of a 120Hz tick before an illegal solid must not
be turned into a foul. Equal-time ties remain deterministic by ball ID.
Chromium coupled-solver/rules checks only; not physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, ok, result):
    checks.append({'name':name,'passed':bool(ok),'details':result if not ok else None})
    if not ok: print('FAIL',name,json.dumps(result),flush=True)

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
        for first in ('stripe','solid','tie'):
            for strength in (25,75,95):
                for railWhen in ('before','between','after'):
                    for reverse in (False,True):
                        result=page.evaluate("""({first,strength,railWhen,reverse})=>{
                          rack();const cue=makeBall(0,400,285);
                          const stripe=makeBall(9,420,273);
                          const solid=makeBall(1,420,297);
                          const factor=shotSpeed(strength,false)/shotSpeed(75,false);
                          cue.vx=9*factor;cue.vy=0;stripe.vx=solid.vx=0;
                          balls=reverse?[cue,solid,stripe]:[cue,stripe,solid];
                          turn=1;groups={1:'stripes',2:'solids'};breakShot=false;
                          gameOver=false;winner=null;ballInHand=false;shooting=true;
                          showPower(strength);
                          shot={player:1,breakShot:false,firstHit:null,
                            railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                          pendingPreContactRails.length=0;
                          const stripeT=first==='solid'?.205:.20;
                          const solidT=first==='stripe'?.205:.20;
                          const earliest=Math.min(stripeT,solidT);
                          const railT=railWhen==='before'?.19:railWhen==='after'?.22:.2025;
                          pendingPreContactRails.push(railT);
                          const pairStripe={a:cue,b:stripe,t:stripeT,swept:false,nx:0,ny:0};
                          const pairSolid={a:cue,b:solid,t:solidT,swept:false,nx:0,ny:0};
                          const batch=reverse?[pairSolid,pairStripe]:[pairStripe,pairSolid];
                          const energy=()=>balls.reduce((s,b)=>s+b.vx*b.vx+b.vy*b.vy+
                            .4*(b.spin*b.spin+b.follow*b.follow),0);
                          const before=energy(),solved=resolveSimultaneousContacts(batch);
                          const after=energy(),firstHit=shot.firstHit;
                          const rail=shot.railAfterContact,impulse=shotSpeed(power,false);
                          resolveShot();
                          return {solved,firstHit,rail,ballInHand,turn,gameOver,shooting,
                            before,after,impulse,power,earliest,railT,stripeT,solidT,
                            finite:balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow]
                              .every(Number.isFinite)),potted:balls.some(b=>b.potted)};
                        }""",{'first':first,'strength':strength,'railWhen':railWhen,'reverse':reverse})
                        expectedHit=9 if first=='stripe' else 1
                        expectedRail=result['railT']>result['earliest']+1e-7
                        expectedFoul=expectedHit!=9 or not expectedRail
                        tag=f'{width}x{height} {first} {strength}% {railWhen} reversed={reverse}'
                        check(tag+' both real cue impulses solved',result['solved'],result)
                        check(tag+' earliest cue object chosen, equal tie by id',
                            result['firstHit']==expectedHit,result)
                        check(tag+' rail judged from earliest cue impact',
                            result['rail']==expectedRail,result)
                        check(tag+' completed-shot foul and turn',
                            result['ballInHand']==expectedFoul and result['turn']==2
                            and not result['gameOver'] and not result['shooting'],result)
                        check(tag+' dissipative finite collision and no phantom pot',
                            result['finite'] and not result['potted'] and
                            result['after']<=result['before']+1e-7,result)
                        check(tag+' selected power and calibrated impulse unchanged',
                            result['power']==strength and
                            abs(result['impulse']-page.evaluate(
                                '(p)=>shotSpeed(p,false)',strength))<1e-9,result)
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SIMULTANEOUS_FIRST_HIT_ORDER_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium solver/rules only; physical Samsung and human acceptance remain release-blocking.'},indent=2))
print('SIMULTANEOUS FIRST HIT ORDER SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
