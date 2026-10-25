"""Ensure a completed turn does not retain stationary spin or follow/draw.
A stopped ball must not carry frozen rotational energy into the next shot.
Automated Chromium physics/rules checks, not physical-device acceptance.
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
 const results=[];
 const assignRotation=()=>{
  for(const b of balls){
   b.vx=.07*(b.id+1);b.vy=-.04*(b.id+1);
   b.spin=b.id%2?.8:-1.1;b.follow=b.id%2?-1.3:1.7;
  }
 };
 const capture=(name,extra={})=>results.push({
  name,states:balls.map(b=>({id:b.id,vx:b.vx,vy:b.vy,spin:b.spin,follow:b.follow})),
  turn,ballInHand,gameOver,winner,breakShot,...extra
 });
 // Legal shot: every stationary ball, including untouched object balls, must
 // lose residual spin once the entire table is declared settled.
 rack();breakShot=false;groups={1:'solids',2:'stripes'};
 assignRotation();balls.find(b=>b.id===1).potted=true;
 shot={player:1,breakShot:false,firstHit:1,railAfterContact:true,
       pocketed:[1],scratch:false,targetEight:false};
 resolveShot();capture('legal');
 // Scratch: the replaced cue and every remaining object must be stationary.
 rack();breakShot=false;assignRotation();balls[0].potted=true;
 shot={player:1,breakShot:false,firstHit:9,railAfterContact:true,
       pocketed:[0],scratch:true,targetEight:false};
 resolveShot();capture('scratch',{cueLegal:canPlace(balls[0].x,balls[0].y),cuePotted:balls[0].potted});
 // Winning 8-ball: game-over path must clear all rotational state too.
 rack();breakShot=false;groups={1:'solids',2:'stripes'};
 for(const b of balls)if(b.id>=1&&b.id<=7)b.potted=true;
 assignRotation();balls.find(b=>b.id===8).potted=true;
 shot={player:1,breakShot:false,firstHit:8,railAfterContact:true,
       pocketed:[8],scratch:false,targetEight:true};
 resolveShot();capture('eight');
 // A real spun shot must settle and complete, not just a synthetic resolve.
 rack();breakShot=false;groups={1:'solids',2:'stripes'};
 for(const b of balls)if(b.id!==0&&b.id!==1)b.potted=true;
 const cue=balls[0],obj=balls.find(b=>b.id===1);
 obj.x=cue.x+4*rad;obj.y=cue.y;obj.spin=.6;obj.follow=-.8;
 aim=0;power=35;spin=85;follow=75;
 const started=shoot();let ticks=0;
 while(shooting&&!settled()&&ticks<3500){physics(STEP);ticks++}
 const stopped=settled();
 if(shooting&&stopped)resolveShot();
 capture('natural',{started,stopped,ticks,stillShooting:shooting});
 return results;
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
        for case in page.evaluate(FIXTURE):
            name=f'{w}x{h} {case["name"]}'
            for ball in case['states']:
                for field in ['vx','vy','spin','follow']:
                    check(f'{name} ball {ball["id"]} {field} clears',
                          abs(ball[field])<1e-8,ball)
            if case['name']=='legal':
                check(name+' retains shooter',case['turn']==1 and not case['ballInHand'] and not case['gameOver'],case)
            elif case['name']=='scratch':
                check(name+' legal cue recovery',case['turn']==2 and case['ballInHand'] and case['cueLegal'] and not case['cuePotted'],case)
            elif case['name']=='eight':
                check(name+' winner',case['gameOver'] and case['winner']==1,case)
            else:
                check(name+' shot finished',case['started'] and case['stopped'] and not case['stillShooting'] and case['ticks']>0,case)
        check(f'{w}x{h} no JS exceptions',not errors,errors)
        page.close()
    browser.close()
passed=sum(x['passed'] for x in checks)
(ROOT/'POOL_WORLD_6.0_SETTLED_SPIN_RESULTS.json').write_text(
 json.dumps({'passed':passed,'total':len(checks),'checks':checks,
 'limits':'Automated Chromium only; no physical Samsung or human acceptance.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
