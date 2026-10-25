"""Pocket-well capture versus near-miss jaw/rail overflow, all six pockets.

Controlled Chromium physics fixtures, including deliberate overrun edge cases.
Not evidence of human playability or real Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parent.parent
P=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(name, ok, result):
    checks.append({'name':name,'passed':bool(ok),'result':result})
    print(('PASS' if ok else 'FAIL'),name,result,flush=True)

# x/y and velocity for approaches on the *outer* side of each jaw.\n# The object ball must rebound rather than be swallowed by the pocket.\n# A corner approach on the inner side can legitimately deflect into the pocket.
mouths=[
    ('top-left',128,93.2,0,-2.4,110,77),
    ('top-middle',581,93.2,0,-2.4,581,77),
    ('top-right',972,93.2,0,-2.4,990,77),
    ('bottom-left',128,476.8,0,2.4,110,493),
    ('bottom-middle',581,476.8,0,2.4,581,493),
    ('bottom-right',972,476.8,0,2.4,990,493),
]
# Legitimate pots must still work at the same physics settings.
centres=[
    ('top-left',210,170,79,78),
    ('top-middle',550,200,550,70),
    ('top-right',920,170,1021,78),
    ('bottom-left',210,400,79,492),
    ('bottom-middle',550,365,550,500),
    ('bottom-right',920,400,1021,492),
]
SIMULATE="""([x,y,vx,vy,steps])=>{
 rack();for(const b of balls)if(b.id!==1)b.potted=true;
 const b=balls.find(b=>b.id===1);
 Object.assign(b,{x,y,vx,vy,spin:0,follow:0,potted:false});
 shot={player:1,breakShot:false,firstHit:1,railAfterContact:false,pocketed:[],scratch:false};
 let n=0;for(;n<steps&&!b.potted;n++)physics(STEP);
 return {potted:b.potted,rail:shot.railAfterContact,x:b.x,y:b.y,vx:b.vx,vy:b.vy,steps:n};
}"""
POT="""([ox,oy,hx,hy])=>{
 rack();balls=balls.slice(0,2);breakShot=false;
 const a=Math.atan2(hy-oy,hx-ox),obj=balls[1],cue=balls[0];
 obj.x=ox;obj.y=oy;cue.x=ox-Math.cos(a)*90;cue.y=oy-Math.sin(a)*90;
 aim=a;showPower(55);const fired=shoot();let n=0;
 while(!settled()&&n++<4000)physics(STEP);
 return {fired,potted:obj.potted,firstHit:shot?.firstHit,settled:settled(),steps:n};
}"""
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390)]:
        page=browser.new_page(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(P.read_text(),wait_until='load')
        for name,x,y,vx,vy,ox,oy in mouths:
            approach=page.evaluate(SIMULATE,[x,y,vx,vy,100])
            check(f'{width} {name} jaw-side near miss rebounds',
                not approach['potted'] and approach['rail'],approach)
            # The historical bug potted any ball past the outer rail in a
            # broad mouth band, even outside the actual circular pocket well.
            # This one-step edge fixture isolates that specific false capture.
            overrun=page.evaluate(SIMULATE,[ox,oy,vx,vy,1])
            check(f'{width} {name} outer-rail overrun is not a pot',
                not overrun['potted'],overrun)
        for name,ox,oy,hx,hy in centres:
            result=page.evaluate(POT,[ox,oy,hx,hy])
            check(f'{width} {name} legitimate centred pot retained',
                result['fired'] and result['potted'] and result['firstHit']==1
                and result['settled'],result)
        check(f'{width} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POCKET_MOUTH_GUARD_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Controlled Chromium fixtures; no physical Samsung or independent human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
