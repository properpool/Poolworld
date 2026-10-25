"""Cross-device gameplay acceptance: phone, tablet and laptop Chromium layouts.

Browser emulation is not physical Samsung or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1]/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]
def check(label,ok,detail=None):
 checks.append(bool(ok))
 print(('PASS' if ok else 'FAIL'),label,detail if detail is not None else '',flush=True)

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 devices=[
  ('phone portrait',390,844,True),
  ('phone landscape',844,390,True),
  ('tablet portrait',768,1024,True),
  ('tablet landscape',1024,768,True),
  ('laptop',1366,768,False),
 ]
 for name,w,h,touch in devices:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=touch,has_touch=touch)
  errors=[]
  page.on('pageerror',lambda error:errors.append(str(error)))
  page.set_content(P.read_text(),wait_until='load')
  layout=page.evaluate("""() => {
   const bounds=id=>{const r=document.getElementById(id).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
   return {table:bounds('table'),track:bounds('track'),shoot:bounds('shoot'),viewport:{w:innerWidth,h:innerHeight},scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight};
  }""")
  vw,vh=layout['viewport']['w'],layout['viewport']['h']
  check(name+' no horizontal overflow',layout['scrollWidth']<=vw+1,(layout['scrollWidth'],vw))
  check(name+' table fully in horizontal viewport',layout['table']['left']>=-1 and layout['table']['right']<=vw+1)
  check(name+' table has usable rendered dimensions',layout['table']['width']>=250 and layout['table']['height']>=140)
  check(name+' power and SHOOT are horizontally reachable',all(layout[id]['left']>=-1 and layout[id]['right']<=vw+1 for id in ('track','shoot')))
  if w>h:
   check(name+' table and SHOOT fit without vertical scrolling',layout['table']['top']>=-1 and layout['table']['bottom']<=vh+1 and layout['shoot']['bottom']<=vh+1 and layout['scrollHeight']<=vh+1,(layout['scrollHeight'],vh))
  if touch:
   check(name+' SHOOT touch target >=44px',layout['shoot']['width']>=44 and layout['shoot']['height']>=44,(layout['shoot']['width'],layout['shoot']['height']))
  # Actual input interaction rather than static CSS assertions.
  table=layout['table']
  px=table['left']+table['width']*.78
  py=table['top']+table['height']*.62
  before=page.evaluate('aim')
  if touch:page.touchscreen.tap(px,py)
  else:page.mouse.click(px,py)
  check(name+' direct pointer aiming responds',abs(page.evaluate('aim')-before)>.05)
  page.locator('#shoot').click()
  check(name+' SHOOT starts real physics',page.evaluate('shooting && shot!==null && Math.hypot(balls[0].vx,balls[0].vy)>1'))
  check(name+' no browser exceptions',not errors,errors)
  page.close()
 browser.close()
print('SUMMARY',sum(checks),'/',len(checks),flush=True)
if not all(checks):raise SystemExit(1)
