"""Active 120Hz contact-list reuse and clustered collision regression.

Records the identity of arrays passed to the real contact-sort comparator
across a moving full rack, and checks that clustered simultaneous-contact
batches are passed without allocating temporary slices. Chromium diagnostics
do not constitute Samsung Galaxy A37 performance or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name, passed, detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed:
        print('FAIL',name,detail,flush=True)

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
            const realSort=Array.prototype.sort,realSlice=Array.prototype.slice;
            const contactArrays=new Set();
            let sortCalls=0,contactBatchSlices=0;
            Array.prototype.sort=function(compare){
                if(compare&&String(compare).includes('u.t-v.t')){
                    contactArrays.add(this);sortCalls++;
                }
                return realSort.call(this,compare);
            };
            Array.prototype.slice=function(...args){
                if(contactArrays.has(this))contactBatchSlices++;
                return realSlice.apply(this,args);
            };
            let full,cluster;
            try{
                rack();aim=0;showPower(100);shoot();
                last=0;accumulator=0;
                const t0=performance.now();
                for(let i=1;i<=72;i++)frame(1000+i*1000/60);
                const elapsed=performance.now()-t0;
                full={sortCalls,distinctArrays:contactArrays.size,
                    batchSlices:contactBatchSlices,elapsedMs:elapsed,
                    moving:balls.some(b=>b.id>0&&(b.potted||Math.hypot(b.vx,b.vy)>.02))};
                const priorSlices=contactBatchSlices;
                shot=null;shooting=false;
                balls=[makeBall(0,350,285),makeBall(1,370,276),makeBall(9,370,294)];
                balls[0].vx=6;
                const energyBefore=balls.reduce((e,b)=>e+b.vx*b.vx+b.vy*b.vy,0);
                physics(STEP);
                const energyAfter=balls.reduce((e,b)=>e+b.vx*b.vx+b.vy*b.vy,0);
                cluster={batchSlices:contactBatchSlices-priorSlices,
                    energyBefore,energyAfter,
                    objectMoved:balls.slice(1).some(b=>Math.hypot(b.vx,b.vy)>.05),
                    finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
            }finally{
                Array.prototype.sort=realSort;
                Array.prototype.slice=realSlice;
            }
            return {full,cluster};
        }""")
        label=f'{width}x{height}'
        full,cluster=data['full'],data['cluster']
        check(label+' full-rack physics ticks instrumented',
            full['sortCalls']>=100,full)
        check(label+' contact sort reuses one list instead of allocating each tick',
            full['distinctArrays']<=1,full)
        check(label+' clustered contacts passed without temporary batch slice',
            cluster['batchSlices']==0,cluster)
        check(label+' clustered impulse transfers to object balls',
            cluster['objectMoved'],cluster)
        check(label+' clustered collision remains finite and energy-bounded',
            cluster['finite'] and cluster['energyAfter']<=cluster['energyBefore']+1e-6,cluster)
        check(label+' full-rack break moves object balls',
            full['moving'],full)
        check(label+' no browser exceptions',not errors,errors)
        print('CONTACT_PROFILE',label,json.dumps(data),flush=True)
        page.close()
    browser.close()

passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_CONTACT_REUSE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Headless Chromium allocation identities, not physical phone frame pacing or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
