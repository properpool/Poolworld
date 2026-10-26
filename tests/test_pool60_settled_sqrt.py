"""Pool World v10.2: settled-shot checks must avoid 16 square roots per rendered frame.

Checks exact 0.022 threshold, potted balls, nonfinite safety and real
headless-Chromium animation callbacks. This is not physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        label=f'{width}x{height}'
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        r=page.evaluate("""() => {
            const originalBalls=balls, originalHypot=Math.hypot;
            const result={};let calls=0;
            try {
                balls=Array.from({length:16},(_,i)=>makeBall(i,220+i*25,200));
                Math.hypot=function(...args){calls++;return originalHypot(...args)};
                for(let i=0;i<240;i++)settled();
                result.staticCalls=calls;
                result.staticRest=settled();
                const probe=(vx,vy,potted=false)=>{
                    for(const b of balls){b.vx=b.vy=0;b.potted=false}
                    balls[5].vx=vx;balls[5].vy=vy;balls[5].potted=potted;
                    return settled();
                };
                result.below=probe(.021999,0);
                result.exact=probe(.022,0);
                result.above=probe(.022001,0);
                result.diagonalBelow=probe(.021/Math.SQRT2,.021/Math.SQRT2);
                result.diagonalAbove=probe(.023/Math.SQRT2,.023/Math.SQRT2);
                result.pottedFast=probe(99,99,true);
                result.nonfinite=probe(NaN,0);
                result.infinity=probe(Infinity,0);
                result.allPotted=(()=>{balls.forEach(b=>{b.potted=true;b.vx=NaN});return settled()})();
                result.totalHypot=calls;
                return result;
            }finally{balls=originalBalls;Math.hypot=originalHypot}
        }""")
        check(label+' 240 settled checks allocate no hypot square roots',
            r['staticCalls']==0,r)
        check(label+' stationary 16-ball rack settled',r['staticRest'],r)
        check(label+' velocity just below 0.022 is settled',r['below'],r)
        check(label+' exact 0.022 is moving',not r['exact'],r)
        check(label+' velocity just above 0.022 is moving',not r['above'],r)
        check(label+' diagonal just below threshold is settled',r['diagonalBelow'],r)
        check(label+' diagonal above threshold is moving',not r['diagonalAbove'],r)
        check(label+' potted fast ball is ignored',r['pottedFast'],r)
        check(label+' NaN nonpotted velocity never settles',not r['nonfinite'],r)
        check(label+' infinite nonpotted velocity never settles',not r['infinity'],r)
        check(label+' all potted balls are settled',r['allPotted'],r)
        check(label+' no hypot in any settled-only fixture',r['totalHypot']==0,r)
        check(label+' browser has no script errors',not errors,errors)
        print('SETTLED_SQRT_DIAGNOSTIC',label,json.dumps(r),flush=True)
        page.close()
        live=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        live.set_content(HTML,wait_until='load')
        live.evaluate("""() => {
            rack();showPower(100);aim=0;shoot();
            window.__diag={times:[],cpu:[]};
            const oldFrame=frame;
            frame=function(t){
                const start=performance.now();
                oldFrame(t);
                __diag.times.push(t);
                __diag.cpu.push(performance.now()-start);
            };
        }""")
        live.wait_for_timeout(650)
        d=live.evaluate("""() => {
            const t=__diag.times, c=__diag.cpu;
            const gaps=t.slice(1).map((v,i)=>v-t[i]);
            const percentile=(a,q)=>{
                const sorted=[...a].sort((x,y)=>x-y);
                return sorted[Math.floor((sorted.length-1)*q)]??null;
            };
            return {callbacks:t.length,p95Gap:percentile(gaps,.95),
                p99Gap:percentile(gaps,.99),
                p95CPU:percentile(c,.95),p99CPU:percentile(c,.99),
                active:shooting};
        }""")
        check(label+' real Chromium moving-rack rAF samples',
            d['callbacks']>=12,d)
        check(label+' real Chromium p95/p99 gap and CPU finite',
            all(isinstance(d[k],(int,float)) and math.isfinite(d[k])
                for k in ('p95Gap','p99Gap','p95CPU','p99CPU')),d)
        print('REAL_MOVING_RACK_RAF',label,json.dumps(d),flush=True)
        live.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SETTLED_SQRT_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
        'limitations':'Headless Chromium only, not Samsung FPS, touch or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
