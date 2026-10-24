"""Natural-layout full matches from three distinct physical breaks, real SHOOT clicks."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import ast,json
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_6.0_STAGING_MATCH.html'
script=ast.parse((Path(__file__).parent/'test_pool60_match.py').read_text())
planner=next(ast.literal_eval(n.value) for n in script.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='planner' for t in n.targets))
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for angle,pow in [(0,85),(.012,78),(-.018,95)]:
  page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(P.read_text(),wait_until='load')
  page.evaluate('([a,p])=>{aim=a;showPower(p)}',[angle,pow]);page.locator('#shoot').click()
  page.evaluate('() => {let n=0;while(!settled()&&n++<3000)physics(STEP);if(settled())resolveShot()}')
  match=[];ball_in_hand=0;reason='shot limit'
  for i in range(100):
   if page.evaluate('gameOver'):reason='completed';break
   state_before=page.evaluate('() => JSON.stringify(snapshot())')
   result=page.evaluate(planner)
   if page.evaluate('() => JSON.stringify(snapshot())')!=state_before:raise AssertionError('Preview mutated game state')
   if result['tested']<=0:reason='no legal candidate';break
   b=result['best'];before=page.evaluate('turn')
   if b.get('pos'):
    box=page.locator('#table').bounding_box();pos=b['pos']
    page.touchscreen.tap(box['x']+pos['x']*box['width']/1100,box['y']+pos['y']*box['height']/570)
    ball_in_hand+=1
   page.evaluate('([a,p])=>{aim=a;showPower(p)}',[b['a'],b['pow']]);page.locator('#shoot').click()
   if not page.evaluate('shooting'):reason='SHOOT blocked';break
   page.evaluate('() => {let n=0;while(!settled()&&n++<4000)physics(STEP);if(settled())resolveShot()}')
   state=page.evaluate('() => ({turn,ballInHand,gameOver,winner,remaining:balls.filter(b=>!b.potted&&b.id!==0).length,finite:balls.every(b=>Number.isFinite(b.x)&&Number.isFinite(b.y)&&Number.isFinite(b.vx)&&Number.isFinite(b.vy))})')
   if not state['finite']:reason='non-finite physics';break
   match.append({'player':before,'target':b['target'],'pockets':b['pockets'],'remaining':state['remaining'],'ball_in_hand':state['ballInHand']})
   if state['gameOver']:reason='completed';break
  final=page.evaluate('() => ({gameOver,winner,ballInHand,remaining:balls.filter(b=>!b.potted&&b.id!==0).length})')
  passed=reason=='completed' and final['gameOver'] and final['winner'] in (1,2) and not errors
  results.append({'break_angle_rad':angle,'break_power':pow,'passed':passed,'reason':reason,'shots':len(match)+1,'ball_in_hand_placements':ball_in_hand,'final':final,'errors':errors,'shot_log':match})
  print(('PASS' if passed else 'FAIL'),angle,pow,'shots',len(match)+1,'BIH',ball_in_hand,'reason',reason,'final',final,flush=True)
  page.close()
 browser.close()
(P.parent/'POOL_WORLD_6.0_VARIED_MATCH_RESULTS.json').write_text(json.dumps({'passed':sum(r['passed'] for r in results),'total':len(results),'results':results},indent=2))
if not all(r['passed'] for r in results):raise SystemExit(1)
