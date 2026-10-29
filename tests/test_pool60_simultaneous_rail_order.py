"""Regression: simultaneous object/object and cue/object contacts are grouped
within a 120Hz physics tick. A rail between those two contact times must be
judged relative to the ACTUAL cue-object contact, not the group's first event.
Tests the real coupled collision solver and completed-shot foul decision in
Chromium across four screen sizes; NOT physical Samsung/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
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
        for order in ('cue-later','cue-earlier'):
            for strength in (25,75,95):
                for railWhen in ('before','between','after'):
                    result=page.evaluate("""({order,strength,railWhen})=>{
                      rack();const cue=makeBall(0,400,285);
                      const one=makeBall(1,424.2,285);
                      const two=makeBall(9,448.4,285);
                      const f=shotSpeed(strength,false)/shotSpeed(75,false);
                      cue.vx=9*f;one.vx=4.5*f;two.vx=0;
                      balls=[cue,one,two];turn=1;
                      groups={1:'solids',2:'stripes'};breakShot=false;
                      gameOver=false;winner=null;ballInHand=false;shooting=true;
                      showPower(strength);
                      shot={player:1,breakShot:false,firstHit:null,
                        railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                      pendingPreContactRails.length=0;
                      const cueT=order==='cue-later'?.21:.20;
                      const objT=order==='cue-later'?.20:.21;
                      const railT=railWhen==='before'?.19:railWhen==='after'?.22:.205;
                      pendingPreContactRails.push(railT);
                      const cuePair={a:cue,b:one,t:cueT,swept:false,nx:0,ny:0};
                      const objPair={a:one,b:two,t:objT,swept:false,nx:0,ny:0};
                      const batch=cueT<objT?[cuePair,objPair]:[objPair,cuePair];
                      const energy=()=>balls.reduce((s,b)=>s+b.vx*b.vx+b.vy*b.vy+
                        .4*(b.spin*b.spin+b.follow*b.follow),0);
                      const before=energy();
                      const solved=resolveSimultaneousContacts(batch);
                      const after=energy();
                      const firstHit=shot.firstHit,rail=shot.railAfterContact;
                      const pocketed=shot.pocketed.slice();
                      const impulse=shotSpeed(power,false);
                      resolveShot();
                      return {solved,firstHit,rail,ballInHand,turn,gameOver,
                        shooting,pocketed,energyBefore:before,energyAfter:after,
                        impulse,power,finite:balls.every(b=>[b.x,b.y,b.vx,b.vy,
                          b.spin,b.follow].every(Number.isFinite)),
                        cueT,objT,railT};
                    }""",{'order':order,'strength':strength,'railWhen':railWhen})
                    expected=result['railT']>result['cueT']+1e-7
                    tag=f'{width}x{height} {order} {strength}% rail-{railWhen}'
                    check(tag+' genuine simultaneous impulses resolved',
                        result['solved'] and result['firstHit']==1,result)
                    check(tag+' chronological rail adjudication',
                        result['rail']==expected,result)
                    check(tag+' correct completed-shot foul and ball-in-hand',
                        result['ballInHand']==(not expected) and result['turn']==2
                        and not result['gameOver'] and not result['shooting'],result)
                    check(tag+' no phantom pocket or kinetic-energy increase',
                        not result['pocketed'] and result['finite']
                        and result['energyAfter']<=result['energyBefore']+1e-7,result)
                    check(tag+' selected shot strength and impulse unchanged',
                        result['power']==strength and
                        abs(result['impulse']-page.evaluate('(v)=>shotSpeed(v,false)',strength))<1e-9,
                        result)
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SIMULTANEOUS_RAIL_ORDER_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Coupled solver and rules in Chromium; independent physical Samsung and human acceptance still release-blocking.'},indent=2))
print('SIMULTANEOUS RAIL ORDER SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
