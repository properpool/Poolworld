"""Pool World v9.9: audio-event allocation regression across active 120Hz physics.
Check repeated rail and pocket events reuse the same two-element records while
retaining event type, intensity, frame clearing, and a natural break sequence.
Browser checks are not physical Samsung Galaxy A37 acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,detail,flush=True)

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
        label=f'{w}x{h}'
        result=page.evaluate("""() => {
          soundOn=false;
          const track=(fn)=>{
            const seen=new Set();let total=0,peak=0,valid=true;
            const push=events.push;
            events.push=function(...items){
              for(const item of items){
                seen.add(item);total++;
                valid=valid&&Array.isArray(item)&&item.length===2&&
                  typeof item[0]==='string'&&Number.isFinite(item[1]);
              }
              const count=push.apply(this,items);
              peak=Math.max(peak,this.length);
              return count;
            };
            let detail;
            try{detail=fn()}finally{events.push=push}
            return {total,unique:seen.size,peak,reused:total-seen.size,valid,detail};
          };
          const rail=track(()=>{
            let valid=true;
            for(let i=0;i<64;i++){
              events.length=0;
              const b=makeBall(1,300,285);b.vx=-2;b.vy=0;
              const hit=reflectCushion(b,1,0,.78,.04);
              valid=valid&&hit&&events.length===1&&events[0][0]==='rail'&&
                events[0][1]>.3&&events[0][1]<.5&&b.vx>0;
            }
            return {valid};
          });
          const pocket=track(()=>{
            let valid=true;
            for(let i=0;i<64;i++){
              events.length=0;
              const b=makeBall(3,400,285);pocketBall(b);
              valid=valid&&b.potted&&events.length===1&&
                events[0][0]==='pocket'&&events[0][1]===.85;
            }
            return {valid};
          });
          const mixed=track(()=>{
            let valid=true;
            for(let i=0;i<40;i++){
              events.length=0;
              const b=makeBall(2,300,285);b.vx=-2;
              reflectCushion(b,1,0,.78,.04);
              pocketBall(makeBall(4,420,285));
              valid=valid&&events.length===2&&
                events[0][0]==='rail'&&events[1][0]==='pocket'&&
                events[0]!==events[1];
            }
            return {valid};
          });
          events.length=0;rack();showPower(100);aim=0;
          const launched=shoot();last=0;accumulator=0;
          const full=track(()=>{
            for(let i=0;i<72;i++)frame((i+1)*1000/60);
            return {finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite)),
              legal:balls.every(b=>b.potted||(b.x>=L+rad-3&&b.x<=R-rad+3&&
                b.y>=T+rad-3&&b.y<=B-rad+3)),
              launched,shotRecorded:!!history};
          });
          return {rail,pocket,mixed,full};
        }""")
        rail=result['rail'];pocket=result['pocket'];mixed=result['mixed'];full=result['full']
        check(label+' rail collisions produce 64 sound events',rail['total']==64,rail)
        check(label+' rail sound records are reused',rail['unique']<=1,rail)
        check(label+' rail rebound event and impulse preserved',rail['detail']['valid'],rail)
        check(label+' pocket captures produce 64 sound events',pocket['total']==64,pocket)
        check(label+' pocket sound records are reused',pocket['unique']<=1,pocket)
        check(label+' pocket sound type and level preserved',pocket['detail']['valid'],pocket)
        check(label+' mixed two-event frames recorded',mixed['total']==80 and mixed['peak']==2,mixed)
        check(label+' mixed sound records bounded by simultaneous peak',mixed['unique']<=2,mixed)
        check(label+' simultaneous sound events stay distinct',mixed['detail']['valid'],mixed)
        check(label+' all event payloads keep legacy two-element array API',
              rail['valid'] and pocket['valid'] and mixed['valid'] and full['valid'],result)
        check(label+' natural full rack has finite legal physics',
              full['detail']['finite'] and full['detail']['legal'] and full['detail']['shotRecorded'],full)
        check(label+' no browser exceptions',not errors,errors)
        print('SOUND_EVENT_DIAGNOSTIC',label,json.dumps(result),flush=True)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SOUND_EVENT_RESULTS.json').write_text(json.dumps({
  'passed':passed,'total':len(checks),'checks':checks,
  'limitations':'Headless Chromium; not real Samsung audio latency, FPS or human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
