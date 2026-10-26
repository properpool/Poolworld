"""High-speed grazing-ball contact must transfer momentum, not merely mark a foul.

A cue can enter and leave the 2*rad contact circle between two 120 Hz ticks
while both endpoint positions are non-overlapping. The real browser executes
the unmodified physics() for each fixture. No physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok:print('FAIL',name,details,flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        prefix=f'{w}x{h}'
        for direction in (-1,1):
            for side in (-1,1):
                data=page.evaluate("""([direction,side])=>{
                  const x=400,y=285;
                  const cue=makeBall(0,x-direction*2.43,y+side*24.35);
                  const obj=makeBall(1,x,y);
                  cue.vx=direction*9.75;balls=[cue,obj];
                  shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
                    pocketed:[],scratch:false,targetEight:false};
                  shooting=true;breakShot=false;accumulator=0;events.length=0;
                  const before=Math.hypot(cue.x-obj.x,cue.y-obj.y);
                  const energy=cue.vx**2+cue.vy**2+obj.vx**2+obj.vy**2;
                  physics(STEP);
                  const after=Math.hypot(cue.x-obj.x,cue.y-obj.y);
                  const speed=Math.hypot(obj.vx,obj.vy);
                  const energyAfter=cue.vx**2+cue.vy**2+obj.vx**2+obj.vy**2
                    +.4*(cue.spin**2+obj.spin**2);
                  return {before,after,speed,firstHit:shot.firstHit,
                    energy,energyAfter,positions:[cue.x,cue.y,obj.x,obj.y],
                    velocities:[cue.vx,cue.vy,obj.vx,obj.vy]};
                }""",[direction,side])
                label=f'{prefix} cue grazing dir={direction} side={side}'
                check(label+' both endpoints are outside overlap',data['before']>24.4 and data['after']>24.4,data)
                check(label+' real object receives grazing impulse',data['speed']>.05,data)
                check(label+' cue first contact is physical',data['firstHit']==1 and data['speed']>.05,data)
                check(label+' energy finite and nonincreasing',
                    all(math.isfinite(v) for v in data['positions']+data['velocities'])
                    and data['energyAfter']<=data['energy']+1e-6,data)
        for clearance in (24.45,25.5):
            data=page.evaluate("""clearance=>{
              const cue=makeBall(0,397.57,285+clearance),obj=makeBall(1,400,285);
              cue.vx=9.75;balls=[cue,obj];
              shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,
                pocketed:[],scratch:false,targetEight:false};
              shooting=true;breakShot=false;events.length=0;
              physics(STEP);
              return {speed:Math.hypot(obj.vx,obj.vy),firstHit:shot.firstHit,
                separation:Math.hypot(obj.x-cue.x,obj.y-cue.y)};
            }""",clearance)
            check(f'{prefix} true near miss {clearance} has no ghost impulse',
                data['speed']<1e-10 and data['firstHit'] is None,data)
        obj=page.evaluate("""()=>{
          const a=makeBall(1,397.57,309.35),b=makeBall(2,400,285);
          a.vx=9.75;balls=[a,b];shot=null;shooting=true;events.length=0;
          physics(STEP);
          return {speed:Math.hypot(b.vx,b.vy),
            finite:[a.x,a.y,b.x,b.y,a.vx,a.vy,b.vx,b.vy].every(Number.isFinite)};
        }""")
        check(f'{prefix} object-object grazing collision transfers momentum',
            obj['speed']>.05 and obj['finite'],obj)
        check(f'{prefix} no browser exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SWEPT_GRAZE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Real Chromium 120 Hz physics ticks, not physical Samsung/human acceptance.'
},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
