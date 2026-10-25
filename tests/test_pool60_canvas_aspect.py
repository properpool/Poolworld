"""Detect non-uniform pool-table canvas scaling on phones, tablets and laptops.
The cue and every ball must remain circular in CSS pixels; Chromium geometry
checks are not physical Samsung acceptance or human playability testing.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys

ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok: print('FAIL',name,details,flush=True)

FIXTURE=r"""() => {
 const rect=canvas.getBoundingClientRect();
 const sx=rect.width/W,sy=rect.height/H;
 const cue=balls[0],target={x:cue.x+155,y:cue.y+92};
 const event={clientX:rect.left+target.x*sx,clientY:rect.top+target.y*sy,pointerType:'touch'};
 const originalAim=aim;aim=-2;
 pointAim(event);
 const aimed=aim;
 aim=originalAim;
 const coords=pointerCoords(event);
 const guard=nearCueTouch({clientX:rect.left+cue.x*sx+10,clientY:rect.top+cue.y*sy,pointerType:'touch'});
 return {width:rect.width,height:rect.height,sx,sy,
         anisotropy:Math.abs(sx/sy-1),aimed,
         expected:Math.atan2(target.y-cue.y,target.x-cue.x),
         coords,target,guard};
}"""

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
      executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
      args=['--no-sandbox'])
    for w,h in [(360,800),(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML.read_text(),wait_until='load')
        v=page.evaluate(FIXTURE)
        name=f'{w}x{h}'
        check(name+' canvas has visible dimensions',v['width']>120 and v['height']>60,v)
        check(name+' ball aspect is round (<0.5% scaling difference)',v['anisotropy']<.005,v)
        check(name+' touch aim retains table-space angle',abs(v['aimed']-v['expected'])<1e-8,v)
        check(name+' touch maps X correctly',abs(v['coords']['x']-v['target']['x'])<1e-6,v)
        check(name+' touch maps Y correctly',abs(v['coords']['y']-v['target']['y'])<1e-6,v)
        check(name+' nearby finger is recognized',v['guard'],v)
        check(name+' no JS exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_CANVAS_ASPECT_RESULTS.json').write_text(
 json.dumps({'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Chromium geometry only; no physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
