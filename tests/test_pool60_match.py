from pathlib import Path
from playwright.sync_api import sync_playwright
import json,time
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_6.0_STAGING_MATCH.html'
planner=r'''() => {
 const player=turn, s0=snapshot(), status0=$('status').textContent, power0=power, sound0=soundOn;
 soundOn=false;
 const own=groups[player];const eligible=balls.filter(b=>!b.potted && (own===null?b.id!==0&&b.id!==8:(remainingFor(player)===0?b.id===8:groupOf(b.id)===own)));
 let choices=[];
 const cue=balls[0];
 for(const obj of eligible){
  for(const [hx,hy] of holes){
   const vx=hx-obj.x,vy=hy-obj.y,dist=Math.hypot(vx,vy);if(dist<1)continue;
   const gx=obj.x-vx/dist*2*rad,gy=obj.y-vy/dist*2*rad;
   const positions=ballInHand? [70,120,180,240].map(d=>({x:obj.x-vx/dist*d,y:obj.y-vy/dist*d})).filter(p=>canPlace(p.x,p.y)) : [{x:cue.x,y:cue.y}];
   for(const pos of positions){
   const ax=gx-pos.x,ay=gy-pos.y,d=Math.hypot(ax,ay);if(d<1)continue;
   const theta=Math.atan2(ay,ax);
   // reject obvious blockers on cue->ghost or target->pocket
   const clear=(x1,y1,x2,y2,ignore)=>{const dx=x2-x1,dy=y2-y1,d2=dx*dx+dy*dy;return balls.every(b=>b.potted||b.id===0||b.id===ignore||((t)=>t<=0||t>=1||Math.hypot(b.x-x1-dx*t,b.y-y1-dy*t)>2*rad+1)( ((b.x-x1)*dx+(b.y-y1)*dy)/d2));};
   if(!clear(pos.x,pos.y,gx,gy,obj.id)||!clear(obj.x,obj.y,hx,hy,obj.id))continue;
   for(const da of [-.008,0,.008])for(const pow of [25.60,60,85])choices.push({a:theta+da,pow,target:obj.id,pocket:[hx,hy],distance:d,pos:ballInHand?pos:null});
   }
  }
 }
 if(!choices.length){const fallback=ballInHand?(()=>{const [x,y]=cuePosition();return {x,y}})():null;const px=fallback?fallback.x:cue.x,py=fallback?fallback.y:cue.y;for(const obj of eligible){let a=Math.atan2(obj.y-py,obj.x-px);for(const delta of [-.1,0,.1])for(const pow of [30,55,80])choices.push({a:a+delta,pow,target:obj.id,pos:fallback})}}
 let best={score:-1e10},tested=0;
 for(const c of choices){
  restore(s0);const b=balls[0];if(c.pos){b.x=c.pos.x;b.y=c.pos.y;ballInHand=false;}aim=c.a;power=c.pow;
  shot={player,breakShot,firstHit:null,railAfterContact:false,pocketed:[],scratch:false,targetEight:groups[player]!==null&&remainingFor(player)===0};
  const speed=shotSpeed(power,breakShot);b.vx=Math.cos(aim)*speed;b.vy=Math.sin(aim)*speed;b.spin=b.follow=0;shooting=true;
  let n=0;while(!settled()&&n++<2000)physics(STEP);
  if(!settled())continue;
  const pockets=shot.pocketed.slice(),firstHit=shot.firstHit;
  resolveShot();tested++;
  let score=0;
  if(gameOver)score=winner===player?1000:-1000;
  else if(turn===player){score=10+10*pockets.filter(id=>id!==0).length;}
  else if(ballInHand)score=-20;
  else score=0;
  score-=n*.0001;
  if(score>best.score){best={...c,score,pockets,firstHit,steps:n,turnAfter:turn,ballInHandAfter:ballInHand};}
 }
 restore(s0);$('status').textContent=status0;power=power0;soundOn=sound0;
 return {best,tested,candidates:choices.length,eligible:eligible.map(b=>b.id)};
}'''
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(P.read_text(),wait_until='load')
 page.evaluate('() => {aim=0;showPower(85)}');page.locator('#shoot').click()
 page.evaluate('() => {let n=0;while(!settled()&&n++<3000)physics(STEP);if(settled())resolveShot()}')
 print('break',page.evaluate('() => ({turn,groups,balls:balls.filter(b=>b.potted).map(b=>b.id),ballInHand})'),flush=True)
 match=[]
 for i in range(100):
  if page.evaluate('gameOver'):break
  t=time.monotonic()
  player_before=page.evaluate('turn')
  state_before=page.evaluate('() => JSON.stringify(snapshot())')
  result=page.evaluate(planner)
  assert page.evaluate('() => JSON.stringify(snapshot())')==state_before,'Bot preview modified match state'
  if result['tested']<=0:print('no candidate',i,result);break
  b=result['best']
  if b.get('pos'):
   box=page.locator('#table').bounding_box();pos=b['pos'];page.touchscreen.tap(box['x']+pos['x']*box['width']/1100,box['y']+pos['y']*box['height']/570)
  page.evaluate('([a,p])=>{aim=a;showPower(p)}',[b['a'],b['pow']]);page.locator('#shoot').click()
  assert page.evaluate('shooting'),f'SHOOT click failed at turn {i}'
  page.evaluate('() => {let n=0;while(!settled()&&n++<4000)physics(STEP);if(settled())resolveShot()}')
  state=page.evaluate('() => ({turn,groups,remaining:balls.filter(b=>!b.potted&&b.id!==0).map(b=>b.id),ballInHand,gameOver,winner})')
  match.append({'shot':i+2,'player':player_before,'target':b['target'],'pockets':b['pockets'],'remaining':len(state['remaining']),'turn_after':state['turn'],'winner':state['winner'],'tested_candidates':result['tested']})
  assert page.evaluate('() => balls.every(b=>Number.isFinite(b.x)&&Number.isFinite(b.y)&&Number.isFinite(b.vx)&&Number.isFinite(b.vy))'),'Nonfinite ball state'
  print(i, 'time',round(time.monotonic()-t,2),'tested',result['tested'],'best',round(b['score'],2),'pockets',b['pockets'],'remaining',len(state['remaining']),'turn',state['turn'],'groups',state['groups'],'BIH',state['ballInHand'],flush=True)
  if state['gameOver']:print('GAME OVER',state);break
 assert state['gameOver'] and state['winner'] in (1,2),f'Unscripted match did not finish: {state}'
 assert not errors,errors
 print('UNSCRIPTED_MATCH_PASS',len(match)+1,'shots, winner',state['winner'],flush=True)
 (P.parent/'POOL_WORLD_6.0_UNSCRIPTED_MATCH_RESULTS.json').write_text(json.dumps({'passed':True,'total_shots':len(match)+1,'winner':state['winner'],'shots':match,'browser_errors':errors},indent=2))
 browser.close()
