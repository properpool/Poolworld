"""Pixel-level canvas and mobile visual checks, not subjective human review."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,statistics
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_5.6_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail):
 checks.append({'name':name,'passed':bool(ok),'details':detail});print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for width,height in [(390,844),(844,390),(1280,800)]:
  page=browser.new_page(viewport={'width':width,'height':height},is_mobile=width<900,has_touch=width<900)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(P.read_text(),wait_until='load');page.wait_for_timeout(120)
  data=page.evaluate('''() => {
   const pixel=(c,x,y)=>[...c.getImageData(Math.round(x),Math.round(y),1,1).data].slice(0,3);
   const s=balls.find(b=>b.id===9),c=canvas.getContext('2d');
   const stripe=pixel(c,s.x+7,s.y),ivory=pixel(c,s.x+7,s.y+8);
   const dist=Math.hypot(...stripe.map((v,i)=>v-ivory[i]));
   const nose=jaws[0], nosePixel=pixel(g,nose[0],nose[1]);
   const pocketPixel=pixel(g,holes[1][0],holes[1][1]);
   const t0=performance.now();for(let i=0;i<120;i++)render();const ms=(performance.now()-t0)/120;
   return {stripe,ivory,dist,nosePixel,pocketPixel,jaws:jaws.length,renderMs:ms,overflow:document.documentElement.scrollWidth>innerWidth,balls:balls.length};
  }''')
  check(f'{width}x{height} stripe and ivory visually distinct',data['dist']>40,data)
  check(f'{width}x{height} pocket interior dark',max(data['pocketPixel'])<55,data['pocketPixel'])
  check(f'{width}x{height} twelve visual jaws',data['jaws']==12 and max(data['nosePixel'])>35,data['nosePixel'])
  check(f'{width}x{height} no horizontal overflow',not data['overflow'],data['overflow'])
  check(f'{width}x{height} no browser errors',not errors,errors)
  check(f'{width}x{height} render 120 calls under 25ms average',data['renderMs']<25,data['renderMs'])
  page.screenshot(path=str(P.parent/f'pool56_{width}x{height}.png'),full_page=True)
  page.close()
 browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks}
(P.parent/'POOL_WORLD_5.6_VISUAL_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',result['passed'],'/',result['total'])
if result['passed']!=result['total']:raise SystemExit(1)