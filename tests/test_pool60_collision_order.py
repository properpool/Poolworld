"""Collision impulse ordering across tightly clustered legal layouts.

Compare the same physical arrangement with object balls stored in opposite
array orders. Chromium fixtures only; not physical-device/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parent.parent
P=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(name,passed,result):
    checks.append({'name':name,'passed':bool(passed),'result':result})
    print(('PASS' if passed else 'FAIL'),name,result,flush=True)

SCENARIO="""({positions,steps})=>{
 rack();
 balls=[makeBall(0,200,285),...positions.map(p=>makeBall(...p))];
 breakShot=false;
 shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
       pocketed:[],scratch:false,targetEight:false};
 balls[0].vx=9.2;balls[0].vy=0;
 const legal=balls.every((a,i)=>balls.slice(i+1).every(
  b=>Math.hypot(a.x-b.x,a.y-b.y)>=2*rad));
 const kinetic=()=>balls.reduce((sum,b)=>sum+b.vx*b.vx+b.vy*b.vy+.4*b.spin*b.spin,0);
 const initialEnergy=kinetic();
 for(let i=0;i<steps;i++)physics(STEP);
 return {legal,firstHit:shot.firstHit,initialEnergy,energy:kinetic(),
  finite:balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin].every(Number.isFinite)),
  state:balls.map(b=>({id:b.id,x:b.x,y:b.y,vx:b.vx,vy:b.vy,spin:b.spin,potted:b.potted}))
    .sort((a,b)=>a.id-b.id)};
}"""

SCENARIOS=[
 ('staggered cue double contact',[[1,224,271],[2,222,299]],2),
 ('symmetric double contact tie',[[1,222,271],[2,222,299]],1),
 ('four-ball clustered transfer',[[1,224,271],[2,222,299],[3,246,285],[4,274,285]],2)
]

def max_state_delta(a,b):
    return max(abs(x[k]-y[k]) for x,y in zip(a,b)
               for k in ('x','y','vx','vy','spin'))

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(P.read_text(),wait_until='load')
        for name,positions,first_hit in SCENARIOS:
            for steps in (1,24):
                original=page.evaluate(SCENARIO,{'positions':positions,'steps':steps})
                reversed_=page.evaluate(SCENARIO,{'positions':list(reversed(positions)),'steps':steps})
                delta=max_state_delta(original['state'],reversed_['state'])
                prefix=f'{width}x{height} {name} {steps} steps'
                check(prefix+' order invariance',delta<1e-6,{'delta':delta})
                check(prefix+' legal finite and first hit',
                    original['legal'] and reversed_['legal'] and
                    original['finite'] and reversed_['finite'] and
                    original['firstHit']==reversed_['firstHit']==first_hit,
                    {'first':original['firstHit'],'reverse':reversed_['firstHit']})
                check(prefix+' dissipative energy',
                    original['energy']<=original['initialEnergy']*1.001 and
                    reversed_['energy']<=reversed_['initialEnergy']*1.001,
                    {'before':original['initialEnergy'],'after':original['energy']})
        check(f'{width}x{height} no browser exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_COLLISION_ORDER_RESULTS.json').write_text(
 json.dumps({'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Chromium deterministic physics only; not physical Samsung or independent human playability.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
