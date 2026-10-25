"""Deterministic high-speed rail-side clustered ball stress.
Chromium physics fixtures only; not physical Samsung or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(label,ok,detail):
    checks.append({'name':label,'passed':bool(ok),'details':detail})
    if not ok: print('FAIL',label,detail,flush=True)

FIXTURE=r"""({seed,edge,count,steps,reverse})=>{
 const sign=(edge==='left'||edge==='top')?1:-1;
 const horizontal=edge==='left'||edge==='right';
 const bound=horizontal?(sign===1?L+rad:R-rad):(sign===1?T+rad:B-rad);
 const transverse=horizontal?170+(seed%12)*13:305+(seed%12)*10;
 const spacing=2*rad-(.2+(seed%5)*.25);
 let objects=[];
 for(let i=0;i<count;i++){
   const along=bound+sign*(.12+i*spacing);
   const side=transverse+((i+seed)%3-1)*.07;
   const b=makeBall(i+1,horizontal?along:side,horizontal?side:along);
   if(i===count-1){
     const speed=4+(seed%5)*.85;
     if(horizontal){b.vx=-sign*speed;b.vy=((seed%3)-1)*.13}
     else{b.vy=-sign*speed;b.vx=((seed%3)-1)*.13}
     b.spin=((seed%5)-2)*.23;b.follow=((seed%3)-1)*.4;
   }
   objects.push(b);
 }
 if(reverse)objects.reverse();
 balls=[makeBall(0,850,380),...objects];
 shot=null;shooting=false;
 const initial=balls.reduce((e,b)=>e+b.vx*b.vx+b.vy*b.vy+.4*(b.spin*b.spin+b.follow*b.follow),0);
 for(let k=0;k<steps;k++)physics(STEP);
 const ordered=balls.slice(1).sort((a,b)=>a.id-b.id);
 let penetration=0;
 for(let i=0;i<ordered.length;i++)for(let j=i+1;j<ordered.length;j++)
   penetration=Math.max(penetration,2*rad-Math.hypot(ordered[i].x-ordered[j].x,ordered[i].y-ordered[j].y));
 const finite=balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow,...b.rollQ].every(Number.isFinite));
 const inside=ordered.every(b=>b.x>=L+rad-1e-5&&b.x<=R-rad+1e-5&&b.y>=T+rad-1e-5&&b.y<=B-rad+1e-5);
 const energy=balls.reduce((e,b)=>e+b.vx*b.vx+b.vy*b.vy+.4*(b.spin*b.spin+b.follow*b.follow),0);
 return {finite,inside,penetration,energy,initial,potted:balls.some(b=>b.potted),
   state:ordered.flatMap(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow])};
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
        for seed in range(12):
            edge=('left','right','top','bottom')[seed%4]
            count=3+seed%4
            for steps in (1,48):
                a=page.evaluate(FIXTURE,{'seed':seed,'edge':edge,'count':count,'steps':steps,'reverse':False})
                b=page.evaluate(FIXTURE,{'seed':seed,'edge':edge,'count':count,'steps':steps,'reverse':True})
                label=f'{width}x{height} seed{seed} {edge} {count} balls {steps} ticks'
                diff=max(abs(x-y) for x,y in zip(a['state'],b['state']))
                check(label+' finite, on cloth, unpotted',a['finite'] and b['finite'] and a['inside'] and b['inside'] and not a['potted'] and not b['potted'],
                      {'finite':a['finite'],'inside':a['inside'],'potted':a['potted']})
                check(label+' no excessive overlap',a['penetration']<=.05 and b['penetration']<=.05,
                      {'overlap':a['penetration'],'reversed':b['penetration']})
                check(label+' order invariant',diff<=1e-6,{'max_delta':diff})
                check(label+' no energy creation',a['energy']<=a['initial']+1e-5 and b['energy']<=b['initial']+1e-5,
                      {'initial':a['initial'],'energy':a['energy'],'reversed':b['energy']})
        check(f'{width}x{height} no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_CLUSTER_STRESS_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Deterministic Chromium simulation only, not real Samsung/human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
