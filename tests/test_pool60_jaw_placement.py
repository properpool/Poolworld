"""Reject ball-in-hand placement overlapping all twelve physical rubber jaw noses.
Chromium geometry/input regression, not physical Samsung or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys
ROOT=Path(__file__).resolve().parent.parent
HTML=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(name,ok,details):
    checks.append({'name':name,'passed':bool(ok),'details':details})
    if not ok: print('FAIL',name,details,flush=True)
FIXTURE=r"""() => {
 rack();for(const b of balls)if(b.id!==0)b.potted=true;
 const cue=balls[0];ballInHand=true;shooting=false;gameOver=false;
 const result=[];
 for(let i=0;i<jaws.length;i++){
  const [jx,jy]=jaws[i];
  const dx=jx===L?1:jx===R?-1:0,dy=jy===T?1:jy===B?-1:0;
  const ix=jx+dx*(rad+2),iy=jy+dy*(rad+2);
  const ox=jx+dx*(rad+jawRadius+2),oy=jy+dy*(rad+jawRadius+2);
  const old=[cue.x,cue.y];
  const before=canPlace(ix,iy),outside=canPlace(ox,oy);
  if(before){cue.x=ix;cue.y=iy;ballInHand=false}
  const rejected=ballInHand&&cue.x===old[0]&&cue.y===old[1];
  ballInHand=true;cue.x=ix;cue.y=iy;
  const confirmed=confirmCuePlacement();
  const clear=jaws.every(([x,y])=>Math.hypot(cue.x-x,cue.y-y)>=rad+jawRadius-.001);
  const valid=canPlace(cue.x,cue.y);
  result.push({jaw:i,inside:before,outside,rejected,confirmed,clear,valid});
  cue.x=old[0];cue.y=old[1];ballInHand=true;
 }
 return result;
}"""
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
      executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
      args=['--no-sandbox'])
    for w,h in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':w,'height':h},
          is_mobile=w<1000,has_touch=w<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML.read_text(),wait_until='load')
        for item in page.evaluate(FIXTURE):
            name=f'{w}x{h} jaw{item["jaw"]}'
            check(name+' rejects overlapping cue',not item['inside'] and item['rejected'],item)
            check(name+' accepts clear position',item['outside'],item)
            check(name+' safe confirm relocates',item['confirmed'] and item['clear'] and item['valid'],item)
        check(f'{w}x{h} no JS exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_JAW_PLACEMENT_RESULTS.json').write_text(
 json.dumps({'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Automated Chromium only; no physical Samsung or independent human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
