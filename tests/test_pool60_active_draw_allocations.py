"""Pool World v9.5 active physics/ball-draw allocation and frame-pacing regression.

Counts observable temporary array iterator usage and marker output allocations
during a full-rack break. Real Chromium rAF metrics are diagnostics only:
they are not Samsung Galaxy A37 GPU/display latency or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, ok, detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        data=page.evaluate("""() => {
            const origIter=Array.prototype[Symbol.iterator], origRoll=rollMarker;
            let axisIterators=0, markerAllocated=0, markerReused=0;
            Array.prototype[Symbol.iterator]=function(...args){
                if(this.length===2&&this[0]==='x'&&this[1]==='y')axisIterators++;
                return origIter.apply(this,args);
            };
            rollMarker=function(q,p,out){
                if(out)markerReused++;else markerAllocated++;
                return origRoll(q,p,out);
            };
            let result;
            try{
                const q=[Math.cos(.27),0,Math.sin(.27),0],p=[0,1,0],out=[NaN,NaN,NaN];
                const expected=origRoll(q,p);
                const returned=rollMarker(q,p,out);
                const scratchIdentity=returned===out;
                const scratchMath=out.every((v,i)=>Number.isFinite(v)&&Math.abs(v-expected[i])<1e-12);
                const legacy=rollMarker(q,p);
                const legacyDistinct=legacy!==out&&legacy!==p&&legacy.every((v,i)=>Math.abs(v-expected[i])<1e-12);
                axisIterators=0;markerAllocated=0;markerReused=0;
                rack();aim=0;showPower(100);shoot();
                last=0;accumulator=0;
                for(let i=1;i<=72;i++)frame(1000+i*1000/60);
                const moving=balls.some(b=>b.id>0&&(b.potted||Math.hypot(b.vx,b.vy)>.02));
                const finite=balls.every(b=>[b.x,b.y,b.vx,b.vy,...b.rollQ].every(Number.isFinite));
                const beforeRestore=history&&history.balls.length===16;
                restore(history);
                const restored=balls.length===16&&balls.every(b=>Math.hypot(b.vx,b.vy)<1e-12);
                result={axisIterators,markerAllocated,markerReused,scratchIdentity,scratchMath,
                    legacyDistinct,moving,finite,beforeRestore,restored};
            }finally{
                Array.prototype[Symbol.iterator]=origIter;
                rollMarker=origRoll;
            }
            return result;
        }""")
        label=f'{width}x{height}'
        check(label+' full rack break transfers momentum',data['moving'],data)
        check(label+' active positions and quaternions finite',data['finite'],data)
        check(label+' full rack retry snapshot intact',data['beforeRestore'] and data['restored'],data)
        check(label+' rail axes do not create per-ball iterator arrays',data['axisIterators']==0,data)
        check(label+' ball marker output arrays eliminated from active drawing',data['markerAllocated']==0,data)
        check(label+' live stripe and cue marks use reusable marker output',data['markerReused']>=400,data)
        check(label+' supplied rollMarker output reused by identity',data['scratchIdentity'],data)
        check(label+' scratch rotation matches original quaternion math',data['scratchMath'],data)
        check(label+' legacy rollMarker API returns correct independent vector',data['legacyDistinct'],data)
        check(label+' no JavaScript exceptions',not errors,errors)
        print('ACTIVE_ALLOCATION_PROFILE',label,json.dumps(data),flush=True)
        page.close()

        # Genuine browser-scheduled rAF, with moving balls. No synthetic clock.
        live=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        live_errors=[]
        live.on('pageerror',lambda error:live_errors.append(str(error)))
        live.set_content(HTML,wait_until='load')
        raf=live.evaluate("""async () => {
            rack();aim=0;showPower(100);shoot();
            const times=[],cpu=[];
            const original=frame;
            frame=function(t){
                const start=performance.now();original(t);
                times.push(t);cpu.push(performance.now()-start);
            };
            await new Promise(resolve=>setTimeout(resolve,1000));
            frame=original;
            const percentile=(values,p)=>{
                const a=values.slice().sort((x,y)=>x-y);
                return a.length?a[Math.floor((a.length-1)*p)]:null;
            };
            const gaps=times.slice(1).map((t,i)=>t-times[i]);
            return {frames:times.length,gapP50:percentile(gaps,.5),
                gapP95:percentile(gaps,.95),gapP99:percentile(gaps,.99),
                cpuP50:percentile(cpu,.5),cpuP95:percentile(cpu,.95),
                cpuP99:percentile(cpu,.99),monotonic:gaps.every(x=>x>0)};
        }""")
        check(label+' genuine active rAF callbacks recorded',raf['frames']>=10,raf)
        check(label+' active frame and CPU p95/p99 measurable',
            raf['monotonic'] and all(isinstance(raf[k],(int,float)) and math.isfinite(raf[k])
                for k in ('gapP95','gapP99','cpuP95','cpuP99')),raf)
        check(label+' real rAF has no JavaScript exceptions',not live_errors,live_errors)
        print('ACTIVE_RAF_DIAGNOSTIC',label,json.dumps(raf),flush=True)
        live.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_ACTIVE_DRAW_ALLOC_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Headless Chromium allocation/CPU diagnostics, not Samsung device FPS or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
