"""Multi-contact solver allocation regression and actual Chromium rAF diagnostics.

The browser rAF measurements are observational: they are not physical Samsung
Galaxy A37 frame-rate, GPU latency or touch/display acceptance measurements.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, statistics, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, ok, detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:
        print('FAIL',name,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for scenario in ('chain','angled','reversed'):
            data=page.evaluate("""scenario=>{
                shot=null;
                let a,b,c;
                if(scenario==='angled'){
                    a=makeBall(0,350,280);
                    b=makeBall(1,373,280);
                    c=makeBall(9,390,296);
                    a.vx=6;a.vy=.4;b.vx=1;b.vy=.2;c.vx=0;c.vy=0;
                }else{
                    a=makeBall(0,350,285);
                    b=makeBall(1,373,285);
                    c=makeBall(9,396,285);
                    a.vx=6;b.vx=1;c.vx=0;
                }
                const ordered=scenario==='reversed'?[{a:b,b:c},{a,b}]:[{a,b},{a:b,b:c}];
                const kinetic=()=>[a,b,c].reduce((e,p)=>e+p.vx*p.vx+p.vy*p.vy+.4*p.spin*p.spin,0);
                const before=kinetic();
                const originalMap=Array.prototype.map;
                let maps=0;
                Array.prototype.map=function(...args){maps++;return originalMap.apply(this,args)};
                let solved=false;
                try{solved=resolveSimultaneousContacts(ordered)}
                finally{Array.prototype.map=originalMap}
                return {maps,solved,before,after:kinetic(),
                    velocities:[a,b,c].map(p=>[p.vx,p.vy]),
                    positions:[a,b,c].map(p=>[p.x,p.y])};
            }""",scenario)
            label=f'{width}x{height} {scenario}'
            check(label+' simultaneous contact solved',data['solved'],data)
            check(label+' no 32-per-iteration array maps',data['maps']<=6,data)
            check(label+' finite velocity and position',
                all(math.isfinite(v) for pair in data['velocities']+data['positions'] for v in pair),data)
            check(label+' bounded contact kinetic energy',
                data['after']<=data['before']+1e-7 and data['after']>=0,data)
        check(f'{width}x{height} no browser exceptions',not errors,errors)
        page.close()

        # Let Chromium schedule its own rAF callbacks instead of injecting
        # synthetic timestamps. This is a diagnostic, not an FPS pass gate.
        live=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        live_errors=[]
        live.on('pageerror',lambda err:live_errors.append(str(err)))
        live.set_content(HTML,wait_until='load')
        metrics=live.evaluate("""async()=>{
            rack();aim=0;showPower(100);shoot();
            const times=[],cpu=[];
            const originalFrame=frame;
            frame=function(t){
                const start=performance.now();
                originalFrame(t);
                times.push(t);
                cpu.push(performance.now()-start);
            };
            await new Promise(resolve=>setTimeout(resolve,1400));
            frame=originalFrame;
            const gaps=times.slice(1).map((t,i)=>t-times[i]);
            const sorted=[...gaps].sort((a,b)=>a-b);
            const costs=[...cpu].sort((a,b)=>a-b);
            const p=(a,q)=>a.length?a[Math.min(a.length-1,Math.floor(q*(a.length-1)))]:null;
            return {frames:times.length,active:shooting,
                moving:balls.filter(b=>!b.potted&&Math.hypot(b.vx,b.vy)>.022).length,
                gapP50:p(sorted,.5),gapP95:p(sorted,.95),gapP99:p(sorted,.99),
                cpuP50:p(costs,.5),cpuP95:p(costs,.95),cpuP99:p(costs,.99),
                monotonic:gaps.every(x=>x>0)};
        }""")
        label=f'{width}x{height} actual Chromium rAF'
        check(label+' callbacks observed',metrics['frames']>=10,metrics)
        check(label+' monotonic timestamps',metrics['monotonic'],metrics)
        check(label+' recorded frame CPU distribution',
            metrics['cpuP95'] is not None and math.isfinite(metrics['cpuP95']),metrics)
        check(label+' no browser exceptions',not live_errors,live_errors)
        print('rAF_DIAGNOSTIC',label,json.dumps(metrics),flush=True)
        live.close()
    browser.close()

output={'checks':checks,'total':len(checks),'passed':sum(c['passed'] for c in checks)}
(ROOT/'POOL_WORLD_6.0_MULTICONTACT_RESULTS.json').write_text(json.dumps(output,indent=2))
print(f"Multi-contact allocations and real Chromium rAF: {output['passed']}/{output['total']} checks",flush=True)
if output['passed']!=output['total']:
    sys.exit(1)
