"""Interrupted pointer-capture recovery for table aim and power slider.

Browser-simulated lostpointercapture is not physical Samsung/human acceptance.
A browser/OS can revoke capture without delivering a pointerup to the element.
The next gesture must remain usable; interrupted pullback must never fire.
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
  rack();showPower(45);
  const table=document.getElementById('table'),track=document.getElementById('track');
  const lost=(el,id)=>el.dispatchEvent(new PointerEvent('lostpointercapture',{pointerId:id,pointerType:'touch'}));
  const result={};
  // Lost capture while aiming: cancel the incomplete gesture and unlock input.
  const originalAim=aim;
  aimPointer=41;dragAim=true;aimFineDrag=true;aimStartAngle=originalAim;aim=originalAim+.7;
  lost(table,40);result.aimWrongIdIgnored=aimPointer===41&&dragAim&&aim!==originalAim;
  lost(table,41);
  result.aimReleased=aimPointer===null&&!dragAim&&!aimFineDrag;
  result.aimRestored=Math.abs(aim-originalAim)<1e-12;
  // Normal pointerup should preserve the chosen angle, and the browser's
  // subsequent lostpointercapture event must not roll it back.
  aimPointer=42;dragAim=true;aimStartAngle=originalAim;aim=originalAim+.15;
  table.dispatchEvent(new PointerEvent('pointerup',{pointerId:42,pointerType:'touch'}));
  lost(table,42);
  result.aimUpKeepsAngle=aimPointer===null&&!dragAim&&Math.abs(aim-originalAim-.15)<1e-12;
  // Lost power capture: clear the stuck drag, restore the pre-gesture power,
  // and do not fire an unintended shot.
  powerPointer=51;powerDrag=true;powerStart=61;powerY=120;showPower(92);
  lost(track,50);result.powerWrongIdIgnored=powerPointer===51&&powerDrag&&power===92;
  lost(track,51);
  result.powerReleased=powerPointer===null&&!powerDrag;
  result.powerRestored=power===61;
  result.noAccidentalShot=!shooting&&shot===null;
  // Normal short release changes power but must not auto-shoot, and a
  // subsequent lostcapture must not revert that accepted value.
  powerPointer=52;powerDrag=true;powerStart=61;powerY=200;showPower(73);
  track.dispatchEvent(new PointerEvent('pointerup',{pointerId:52,pointerType:'touch',clientY:200}));
  lost(track,52);
  result.powerUpKeepsValue=powerPointer===null&&!powerDrag&&power===73&&!shooting;
  return result;
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
        result=page.evaluate(FIXTURE)
        for key,ok in result.items():check(f'{w}x{h} {key}',ok,result)
        check(f'{w}x{h} no JS errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POINTER_CAPTURE_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Chromium event simulation only; no physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
