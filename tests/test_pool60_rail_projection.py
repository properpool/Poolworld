"""Rail-side contact projection: resolve overlap without ejecting balls from cloth.

Deterministic Chromium physics fixtures only; not real-device or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    print(('PASS' if ok else 'FAIL'),name,details,flush=True)

FIXTURE="""({edge,count,moving})=>{
 rack();
 const lx=L+rad,hx=R-rad,ly=T+rad,hy=B-rad;
 const setups={
  left:{x:lx+.15,y:285,dx:1,dy:0,vx:-1.6,vy:0},
  right:{x:hx-.15,y:285,dx:-1,dy:0,vx:1.6,vy:0},
  top:{x:400,y:ly+.15,dx:0,dy:1,vx:0,vy:-1.6},
  bottom:{x:400,y:hy-.15,dx:0,dy:-1,vx:0,vy:1.6}
 };
 const s=setups[edge];
 balls=[makeBall(0,850,380)];
 for(let k=0;k<count;k++)balls.push(makeBall(k+1,
  s.x+s.dx*k*(2*rad-1.35),s.y+s.dy*k*(2*rad-1.35)));
 if(moving){balls[count].vx=s.vx;balls[count].vy=s.vy}
 const before=balls.slice(1).reduce((t,b)=>t+b.vx*b.vx+b.vy*b.vy,0);
 shot=null;shooting=false;
 physics(STEP);
 let overlap=0;
 for(let i=1;i<balls.length;i++)for(let j=i+1;j<balls.length;j++){
  const a=balls[i],b=balls[j];
  overlap=Math.max(overlap,2*rad-Math.hypot(a.x-b.x,a.y-b.y));
 }
 const inside=balls.slice(1).every(b=>b.x>=lx-1e-6&&b.x<=hx+1e-6&&b.y>=ly-1e-6&&b.y<=hy+1e-6);
 const finite=balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.follow,...b.rollQ].every(Number.isFinite));
 const energy=balls.slice(1).reduce((t,b)=>t+b.vx*b.vx+b.vy*b.vy+.4*(b.spin*b.spin+b.follow*b.follow),0);
 return {inside,finite,overlap,energy,before,potted:balls.some(b=>b.potted),
         states:balls.slice(1).map(b=>[b.id,b.x,b.y,b.vx,b.vy])};
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
        for edge in ('left','right','top','bottom'):
            for count in (2,3):
                for moving in (False,True):
                    r=page.evaluate(FIXTURE,{'edge':edge,'count':count,'moving':moving})
                    label=f'{width}x{height} {edge} {count}-ball '+('impact' if moving else 'rest')
                    check(label+' separation <= 0.05',r['overlap']<=.05,
                          {'overlap':r['overlap'],'states':r['states']})
                    check(label+' stays on cloth and unpotted',r['inside'] and not r['potted'],
                          {'inside':r['inside'],'potted':r['potted']})
                    check(label+' finite and no kinetic energy gain',r['finite'] and r['energy']<=r['before']+1e-5,
                          {'finite':r['finite'],'energy':r['energy'],'before':r['before']})
        check(f'{width}x{height} no browser errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_RAIL_PROJECTION_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Deterministic Chromium only; no physical Samsung or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
