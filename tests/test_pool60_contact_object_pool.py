"""Pool World v9.6 contact-object lifetime and active-break regression.

A reusable contacts *array* still allocated one {a,b,t} object for each
overlap on every 120Hz physics tick. These tests count distinct object
identities, check reuse after zero-contact gaps, and retain collision checks.
Chromium is not a physical Samsung Galaxy A37 acceptance test.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        label=f'{w}x{h}'
        result=page.evaluate("""() => {
          const track=(run)=>{
            const seen=new Set();
            let total=0,peak=0;
            const original=contacts.push;
            contacts.push=function(...items){
              for(const item of items){seen.add(item);total++}
              return original.apply(this,items);
            };
            try{run(()=>{peak=Math.max(peak,contacts.length)})}
            finally{contacts.push=original}
            return {total,unique:seen.size,peak,reused:total-seen.size};
          };
          const repeat=track(()=>{
            for(let n=0;n<64;n++){
              balls=[makeBall(0,400,285),makeBall(1,400+2*rad-.28,285)];
              shot=null;shooting=false;physics(STEP);
            }
          });
          repeat.finite=balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite));
          repeat.array=Array.isArray(contacts)&&typeof contacts.sort==='function';
          const cluster=track(()=>{
            for(let n=0;n<40;n++){
              balls=[makeBall(0,410,270),
                makeBall(1,410+rad*1.6,270),
                makeBall(2,410+rad*.8,270+rad*1.3)];
              shot=null;shooting=false;physics(STEP);
            }
          });
          cluster.finite=balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin].every(Number.isFinite));
          cluster.pairs=contacts.length;
          // The pool must survive a quiet tick and be reused on the next hit.
          balls=[makeBall(0,400,285),makeBall(1,400+2*rad-.28,285)];
          physics(STEP);const first=contacts[0];
          balls=[makeBall(0,300,285),makeBall(1,800,285)];
          physics(STEP);const quiet=contacts.length===0;
          balls=[makeBall(0,400,285),makeBall(1,400+2*rad-.28,285)];
          physics(STEP);const gap={quiet,reused:contacts[0]===first,contact:contacts.length};
          // A natural rack should use at most the peak simultaneous number
          // of pooled objects, not allocate new objects on every contact.
          rack();showPower(100);aim=0;shoot();
          last=0;accumulator=0;
          const full=track((sample)=>{
            for(let i=0;i<72;i++){frame((i+1)*1000/60);sample()}
          });
          full.finite=balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite));
          full.valid=balls.every(b=>b.potted||
            b.x>=L+rad-3&&b.x<=R-rad+3&&b.y>=T+rad-3&&b.y<=B-rad+3);
          full.shotStarted=!!history;
          return {repeat,cluster,gap,full};
        }""")
        repeat=result['repeat'];cluster=result['cluster']
        gap=result['gap'];full=result['full']
        check(label+' 64 overlapping pair contacts observed',repeat['total']>=64,repeat)
        check(label+' overlapping pair contact object reused',repeat['unique']<=2,repeat)
        check(label+' repeated contacts avoid at least 62 allocations',repeat['reused']>=62,repeat)
        check(label+' pair physics stays finite',repeat['finite'],repeat)
        check(label+' legacy contacts array interface preserved',repeat['array'],repeat)
        check(label+' 40 three-ball clusters produce multiple contacts',cluster['total']>=80,cluster)
        check(label+' cluster contact objects reused',cluster['unique']<=3,cluster)
        check(label+' three-ball contact solver stays finite',cluster['finite'],cluster)
        check(label+' quiet physics tick empties active contact list',gap['quiet'],gap)
        check(label+' contact objects reused after quiet gap',gap['reused'] and gap['contact']>=1,gap)
        check(label+' natural full-rack shot launched',full['shotStarted'],full)
        check(label+' natural full-rack collisions recorded',full['total']>=1,full)
        check(label+' full-rack contact identities bounded by peak',full['unique']<=full['peak'],full)
        check(label+' full-rack positions and velocities finite',full['finite'],full)
        check(label+' full-rack ball positions remain legal',full['valid'],full)
        check(label+' no browser exceptions',not errors,errors)
        print('CONTACT_POOL_DIAGNOSTIC',label,json.dumps(result),flush=True)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_CONTACT_POOL_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Headless Chromium only; not real Samsung FPS, touch latency or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
