"""Verify rendered ball roll follows actual on-table displacement after rail/jaw correction.
Deterministic Chromium physics/visual-state regression, NOT human or Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    print(('PASS' if passed else 'FAIL'),name,detail,flush=True)

FIXTURE="""({kind})=>{
 rack();
 const cases={
  free:{x:400,y:285,vx:5,vy:2},
  left:{x:L+rad+.8,y:285,vx:-8,vy:0},
  top:{x:380,y:T+rad+.8,vx:0,vy:-8},
  jaw:{x:L+cornerMouth+11.5,y:T+17,vx:-9,vy:0}
 };
 const c=cases[kind];
 balls=[makeBall(0,900,450),makeBall(1,c.x,c.y)];
 const b=balls[1],initial=[b.x,b.y];
 b.vx=c.vx;b.vy=c.vy;
 shot=null;shooting=false;
 physics(STEP);
 const dx=b.x-initial[0],dy=b.y-initial[1];
 const expected=makeBall(9,0,0);
 rotateRoll(expected,dx,dy);
 const q=b.rollQ,e=expected.rollQ;
 const plus=Math.hypot(...q.map((v,i)=>v-e[i]));
 const minus=Math.hypot(...q.map((v,i)=>v+e[i]));
 return {dx,dy,q,error:Math.min(plus,minus),norm:Math.hypot(...q),
         finite:[b.x,b.y,b.vx,b.vy,...q].every(Number.isFinite),
         inBounds:b.x>=L+rad-1e-5&&b.x<=R-rad+1e-5&&
                  b.y>=T+rad-1e-5&&b.y<=B-rad+1e-5,
         moved:Math.hypot(dx,dy)>0.01};
}"""
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
        for kind in ('free','left','top','jaw'):
            result=page.evaluate(FIXTURE,{'kind':kind})
            tag=f'{width}x{height} {kind}'
            check(tag+' roll matches actual displacement',result['error']<1e-6,
                  {'quaternion_error':result['error'],'travel':[result['dx'],result['dy']]})
            check(tag+' finite normalized rolling orientation',
                  result['finite'] and abs(result['norm']-1)<1e-6,
                  {'finite':result['finite'],'norm':result['norm']})
            check(tag+' ball stays on cloth after rail or jaw',
                  result['inBounds'] and result['moved'],
                  {'inBounds':result['inBounds'],'moved':result['moved']})
        check(f'{width}x{height} browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_RAIL_ROLL_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Chromium deterministic physics only; no real Samsung or human playability acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
