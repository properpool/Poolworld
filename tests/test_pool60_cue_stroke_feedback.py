"""Browser regression for power-readable cue pullback and short visual cue stroke.
A cue stick must communicate selected power and remain visible briefly on impact,
without delaying the authoritative physics shot or changing approved audio.
Chromium-only: does not certify physical Samsung shot feel or frame pacing.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 if not ok:print('FAIL',name,detail,flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,
  executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
  args=['--no-sandbox'])
 for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1000,has_touch=w<1000)
  page.evaluate('window.requestAnimationFrame=()=>0')
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(HTML,wait_until='load')
  tag=f'{w}x{h}'
  geometry=page.evaluate("""() => {
    if(typeof cueTipOffset!=='function'||typeof drawCue!=='function')
      return {available:false};
    return {available:true,
      rest:[15,45,90].map(p=>cueTipOffset(p,null)),
      start:cueTipOffset(90,0),
      contact:cueTipOffset(90,.65),
      finish:cueTipOffset(90,1),
      invalid:[cueTipOffset(-100,null),cueTipOffset(1000,null)],
      valuesFinite:[cueTipOffset(15,null),cueTipOffset(45,null),cueTipOffset(90,null),cueTipOffset(90,.65)].every(Number.isFinite)
    };
  }""")
  check(tag+' dynamic cue geometry available',geometry.get('available'),geometry)
  if geometry.get('available'):
   rest=geometry['rest']
   check(tag+' higher selected power visibly retracts cue',rest[0]>rest[1]>rest[2] and rest[0]-rest[2]>=25,geometry)
   check(tag+' cue starts behind and advances towards cue ball',geometry['start']<geometry['contact'] and geometry['contact']< -12.2,geometry)
   check(tag+' stroke reaches near cue ball without crossing centre',-28<geometry['contact']< -12.2,geometry)
   check(tag+' stroke geometry clamps power and stays finite',geometry['valuesFinite'] and abs(geometry['invalid'][0]-rest[0])<6 and abs(geometry['invalid'][1]-rest[2])<6,geometry)
  visual=page.evaluate("""() => {
    rack();balls=[makeBall(0,300,285)];breakShot=false;aim=0;
    showPower(90);
    const original=drawCue,seen=[];
    if(typeof drawCue!=='function')return {available:false};
    drawCue=function(x,y,a,p,phase){seen.push({x,y,a,p,phase});return original.apply(this,arguments)};
    render();const idle=seen.slice();
    const expected=shotSpeed(90,false),fired=shoot(),velocity=Math.hypot(balls[0].vx,balls[0].vy);
    render();const onShot=seen.slice(idle.length);
    last=1000;frame(1016.6666667);
    const early=seen.slice(idle.length+onShot.length),elapsed=cueStrike&&cueStrike.elapsed;
    for(let i=2;i<=12;i++)frame(1000+i*1000/60);
    const ended=cueStrike===null,lateStart=seen.length;
    render();const late=seen.slice(lateStart);
    const result={available:true,idle,onShot,early,elapsed,ended,late,
      fired,expected,velocity,shooting,shotPower:power,
      cueBall:{x:balls[0].x,y:balls[0].y},
      renderDirty,physicsValid:balls[0].x>300};
    drawCue=original;
    return result;
  }""")
  check(tag+' cue appears in aiming and first shot frame',visual.get('available') and len(visual.get('idle',[]))==1 and len(visual.get('onShot',[]))==1,visual)
  if visual.get('available'):
   check(tag+' first impact cue preserves selected power and original origin',
     len(visual['onShot'])==1 and visual['onShot'][0]['p']==90 and visual['onShot'][0]['x']==300,visual)
   check(tag+' cue stroke advances across actual moving frames',
     len(visual['early'])>=1 and visual['elapsed'] is not None and 0<visual['elapsed']<.16,visual)
   check(tag+' cue stroke expires while physical shot continues',
     visual['ended'] and not visual['late'] and visual['shooting'] and visual['physicsValid'],visual)
   check(tag+' visual feedback never delays or weakens cue-ball impulse',
     visual['fired'] and abs(visual['velocity']-visual['expected'])<1e-8,visual)
   check(tag+' selected shot power survives visual cue animation',
     visual['shotPower']==90,visual)
  check(tag+' no browser errors',not errors,errors)
  page.close()
 browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,
 'limits':'Headless Chromium visual/cue-impulse regression; not physical Samsung or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_CUE_STROKE_RESULTS.json').write_text(json.dumps(result,indent=2))
print('CUE STROKE',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
