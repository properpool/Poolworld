"""Two equal-time swept cue/object contacts must produce a symmetric split.

Both balls are genuinely touched *between* 120Hz endpoints: the old
single-contact fallback delivered asymmetric impulses based on ID ordering.
These are Chromium physics fixtures, NOT physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, ok, details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok:
        print('FAIL',name,details,flush=True)

SCENE="""({direction,side,steps,reverse})=>{
  rack();
  const x=400,y=285,offset=24.35;
  const cue=makeBall(0,x-direction*2.43,y);
  const first=makeBall(1,x,y-side*offset);
  const second=makeBall(2,x,y+side*offset);
  cue.vx=direction*9.75;
  balls=reverse?[cue,second,first]:[cue,first,second];
  shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
        pocketed:[],scratch:false,targetEight:false};
  shooting=true;breakShot=false;events.length=0;
  const initial=balls.reduce((s,b)=>s+b.vx*b.vx+b.vy*b.vy,0);
  const pre=balls.map(b=>({id:b.id,x:b.x,y:b.y})).sort((a,b)=>a.id-b.id);
  for(let i=0;i<steps;i++)physics(STEP);
  const state=balls.map(b=>({id:b.id,x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                              spin:b.spin,potted:b.potted})).sort((a,b)=>a.id-b.id);
  const energy=balls.reduce((s,b)=>s+b.vx*b.vx+b.vy*b.vy+.4*b.spin*b.spin,0);
  return {state,pre,initial,energy,firstHit:shot.firstHit,
          finite:state.every(b=>[b.x,b.y,b.vx,b.vy,b.spin].every(Number.isFinite))};
}"""

def delta(a,b):
    return max(abs(x[k]-y[k]) for x,y in zip(a,b)
               for k in ('x','y','vx','vy','spin'))

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for direction in (-1,1):
            for side in (-1,1):
                for steps in (1,2,8,24):
                    args={'direction':direction,'side':side,'steps':steps,'reverse':False}
                    a=page.evaluate(SCENE,args)
                    b=page.evaluate(SCENE,{**args,'reverse':True})
                    state=a['state'];cue,one,two=state
                    name=f'{width}x{height} direction={direction} side={side} ticks={steps}'
                    symmetry=max(abs(cue['y']-285),abs(cue['vy']),
                                 abs(one['x']-two['x']),abs(one['y']+two['y']-570),
                                 abs(one['vx']-two['vx']),abs(one['vy']+two['vy']))
                    check(name+' equal-time swept impacts symmetric',
                          symmetry<1e-5,{'delta':symmetry,'cue':cue,'objects':state[1:]})
                    check(name+' order invariant',delta(a['state'],b['state'])<1e-6,
                          {'delta':delta(a['state'],b['state'])})
                    check(name+' both receivers move after physical contact',
                          math.hypot(one['vx'],one['vy'])>.03 and
                          math.hypot(two['vx'],two['vy'])>.03 and
                          a['firstHit']==b['firstHit']==1,
                          {'firstHit':a['firstHit'],'objects':state[1:]})
                    check(name+' energy bounded, finite, not pocketed',
                          a['finite'] and b['finite'] and
                          a['energy']<=a['initial']+1e-6 and
                          b['energy']<=b['initial']+1e-6 and
                          not any(s['potted'] for s in state),
                          {'initial':a['initial'],'energy':a['energy']})
        check(f'{width}x{height} browser errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SIMULTANEOUS_SWEPT_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Deterministic Chromium only; no physical Samsung/human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):
    sys.exit(1)
