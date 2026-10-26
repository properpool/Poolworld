"""Pool World active-frame and contact-projection regression.

Measures real headless Chromium frame CPU distributions and pointer-to-render
responsiveness. These results are NOT physical Samsung FPS or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',name,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        page.evaluate("""() => {
          window.probe={projections:0,frameMs:[],physicsMs:[],renderMs:[],renderAt:0,pointerAt:0};
          const oldProject=projectRailContactOverlaps;
          projectRailContactOverlaps=function(){probe.projections++;return oldProject()};
          const oldPhysics=physics;
          physics=function(dt){const start=performance.now();oldPhysics(dt);
            probe.physicsMs.push(performance.now()-start)};
          const oldRender=render;
          render=function(){const start=performance.now();oldRender();
            probe.renderAt=performance.now();
            probe.renderMs.push(probe.renderAt-start)};
          const oldFrame=frame;
          frame=function(t){const start=performance.now();oldFrame(t);
            probe.frameMs.push(performance.now()-start)};
          canvas.addEventListener('pointerdown',()=>probe.pointerAt=performance.now(),true);
          last=0;accumulator=0;
        }""")
        # Shallow contact: the ordinary impulse already resolves the overlap.
        # The costly rail/jaw projection has no work to do and must be skipped.
        center=page.evaluate("""() => {
          balls=[makeBall(0,350,285),makeBall(1,350+2*rad-.10,285)];
          shot=null;shooting=false;probe.projections=0;
          physics(STEP);
          return {projections:probe.projections,
            penetration:2*rad-Math.hypot(balls[1].x-balls[0].x,balls[1].y-balls[0].y),
            finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
        }""")
        label=f'{w}x{h}'
        check(label+' resolved central contact skips redundant projection',
            center['projections']==0,center)
        check(label+' central contact remains separated and finite',
            center['penetration']<=.0021 and center['finite'],center)
        # Dense rail-side chain still needs the jaw-aware solver.
        rail=page.evaluate("""() => {
          const x=L+rad+.15,y=285;
          balls=[makeBall(0,850,380)];
          for(let i=0;i<3;i++)balls.push(makeBall(i+1,x+i*(2*rad-1.35),y));
          shot=null;shooting=false;probe.projections=0;
          physics(STEP);
          let overlap=0;
          for(let i=1;i<balls.length;i++)for(let j=i+1;j<balls.length;j++)
            overlap=Math.max(overlap,2*rad-Math.hypot(balls[i].x-balls[j].x,balls[i].y-balls[j].y));
          return {projections:probe.projections,overlap,
            inside:balls.slice(1).every(b=>b.x>=L+rad-1e-5&&b.x<=R-rad+1e-5&&
              b.y>=T+rad-1e-5&&b.y<=B-rad+1e-5)};
        }""")
        check(label+' deep rail chain still invokes projection',rail['projections']>=1,rail)
        check(label+' rail chain stays legal and separated',rail['inside'] and rail['overlap']<=.05,rail)
        # Measure complete active frame CPU, including physics and render.
        active=page.evaluate("""() => {
          rack();showPower(100);aim=0;shoot();
          probe.frameMs=[];probe.physicsMs=[];probe.renderMs=[];probe.projections=0;
          last=0;accumulator=0;
          for(let i=1;i<=72;i++)frame(1000+i*1000/60);
          const stats=values=>{
            const s=values.slice().sort((a,b)=>a-b);
            const p=q=>s.length?s[Math.floor((s.length-1)*q)]:null;
            return {count:s.length,p50:p(.5),p95:p(.95),p99:p(.99),
              totalMs:s.reduce((a,b)=>a+b,0)};
          };
          return {frames:stats(probe.frameMs),physics:stats(probe.physicsMs),
            render:stats(probe.renderMs),projections:probe.projections,
            moved:balls.some(b=>b.id>0&&(Math.hypot(b.vx,b.vy)>.02||b.potted))};
        }""")
        f=active['frames']
        check(label+' 72 full-rack frames profiled',f['count']==72 and active['render']['count']==72,active)
        check(label+' active frame p50/p95/p99 finite and ordered',
            all(isinstance(f[k],(int,float)) and math.isfinite(f[k]) for k in ('p50','p95','p99'))
            and 0<=f['p50']<=f['p95']<=f['p99']<250,active)
        check(label+' real rack impulse transfers to object balls',active['moved'],active)
        # A real pointer event must cause a visible draw on the next frame.
        page.evaluate("""() => {rack();frame(3000);probe.renderAt=0;probe.pointerAt=0}""")
        box=page.locator('#table').bounding_box()
        page.mouse.click(box['x']+box['width']*.64,box['y']+box['height']*.30)
        pointer=page.evaluate("""() => {
          const before=probe.renderMs.length;
          frame(last+1000/60);
          return {pointerAt:probe.pointerAt,renderAt:probe.renderAt,
            redraw:probe.renderMs.length-before,
            measuredDelayMs:probe.renderAt-probe.pointerAt};
        }""")
        check(label+' pointer input repaints next frame',
            pointer['pointerAt']>0 and pointer['redraw']==1 and
            pointer['renderAt']>=pointer['pointerAt'],pointer)
        check(label+' no JavaScript errors',not errors,errors)
        print('PROFILE',label,json.dumps({'center':center,'rail':rail,
            'active':active,'pointer':pointer}),flush=True)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_ACTIVE_FRAME_LATENCY_RESULTS.json').write_text(json.dumps({
 'passed':passed,'total':len(checks),'checks':checks,
 'limitations':'Headless Chromium deterministic CPU timings; no physical Samsung FPS, GC pause measurement or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
