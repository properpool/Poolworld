"""First-contact ordering in tightly clustered natural ball layouts.

Checks swept 120Hz cue contacts rather than relying on rack array order.
Controlled Chromium physics only; not human or physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parent.parent
P=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(name,ok,data):
    checks.append({'name':name,'passed':bool(ok),'result':data})
    print(('PASS' if ok else 'FAIL'),name,data,flush=True)

# Cue moves about 4.59 table units per 120Hz step at 9.2 initial speed.
# At y +/-14, collision threshold in x is ~19.98. The nearer object
# (x=222) is reached ~2 table units before the farther (x=224), but
# both overlap the cue at the end of the step.
SCENARIO="""({positions,velocity})=>{
 rack();balls=[makeBall(0,200,285),...positions.map(p=>makeBall(p[0],p[1],p[2]))];
 breakShot=false;shot={player:1,breakShot:false,firstHit:null,
 railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
 balls[0].vx=velocity;balls[0].vy=0;
 const initiallyLegal=balls.every((a,i)=>balls.slice(i+1).every(
   b=>Math.hypot(a.x-b.x,a.y-b.y)>=2*rad));
 physics(STEP);
 return {firstHit:shot.firstHit,initiallyLegal,
  cueX:balls[0].x,positions:balls.map(b=>[b.id,b.x,b.y]),
  finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
}"""
cases=[
 ('nearer second in rack array',[[1,224,271],[2,222,299]],2,9.2),
 ('nearer first in rack array',[[2,222,299],[1,224,271]],2,9.2),
 ('opposite cluster approach',[[1,222,271],[2,224,299]],1,9.2),
 ('single legal contact',[[2,222,299]],2,9.2),
 ('no contact when cue stops short',[[1,224,271],[2,222,299]],None,2.0),
]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(P.read_text(),wait_until='load')
        for name,positions,expected,velocity in cases:
            r=page.evaluate(SCENARIO,{'positions':positions,'velocity':velocity})
            check(f'{width}x{height} {name}',
                r['firstHit']==expected and r['initiallyLegal'] and r['finite'],r)
        check(f'{width}x{height} no JS exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_FIRST_CONTACT_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
     'limits':'Controlled Chromium fixtures; not independent human or physical Samsung testing.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
