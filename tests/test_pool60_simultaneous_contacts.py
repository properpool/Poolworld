"""Simultaneous clustered contacts: symmetric split, conservation, order invariance.
Chromium deterministic fixtures, not real Samsung/human playability.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parent.parent
P=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(name,condition,detail):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
    print(('PASS' if condition else 'FAIL'),name,detail,flush=True)

SCENARIO="""({positions,steps})=>{
 rack();
 balls=[makeBall(0,200,285),...positions.map(p=>makeBall(...p))];
 breakShot=false;
 shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
       pocketed:[],scratch:false,targetEight:false};
 balls[0].vx=9.2;balls[0].vy=0;
 const kinetic=()=>balls.reduce((sum,b)=>sum+b.vx*b.vx+b.vy*b.vy+.4*(b.spin*b.spin+b.follow*b.follow),0);
 const initial=kinetic();
 const legal=balls.every((a,i)=>balls.slice(i+1).every(b=>Math.hypot(a.x-b.x,a.y-b.y)>=2*rad));
 for(let i=0;i<steps;i++)physics(STEP);
 const sorted=balls.map(b=>({id:b.id,x:b.x,y:b.y,vx:b.vx,vy:b.vy,spin:b.spin,follow:b.follow,potted:b.potted}))
   .sort((a,b)=>a.id-b.id);
 return {initial,energy:kinetic(),firstHit:shot.firstHit,legal,
         finite:sorted.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow].every(Number.isFinite)),
         state:sorted};
}"""

SCENARIOS=[
 ('symmetric split',[[1,222,271],[2,222,299]]),
 ('symmetric split plus centre receiver',[[1,222,271],[2,222,299],[3,248,285]]),
 ('symmetric four-object cluster',[[1,222,271],[2,222,299],[3,248,285],[4,274,285]])
]

def max_delta(a,b):
    return max(abs(x[k]-y[k]) for x,y in zip(a,b)
               for k in ('x','y','vx','vy','spin','follow'))

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
        for label,positions in SCENARIOS:
            for steps in (1,24,72):
                a=page.evaluate(SCENARIO,{'positions':positions,'steps':steps})
                b=page.evaluate(SCENARIO,{'positions':list(reversed(positions)),'steps':steps})
                prefix=f'{width}x{height} {label} {steps} steps'
                delta=max_delta(a['state'],b['state'])
                check(prefix+' permutation invariant',delta<1e-6,{'delta':delta})
                upper=a['state'][1];lower=a['state'][2]
                symmetry=max(abs(upper['x']-lower['x']),abs(upper['y']+lower['y']-570),
                             abs(upper['vx']-lower['vx']),abs(upper['vy']+lower['vy']))
                check(prefix+' symmetric cue split',symmetry<1e-5,{'symmetry_delta':symmetry})
                check(prefix+' dissipative bounded energy',
                      a['energy']<=a['initial']*1.00001 and b['energy']<=b['initial']*1.00001,
                      {'before':a['initial'],'after':a['energy'],'reverse':b['energy']})
                check(prefix+' finite legal and stable first contact',
                      a['legal'] and b['legal'] and a['finite'] and b['finite']
                      and a['firstHit']==b['firstHit']==1,
                      {'legal':a['legal'],'finite':a['finite'],'firstHit':a['firstHit']})
        check(f'{width}x{height} browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SIMULTANEOUS_CONTACT_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Deterministic Chromium tests only, no physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
