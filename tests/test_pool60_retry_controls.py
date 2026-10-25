"""Retry-shot integrity across phone portrait/landscape and desktop Chromium.
Checks game-state and UI controls, not physical-device or human playability.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(label,ok,details=None):
    checks.append({'name':label,'passed':bool(ok),'details':details})
    print(('PASS ' if ok else 'FAIL ')+label+' '+str(details or ''),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
    for name,w,h,touch in [('Samsung portrait',390,844,True),('Samsung landscape',844,390,True),('laptop',1366,768,False)]:
        page=browser.new_page(viewport={'width':w,'height':h},is_mobile=touch,has_touch=touch)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(SOURCE.read_text(),wait_until='load')
        page.evaluate("""() => {
          rack();breakShot=false;aim=.19;showPower(68);spin=44;follow=-31;
          document.getElementById('spin').value=spin;
          document.getElementById('follow').value=follow;
          window.expectedRetryState=snapshot();
        }""")
        page.locator('#shoot').click()
        first=page.evaluate("""() => ({
          shooting,historyPower:history?.power,historySpin:history?.spin,
          historyFollow:history?.follow,initialSpeed:Math.hypot(balls[0].vx,balls[0].vy)
        })""")
        check(name+' shot starts with chosen power and spin',
              first['shooting'] and first['historyPower']==68 and first['historySpin']==44 and first['historyFollow']==-31,first)
        # A drag-to-shoot gesture resets power to 45%; UI changes must not corrupt shot history.
        page.evaluate("""() => {
          showPower(45);spin=0;follow=0;
          document.getElementById('spin').value=0;
          document.getElementById('follow').value=0;
          let n=0;while(!settled()&&n++<4500)physics(STEP);
          if(settled())resolveShot();
        }""")
        check(name+' first shot resolves',page.evaluate('!shooting'))
        page.locator('#undo').click()
        restored=page.evaluate("""() => ({
          same:JSON.stringify(snapshot())===JSON.stringify(window.expectedRetryState),
          power,powerOutput:document.getElementById('powerValue').textContent,
          powerSlider:document.getElementById('strength').value,
          spin,spinSlider:document.getElementById('spin').value,
          follow,followSlider:document.getElementById('follow').value,
          shooting,historyCleared:history===null,button:document.getElementById('shoot').textContent
        })""")
        check(name+' retry restores all pre-shot game state',restored['same'],restored)
        check(name+' retry restores power slider and label',
              restored['power']==68 and restored['powerOutput']=='68%' and restored['powerSlider']=='68',restored)
        check(name+' retry restores side and top/backspin sliders',
              restored['spin']==44 and restored['spinSlider']=='44' and restored['follow']==-31 and restored['followSlider']=='-31',restored)
        check(name+' retry leaves SHOOT enabled and clears old history',
              not restored['shooting'] and restored['historyCleared'] and restored['button']=='SHOOT',restored)
        # Dispatch the real button action and sample speed in the same browser
        # task. Separate Playwright round-trips can allow a 120Hz physics tick
        # to run before sampling, making a correct shot look underpowered.
        repeat=page.evaluate("""() => {
          document.getElementById('shoot').click();
          return {
            shooting,historyPower:history?.power,historySpin:history?.spin,
            historyFollow:history?.follow,speed:Math.hypot(balls[0].vx,balls[0].vy),
            expectedSpeed:shotSpeed(68,false)
          };
        }""")
        check(name+' replay uses the original 68% shot speed and spin',
              repeat['shooting'] and repeat['historyPower']==68 and repeat['historySpin']==44 and
              repeat['historyFollow']==-31 and abs(repeat['speed']-repeat['expectedSpeed'])<1e-10,repeat)
        check(name+' no browser exceptions',not errors,errors)
        page.close()
    browser.close()

result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,
        'limits':'Chromium emulation only; not physical Samsung or human playability.'}
(ROOT/'POOL_WORLD_6.0_RETRY_CONTROLS_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
