"""Browser render cost regression: a moving full rack must not allocate per-ball gradients each frame.
Profiles render CPU distributions and checks real pointer-to-frame visual updates.
Measurements are headless Chromium only, NOT physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,statistics,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 if not ok: print('FAIL',name,detail,flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<1000,has_touch=w<1000)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.evaluate('window.requestAnimationFrame=()=>0')
  page.set_content(HTML,wait_until='load')
  page.evaluate("""() => {
   window.perf={radial:0,linear:0,draws:0,times:[]};
   const proto=CanvasRenderingContext2D.prototype;
   const radial=proto.createRadialGradient,linear=proto.createLinearGradient;
   proto.createRadialGradient=function(...args){perf.radial++;return radial.apply(this,args)};
   proto.createLinearGradient=function(...args){perf.linear++;return linear.apply(this,args)};
   const orig=render;
   render=function(){const t=performance.now();orig();perf.draws++;perf.times.push(performance.now()-t)};
   last=0;accumulator=0;
  }""")
  # Full-rack shot: exercise visible 16-ball drawing over 48 frames.
  shot=page.evaluate("""() => {
   showPower(100);aim=0;shoot();
   for(let i=1;i<=48;i++)frame(1000+i*1000/60);
   const times=perf.times.slice().sort((a,b)=>a-b);
   const p=q=>times[Math.min(times.length-1,Math.floor(q*(times.length-1)))];
   return {radial:perf.radial,linear:perf.linear,draws:perf.draws,
           p50:p(.5),p95:p(.95),p99:p(.99),totalMs:perf.times.reduce((a,b)=>a+b,0),
           moved:balls.some(b=>b.id>0&&Math.hypot(b.vx,b.vy)>.02),
           ballCount:balls.filter(b=>!b.potted).length};
  }""")
  label=f'{w}x{h}'
  check(label+' moving full rack draws every frame',shot['draws']==48,shot)
  check(label+' full-rack balls receive impulse',shot['moved'],shot)
  check(label+' zero runtime radial gradient allocation',shot['radial']==0,shot)
  check(label+' zero runtime linear gradient allocation',shot['linear']==0,shot)
  check(label+' finite measured render p95',0<=shot['p95']<100 and shot['p99']>=shot['p95'],shot)
  # Draw a moving stripe and confirm the actual canvas contains an opaque,
  # coloured ball away from the table cloth.
  pix=page.evaluate("""() => {
   const b=balls.find(b=>b.id===10);
   if(!b||b.potted)return null;
   const x=Math.round(b.x+rad*.75),y=Math.round(b.y);
   return [...ctx.getImageData(x,y,1,1).data];
  }""")
  check(label+' rendered stripe remains opaque',pix is not None and pix[3]==255,pix)
  # Actual mouse pointer aim should affect the next rendered frame.
  page.evaluate("""() => {rack();perf.draws=0;perf.times=[];frame(2000)}""")
  box=page.locator('#table').bounding_box()
  page.mouse.click(box['x']+box['width']*.64,box['y']+box['height']*.30)
  inp=page.evaluate("""() => {const angle=aim;const prev=perf.draws;frame(last+1000/60);return {angle,draws:perf.draws-prev}}""")
  check(label+' real pointer aim appears on next frame',inp['draws']==1 and abs(inp['angle'])>.01,inp)
  check(label+' no browser JS errors',not errors,errors)
  page.close()
 browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_ACTIVE_RENDER_RESULTS.json').write_text(json.dumps({'passed':passed,'total':len(checks),'checks':checks,'limitations':'Headless Chromium CPU timings; not device FPS, latency or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
