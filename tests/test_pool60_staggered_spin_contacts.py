"""Near-coincident clustered hits with English and follow/draw.
Deterministic Chromium regression only, not physical Samsung/human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'detail':details})
    print(('PASS' if ok else 'FAIL'),name,details,flush=True)

SCENARIO="""({offset,english,draw,steps,reverse})=>{
 rack();
 const objects=[makeBall(1,222,271),makeBall(2,222+offset,299),makeBall(3,248,285)];
 balls=[makeBall(0,200,285),...(reverse?objects.reverse():objects)];
 breakShot=false;
 shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
       pocketed:[],scratch:false,targetEight:false};
 const cue=balls.find(b=>b.id===0);
 cue.vx=9.2;cue.vy=0;cue.spin=english;cue.follow=draw;
 const kinetic=()=>balls.reduce((v,b)=>v+b.vx*b.vx+b.vy*b.vy+.4*(b.spin*b.spin+b.follow*b.follow),0);
 const initial=kinetic();let maximum=initial,coupled=0;
 const previous=resolveSimultaneousContacts;
 resolveSimultaneousContacts=function(batch){coupled++;return previous(batch)};
 try {for(let i=0;i<steps;i++){physics(STEP);maximum=Math.max(maximum,kinetic())}}
 finally{resolveSimultaneousContacts=previous}
 const state=balls.map(b=>({id:b.id,x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                 spin:b.spin,follow:b.follow,potted:b.potted})).sort((a,b)=>a.id-b.id);
 return {initial,maximum,coupled,firstHit:shot.firstHit,state,
         finite:state.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow].every(Number.isFinite))};
}"""
def delta(a,b):
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
        page.set_content(HTML.read_text(),wait_until='load')
        for offset in (.025,-.025):
            for english in (-1.1,0,1.1):
                for draw in (-1.8,1.8):
                    for steps in (1,48):
                        args={'offset':offset,'english':english,'draw':draw,'steps':steps}
                        a=page.evaluate(SCENARIO,{**args,'reverse':False})
                        b=page.evaluate(SCENARIO,{**args,'reverse':True})
                        name=f'{width}x{height} offset={offset} spin={english} follow={draw} steps={steps}'
                        d=delta(a['state'],b['state'])
                        check(name+' rack permutation',d<1e-5,{'delta':d})
                        check(name+' bounded total kinetic energy',
                              a['maximum']<=a['initial']*1.00001 and b['maximum']<=b['initial']*1.00001,
                              {'initial':a['initial'],'max':a['maximum'],'reverse':b['maximum']})
                        check(name+' finite state and chronological first hit',
                              a['finite'] and b['finite'] and a['firstHit']==b['firstHit']==(1 if offset>0 else 2),
                              {'finite':a['finite'],'firstHit':a['firstHit'],'reverse':b['firstHit']})
                        check(name+' coupled near-simultaneous response',
                              a['coupled']>0 and b['coupled']>0,
                              {'normal':a['coupled'],'reverse':b['coupled']})
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_STAGGERED_SPIN_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Chromium deterministic physics only; no physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
