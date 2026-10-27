"""Pool World cue guide: never promise an object hit beyond the first cushion.

The object may lie inside the cloth but a grazing cue-centre ray can reach the
cushion before its expanded ball circle. The previous guide drew through the
rail and displayed an impossible ghost-ball impact. Browser tests only.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,ok,detail=None):
    checks.append({'name':label,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',label,detail,flush=True)

# Three physically valid positions with a grazing target just beyond a cushion.
# The object is on the cloth; the cue-centre trajectory hits rubber first.
C=(467.268911527382,155.57344798591507)
O=(625.5305953458751,97.69404764653603)
A=-0.49449104311148695
cases=[
 ('top-graze',C,O,A,False),
 ('bottom-graze',(C[0],570-C[1]),(O[0],570-O[1]),-A,False),
 ('left-graze',(1100-C[0],C[1]),(1100-O[0],O[1]),-math.pi-A,False),
 ('reachable-centre',(260,280),(600,280),0,True),
 ('reachable-diagonal',(260,280),(560,360),math.atan2(80,300),True),
 ('clear-rail',(260,280),(600,430),0,False),
]
def expected(c,o,a):
    dx,dy=math.cos(a),math.sin(a)
    tx=((1021-12.2-c[0])/dx if dx>0 else (79+12.2-c[0])/dx) if abs(dx)>1e-12 else float('inf')
    ty=((492-12.2-c[1])/dy if dy>0 else (78+12.2-c[1])/dy) if abs(dy)>1e-12 else float('inf')
    rail=min(v for v in (tx,ty) if v>0)
    ox,oy=o[0]-c[0],o[1]-c[1]
    proj=ox*dx+oy*dy
    perp2=ox*ox+oy*oy-proj*proj
    if proj>0 and perp2<(24.4)**2:
        hit=proj-math.sqrt(max(0,24.4**2-perp2))
        if hit>=0 and hit<=rail:return hit,True
    return min(900,rail),False

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(412,915),(1280,800)):
        page=browser.new_page(viewport={'width':w,'height':h})
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        label=f'{w}x{h}'
        for name,c,o,a,reachable in cases:
            result=page.evaluate("""({c,o,a})=>{
                balls=[makeBall(0,c[0],c[1]),makeBall(1,o[0],o[1])];
                aim=a;guide=true;
                const oldLine=ctx.lineTo,oldArc=ctx.arc;
                let end=null,arcs=0;
                ctx.lineTo=function(x,y){if(end===null)end=[x,y];return oldLine.apply(this,arguments)};
                ctx.arc=function(){arcs++;return oldArc.apply(this,arguments)};
                try{drawAim()}finally{ctx.lineTo=oldLine;ctx.arc=oldArc}
                return {end,arcs,angle:aim};
            }""",{'c':c,'o':o,'a':a})
            exp,ghost=expected(c,o,a)
            actual=(result['end'][0]-c[0])*math.cos(a)+(result['end'][1]-c[1])*math.sin(a)
            check(f'{label} {name} guide terminates at first reachable contact',
                  abs(actual-exp)<.06,{'actual':actual,'expected':exp})
            check(f'{label} {name} ghost only for reachable ball',
                  (result['arcs']>0)==ghost,{'arcs':result['arcs'],'expected':ghost})
            check(f'{label} {name} aiming angle unchanged',
                  abs(math.atan2(math.sin(result['angle']-a),math.cos(result['angle']-a)))<1e-9)
        check(label+' shot impulse unchanged',
              abs(page.evaluate('shotSpeed(100,false)')-8.35)<1e-8)
        check(label+' no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'checks':checks,'limits':'Chromium only; no physical Samsung performance or independent human acceptance.'}
(ROOT/'POOL_WORLD_6.0_AIM_GUIDE_RAIL_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
