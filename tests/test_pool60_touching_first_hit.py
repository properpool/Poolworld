"""A resting cue beside another ball must not get a phantom first contact.

The earliest-contact sweep used to mark any pre-existing tiny overlap as a
first hit even when the balls separated, slid apart, or never exchanged
momentum. This changes foul adjudication and can mask the real first hit.
Run the unmodified browser physics at four screen sizes. Not phone acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys
ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / 'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks = []
def check(name, ok, data):
    checks.append({'name': name, 'passed': bool(ok), 'details': data})
    if not ok:
        print('FAIL', name, data, flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page = browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000, has_touch=w<1000)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML, wait_until='load')
        for direction in (-1,1):
            for motion in ('away','still','tangent','sliding_out','object_away','toward','real_other'):
                data = page.evaluate("""([direction,motion])=>{
                  const cue=makeBall(0,400,285);
                  const neighbor=makeBall(1,400+direction*(2*rad-.001),285);
                  const other=makeBall(2,400-direction*40,285);
                  balls=motion==='real_other'?[cue,neighbor,other]:[cue,neighbor];
                  shot={player:1,breakShot:false,firstHit:null,
                    railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                  shooting=true;breakShot=false;events.length=0;accumulator=0;
                  if(motion==='away')cue.vx=-direction*8;
                  if(motion==='still')cue.vx=0;
                  if(motion==='tangent')cue.vy=8;
                  if(motion==='sliding_out'){cue.vx=direction*.04;cue.vy=8;}
                  if(motion==='object_away')neighbor.vx=direction*8;
                  if(motion==='toward')cue.vx=direction*8;
                  if(motion==='real_other')cue.vx=-direction*9;
                  const before=Math.hypot(cue.x-neighbor.x,cue.y-neighbor.y);
                  for(let i=0;i<(motion==='real_other'?8:1);i++)physics(STEP);
                  return {firstHit:shot.firstHit,before,
                    neighborSpeed:Math.hypot(neighbor.vx,neighbor.vy),
                    otherSpeed:motion==='real_other'?Math.hypot(other.vx,other.vy):0,
                    cueX:cue.x,neighborX:neighbor.x,
                    finite:balls.every(b=>[b.x,b.y,b.vx,b.vy].every(Number.isFinite))};
                }""",[direction,motion])
                label=f'{w}x{h} direction={direction} {motion}'
                check(label+' starts with sub-tolerance resting contact',
                    abs(data['before']-(24.4-.001))<1e-5,data)
                if motion in ('away','still','tangent','sliding_out','object_away'):
                    check(label+' no phantom cue first hit',
                        data['firstHit'] is None,data)
                    if motion != 'object_away':
                        check(label+' no artificial object impulse',
                            data['neighborSpeed']<1e-8,data)
                elif motion=='toward':
                    check(label+' real closing impulse is recorded',
                        data['firstHit']==1 and data['neighborSpeed']>.1,data)
                else:
                    check(label+' actual other ball is first contact',
                        data['firstHit']==2 and data['otherSpeed']>.1
                        and data['neighborSpeed']<1e-8,data)
                check(label+' finite physics',data['finite'],data)
        check(f'{w}x{h} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_TOUCHING_FIRST_HIT_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limitations':'Chromium 120Hz physics, not physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
