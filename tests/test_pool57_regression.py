from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,hashlib,time,re
P=(Path(__file__).resolve().parent.parent/'POOL_WORLD_5.7_STAGING_MATCH.html').resolve()
checks=[]
def check(label,condition,details=None):
    checks.append((label,bool(condition),details))
    print(('PASS' if condition else 'FAIL')+' '+label+(f' {details}' if details is not None else ''))

AUDIO_HASHES={'ball':'6e0440053e5859b48fa1','cue':'7e2b39137a6de6afd751','rail':'e405df7c5c3c3937a6e2','pocket':'6931e106287f67f9b771'}
html=P.read_text()
for name,expected in AUDIO_HASHES.items():
    match=re.search(r'\b'+name+r':"(data:audio/[^" ]+)"',html)
    digest=hashlib.sha256(match.group(1).encode()).hexdigest()[:20] if match else None
    check('approved v3.9 '+name+' audio unchanged',digest==expected,digest)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(P.read_text(),wait_until="load");page.wait_for_timeout(300)
    check('initial game state',page.evaluate('() => ({turn,breakShot,count:balls.length,phase:document.getElementById("phase").textContent})')=={'turn':1,'breakShot':True,'count':16,'phase':'READY TO BREAK'})
    check('mobile viewport no overflow',page.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth'))
    check('all four approved sound sources embedded',page.evaluate('() => Object.keys(RECORDED_SOUNDS).sort().join(",")')=='ball,cue,pocket,rail')
    # Actual UI shooting and animation-frame physics (not simulated shortcut).
    page.evaluate('showPower(85)');page.locator('#shoot').click()
    check('actual SHOOT button starts moving',page.evaluate('() => shooting && balls[0].vx > 3'))
    page.wait_for_function('!shooting',timeout=20000)
    first=page.evaluate('() => ({count:balls.filter(b=>!b.potted).length,turn,breakShot,status:document.getElementById("status").textContent,firstHit:history?.balls?.length})')
    check('actual browser shot settles and transitions',first['breakShot']==False and first['turn'] in (1,2),first)
    check('actual SHOOT remains usable after first shot',page.locator('#shoot').is_enabled())
    # Physics break: direct deterministic stepping of the real physics implementation.
    phys=page.evaluate('''() => {rack();showPower(85);aim=0;shoot();let steps=0,firstHit=null;while(!settled()&&steps++<2500){physics(STEP);if(shot&&shot.firstHit!==null)firstHit=shot.firstHit;}let stopped=settled();if(stopped)resolveShot();return {steps,stopped,firstHit,turn,breakShot};}''')
    check('break contacts object ball and settles',phys['stopped'] and phys['firstHit'] is not None and phys['steps']<2500,phys)
    # Cue scratch + ball-in-hand, and valid/invalid placement through actual mobile canvas taps.
    page.evaluate('''() => {rack();breakShot=false;groups={1:'solids',2:'stripes'};history=snapshot();shot={player:1,breakShot:false,firstHit:1,railAfterContact:true,pocketed:[0],scratch:true};balls[0].potted=true;resolveShot()}''')
    check('scratch awards ball in hand to opponent',page.evaluate('() => ballInHand && turn===2 && !balls[0].potted && document.getElementById("shoot").disabled'))
    initial=page.evaluate('() => ({x:balls[0].x,y:balls[0].y})')
    box=page.locator('#table').bounding_box()
    # Tapping a ball's occupied location must not accept invalid placement.
    p0=page.evaluate('() => ({x:balls[1].x,y:balls[1].y})')
    page.touchscreen.tap(box['x']+p0['x']*box['width']/1100,box['y']+p0['y']*box['height']/570)
    check('occupied cue placement rejected',page.evaluate('() => ballInHand'))
    x,y=460,360
    page.touchscreen.tap(box['x']+x*box['width']/1100,box['y']+y*box['height']/570)
    check('valid touch placement accepted',page.evaluate('() => !ballInHand && Math.hypot(balls[0].x-460,balls[0].y-360)<3 && !document.getElementById("shoot").disabled'))
    page.locator('#undo').click()
    check('undo restores complete state',page.evaluate("() => turn===1 && groups[1]==='solids' && !ballInHand && !breakShot && !shooting"))
    # Rule outcomes from deterministic event fixtures.
    cases=page.evaluate('''() => {
      const result={};
      rack();breakShot=false;shot={player:1,breakShot:false,firstHit:1,railAfterContact:true,pocketed:[1],scratch:false};balls.find(b=>b.id===1).potted=true;resolveShot();result.assignment=groups[1]==='solids'&&groups[2]==='stripes'&&turn===1;
      rack();breakShot=false;groups={1:'solids',2:'stripes'};shot={player:1,breakShot:false,firstHit:9,railAfterContact:true,pocketed:[9],scratch:false};balls.find(b=>b.id===9).potted=true;resolveShot();result.wrongContact=turn===2&&ballInHand;
      rack();breakShot=false;groups={1:'solids',2:'stripes'};shot={player:1,breakShot:false,firstHit:1,railAfterContact:false,pocketed:[],scratch:false};resolveShot();result.noRail=turn===2&&ballInHand;
      rack();breakShot=false;groups={1:'solids',2:'stripes'};shot={player:1,breakShot:false,firstHit:8,railAfterContact:true,pocketed:[8],scratch:false};balls.find(b=>b.id===8).potted=true;resolveShot();result.earlyEight=gameOver&&winner===2;
      rack();breakShot=false;groups={1:'solids',2:'stripes'};for(let i=1;i<=7;i++)balls.find(b=>b.id===i).potted=true;shot={player:1,breakShot:false,firstHit:8,railAfterContact:false,pocketed:[8],scratch:false};balls.find(b=>b.id===8).potted=true;resolveShot();result.legalEight=gameOver&&winner===1;
      rack();shot={player:1,breakShot:true,firstHit:1,railAfterContact:true,pocketed:[8],scratch:false};balls.find(b=>b.id===8).potted=true;resolveShot();result.eightBreakRerack=!gameOver&&breakShot&&balls.length===16;
      return result;
    }''')
    for name,ok in cases.items():check('rule '+name,ok)
    # Real pointer gesture on the power track should fire a shot and remain responsive.
    page.evaluate('rack()')
    power_box=page.locator('#track').bounding_box()
    page.mouse.move(power_box['x']+power_box['width']/2,power_box['y']+power_box['height']*.35)
    page.mouse.down()
    page.mouse.move(power_box['x']+power_box['width']/2,power_box['y']+power_box['height']*.82,steps=8)
    page.mouse.up()
    check('actual pullback gesture fires a shot',page.evaluate('() => shooting && balls[0].vx>0'))
    page.evaluate('() => {let n=0;while(!settled()&&n++<2000)physics(STEP);if(settled())resolveShot()}')
    check('power gesture shot settles',page.evaluate('() => !shooting'))
    # Eight physical pots in sequence using real collision and pocket physics.
    physical=page.evaluate('''() => {
      rack();breakShot=false;turn=1;groups={1:'solids',2:'stripes'};const out=[];
      for(const target of [1,2,3,4,5,6,7,8]){
        const cue=balls[0];cue.x=206;cue.y=206;cue.potted=false;cue.vx=cue.vy=0;
        for(const b of balls){if(b.id===0||b.potted)continue;
          if(b.id===target){b.x=142;b.y=142;}
          else {const ix=b.id;b.x=750+(ix%4)*48;b.y=145+Math.floor(ix/4)*58;}
          b.vx=b.vy=0;
        }
        aim=-Math.PI*3/4;showPower(58);
        const fired=shoot();let steps=0,hit=null,pocketed=[];
        if(fired){while(!settled()&&steps++<4000){physics(STEP);if(shot){hit=shot.firstHit;pocketed=shot.pocketed.slice();}}
          if(settled())resolveShot();}
        out.push({target,fired,steps,hit,pocketed,turn,gameOver,winner,status:document.getElementById('status').textContent});
        if(!fired||steps>=4000||!pocketed.includes(target)||turn!==1&&target!==8)break;
      }
      return out;
    }''')
    check('full 8-ball physical sequence (position-controlled fixture)',len(physical)==8 and all(v['target'] in v['pocketed'] and v['steps']<4000 for v in physical) and physical[-1]['winner']==1,physical)
    # Regression: repeatedly use the actual on-screen SHOOT control (previously stopped responding).
    page.evaluate('rack()')
    clicks=0
    for i in range(20):
        if page.evaluate('() => ballInHand'):
            page.evaluate('() => {const [x,y]=cuePosition();balls[0].x=x;balls[0].y=y;ballInHand=false;updateHUD()}')
        if page.evaluate('() => gameOver'):page.evaluate('rack()')
        if not page.locator('#shoot').is_enabled():break
        page.locator('#shoot').click()
        if not page.evaluate('() => shooting'):break
        result=page.evaluate('() => {let n=0;while(!settled()&&n++<4000)physics(STEP);if(settled())resolveShot();return {n,done:!shooting}}')
        if not result['done']:break
        clicks+=1
    check('SHOOT button remains functional for 20 consecutive matches/turns',clicks==20,{'clicks':clicks})
    # Cushion and pocket dynamics on actual physics engine.
    physicsCases=page.evaluate('''() => {
      rack();for(const b of balls)if(b.id!==0&&b.id!==1)b.potted=true;
      const b=balls.find(v=>v.id===1);b.x=R-rad-.1;b.y=(T+B)/2;b.vx=2;b.vy=0;
      shot={player:1,breakShot:false,firstHit:1,railAfterContact:false,pocketed:[],scratch:false};
      physics(STEP);const rail=b.vx<0&&b.x<=R-rad&&shot.railAfterContact;
      rack();for(const b of balls)if(b.id!==0&&b.id!==1)b.potted=true;
      const c=balls.find(v=>v.id===1);c.x=L+27;c.y=T+27;c.vx=-2;c.vy=-2;
      shot={player:1,breakShot:false,firstHit:1,railAfterContact:false,pocketed:[],scratch:false};
      for(let i=0;i<30&&!c.potted;i++)physics(STEP);
      return {rail,pocket:c.potted&&shot.pocketed.includes(1)};
    }''')
    for name,ok in physicsCases.items():check('physics '+name,ok)
    # Randomised physics stress across 80 shots, with cue re-positioned on fouls.
    stress=page.evaluate('''() => {
      let failures=[],completed=0,maxSteps=0;let seed=712367;
      const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
      for(let i=0;i<80;i++){
        if(gameOver)rack();if(ballInHand){ballInHand=false;const [x,y]=cuePosition();balls[0].x=x;balls[0].y=y;}
        if(balls[0].potted){balls[0].potted=false;const [x,y]=cuePosition();balls[0].x=x;balls[0].y=y;}
        aim=rand()*Math.PI*2;showPower(15+rand()*85);if(!shoot()){failures.push('shoot blocked '+i);break}
        let n=0;while(!settled()&&n++<5000)physics(STEP);maxSteps=Math.max(maxSteps,n);
        if(!settled()){failures.push('never settled '+i);break}resolveShot();completed++;
        if(balls.some(b=>!Number.isFinite(b.x)||!Number.isFinite(b.y)||!Number.isFinite(b.vx)||!Number.isFinite(b.vy))){failures.push('nonfinite '+i);break}
        if(balls.some(b=>!b.potted&&(b.x<L-2*rad||b.x>R+2*rad||b.y<T-2*rad||b.y>B+2*rad))){failures.push('out of bounds '+i);break}
      }
      return {completed,maxSteps,failures};
    }''')
    check('80 random shots settle without nonfinite/out-of-bounds',stress['completed']==80 and not stress['failures'],stress)
    check('no runtime JavaScript errors',not errors,errors)
    page.screenshot(path=str(P.parent/'pool57_mobile_test.png'),full_page=True)
    browser.close()
print('\nSUMMARY',sum(x[1] for x in checks),'/',len(checks))
(P.parent/'POOL_WORLD_5.7_REGRESSION_RESULTS.json').write_text(json.dumps({'passed':sum(x[1] for x in checks),'total':len(checks),'checks':[{'name':a,'passed':b,'details':c} for a,b,c in checks]},indent=2))
if not all(x[1] for x in checks):raise SystemExit(1)