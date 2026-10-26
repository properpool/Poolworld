"""Pool World v9.8 sustained low-FPS debt and real Chromium input/rAF diagnostics.

Transient 150ms hitches must preserve physics time, but sustained low frame
rates must not accumulate seconds of stale catch-up that fast-forwards shots
after the device recovers. The live rAF/input measurements use Chromium, NOT
the physical Samsung display, GPU, or touchscreen.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, ok, detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:
        print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(
        headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        label=f'{width}x{height}'
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        data=page.evaluate("""() => {
            // Instrument the scheduler, keeping a moving cue ball without
            // allowing a shot to finish during the prolonged 10fps fixture.
            const originalPhysics=physics;
            let ticks=0;
            physics=function(dt){ticks++};
            try {
                rack();aim=0;showPower(100);shoot();
                last=1000;accumulator=0;
                const perFrame=[];
                for(let i=1;i<=80;i++){
                    const before=ticks;
                    frame(1000+i*100);
                    perFrame.push(ticks-before);
                }
                const slow={debt:accumulator,ticks,
                    maxTicks:Math.max(...perFrame),active:shooting,
                    finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                const recovery=[];
                for(let i=1;i<=30;i++){
                    const before=ticks;
                    frame(9000+i*1000/60);
                    recovery.push(ticks-before);
                }
                const recovered={debt:accumulator,
                    maxTicks:Math.max(...recovery),ticks,
                    active:shooting};
                rack();frame(15000);
                const idleDebt=accumulator;
                showPower(70);aim=0;shoot();
                const before=ticks;
                frame(15000+1000/60);
                const restart={idleDebt,ticks:ticks-before,active:shooting};
                return {slow,recovered,restart};
            } finally {physics=originalPhysics}
        }""")
        slow=data['slow'];recovered=data['recovered'];restart=data['restart']
        check(label+' sustained low-fps shot remains finite and active',
            slow['active'] and slow['finite'],slow)
        check(label+' 10fps callback physics remains capped at eight ticks',
            slow['maxTicks']<=8 and slow['ticks']>=600,slow)
        check(label+' prolonged 10fps never banks more than 250ms debt',
            slow['debt']<=.25+1e-6,slow)
        check(label+' recovered 60fps clears stale debt within 30 frames',
            recovered['debt']<.03 and recovered['active'],recovered)
        check(label+' recovery does not burst beyond eight physics ticks',
            recovered['maxTicks']<=8,recovered)
        check(label+' idle gap clears accumulated shot debt',
            restart['idleDebt']<1/120+1e-6,restart)
        check(label+' next shot after idle starts at normal cadence',
            restart['active'] and 1<=restart['ticks']<=3,restart)
        check(label+' synthetic browser JavaScript has no errors',
            not errors,errors)
        page.close()

        # Actual Chromium requestAnimationFrame callbacks and browser mouse
        # pointer events, rather than manually advanced frame timestamps.
        live=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        live_errors=[]
        live.on('pageerror',lambda error:live_errors.append(str(error)))
        live.set_content(HTML,wait_until='load')
        live.evaluate("""() => {
            rack();showPower(100);aim=0;shoot();
            window.__live={times:[],costs:[],eventAt:0,renderAt:0};
            const originalFrame=frame;
            frame=function(t){
                const start=performance.now();
                originalFrame(t);
                window.__live.times.push(t);
                window.__live.costs.push(performance.now()-start);
            };
        }""")
        live.wait_for_timeout(1050)
        metrics=live.evaluate("""() => {
            const m=window.__live;
            const gaps=m.times.slice(1).map((t,i)=>t-m.times[i]);
            const pct=(arr,q)=>{
                if(!arr.length)return null;
                const sorted=[...arr].sort((a,b)=>a-b);
                return sorted[Math.floor((sorted.length-1)*q)];
            };
            return {callbacks:m.times.length,
                gapP95:pct(gaps,.95),gapP99:pct(gaps,.99),
                cpuP95:pct(m.costs,.95),cpuP99:pct(m.costs,.99),
                monotonic:gaps.every(x=>x>0),active:shooting};
        }""")
        check(label+' actual Chromium rAF callback sampling',metrics['callbacks']>=12,metrics)
        check(label+' actual Chromium frame gaps monotonic',
            metrics['monotonic'],metrics)
        check(label+' real browser p95/p99 frame CPU metrics finite',
            all(isinstance(metrics[k],(int,float)) and math.isfinite(metrics[k])
                for k in ('cpuP95','cpuP99','gapP95','gapP99')),metrics)
        print('REAL_RAF_DIAGNOSTIC',label,json.dumps(metrics),flush=True)

        live.evaluate("""() => {
            rack();
            window.__live.eventAt=0;window.__live.renderAt=0;
            const originalRender=render;
            render=function(){
                if(window.__live.eventAt>0 && !window.__live.renderAt)
                    window.__live.renderAt=performance.now();
                return originalRender();
            };
            canvas.addEventListener('pointermove',e=>{
                if(dragAim&&e.pointerId===aimPointer){
                    window.__live.eventAt=performance.now();
                    window.__live.renderAt=0;
                }
            },true);
        }""")
        box=live.locator('canvas').bounding_box()
        startx=box['x']+box['width']*.68
        starty=box['y']+box['height']*.3
        endx=box['x']+box['width']*.83
        endy=box['y']+box['height']*.72
        live.mouse.move(startx,starty)
        live.mouse.down()
        live.mouse.move(endx,endy)
        try:
            live.wait_for_function(
                'window.__live.eventAt>0 && window.__live.renderAt>0',
                timeout=3000)
        except Exception:
            pass
        live.mouse.up()
        response=live.evaluate("""() => ({
            eventAt:window.__live.eventAt,renderAt:window.__live.renderAt,
            delay:window.__live.renderAt-window.__live.eventAt,
            aim,finite:Number.isFinite(aim),shooting
        })""")
        check(label+' actual browser pointermove event observed',
            response['eventAt']>0,response)
        check(label+' pointer event triggers a subsequent canvas redraw',
            response['renderAt']>=response['eventAt']>0,response)
        check(label+' event-to-canvas-render-start under 250ms in Chromium',
            0<=response['delay']<250,response)
        check(label+' browser aim changes to finite direction',
            response['finite'] and abs(response['aim'])>.05
            and not response['shooting'],response)
        check(label+' real browser has no JavaScript errors',
            not live_errors,live_errors)
        print('BROWSER_POINTER_TO_RENDER_DIAGNOSTIC',label,
            json.dumps(response),flush=True)
        live.close()
    browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),
    'checks':checks,
    'limitations':'Headless Chromium rAF and mouse-to-canvas-render-start only; not Samsung touchscreen or actual display-photon latency.'}
(ROOT/'POOL_WORLD_6.0_SUSTAINED_FRAME_RESULTS.json').write_text(
    json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:
    sys.exit(1)
