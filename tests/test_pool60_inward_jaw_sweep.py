"""Fast balls can cross a rubber jaw and land inside the central rectangle.
Their swept impact must not be discarded by an endpoint-only broad-phase.
Browser checks are not physical Samsung Galaxy A37 acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,sys
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(label,ok,result):
    checks.append((label,bool(ok)))
    if not ok: print('FAIL',label,json.dumps(result),flush=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=width<1100)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        for top in (True,False):
          for left in (True,False):
            for horizontal in (-1,1):
              for level in (75,90):
                for scenario in ('swept-impact','clear-miss'):
                  result=page.evaluate("""([top,left,horizontal,level,scenario])=>{
                    const jx=W/2+(left?-mouth:mouth),jy=top?T:B;
                    const inward=top?1:-1;
                    const startX=level===75?3.55:3.8;
                    const startY=scenario==='clear-miss'?20.4:(level===75?18.9:18.85);
                    const speed=shotSpeed(level,false),angle=5.5*Math.PI/180;
                    const cue=makeBall(0,300,285);
                    const b=makeBall(1,jx-horizontal*startX,jy+inward*startY);
                    b.vx=horizontal*speed*Math.cos(angle);
                    b.vy=inward*speed*Math.sin(angle);
                    balls=[cue,b];turn=1;groups={1:'solids',2:'stripes'};
                    breakShot=false;ballInHand=false;gameOver=false;
                    shot={player:1,breakShot:false,firstHit:1,
                      railAfterContact:false,pocketed:[],scratch:false,targetEight:false};
                    shooting=true;events.length=0;pocketVisuals.length=0;
                    const initial={x:b.x,y:b.y,vx:b.vx,vy:b.vy,speed};
                    const scale=STEP*60,f=(speed-(.012+.0016*Math.min(speed,4))*scale)/speed;
                    const endX=b.x+b.vx*f*scale,endY=b.y+b.vy*f*scale;
                    const entryDistance=Math.hypot(b.x-jx,b.y-jy);
                    const endDistance=Math.hypot(endX-jx,endY-jy);
                    const endInner=endY>=T+rad+jawRadius&&endY<=B-rad-jawRadius;
                    physics(STEP);
                    return {initial,final:{x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                      speed:Math.hypot(b.vx,b.vy)},entryDistance,endDistance,endInner,
                      rail:shot.railAfterContact,potted:b.potted,pocketed:shot.pocketed.slice(),
                      cue:[cue.x,cue.y,cue.vx,cue.vy],
                      calibration:shotSpeed(level,false),
                      state:balls.flatMap(x=>[x.x,x.y,x.vx,x.vy])};
                  }""",[top,left,horizontal,level,scenario])
                  tag=f'{width}x{height} top={top} left={left} dir={horizontal} power={level} {scenario}'
                  impact=scenario=='swept-impact'
                  check(tag+' fixture outside jaw at both ends and central landing',
                        result['entryDistance']>19.2 and result['endDistance']>19.2 and
                        result['endInner'],result)
                  check(tag+' physical rebound correctly registered',
                        result['rail']==impact,result)
                  delta=(result['final']['vy']-result['initial']['vy'])*(1 if top else -1)
                  check(tag+' inward deflection or unchanged near miss',
                        delta>.15 if impact else abs(delta)<.02,result)
                  check(tag+' no phantom pocket or cue motion',
                        not result['potted'] and not result['pocketed'] and
                        result['cue']==[300,285,0,0],result)
                  check(tag+' dissipative finite physics',
                        result['final']['speed']<=result['initial']['speed']+1e-8 and
                        all(math.isfinite(v) for v in result['state']),result)
                  check(tag+' unchanged calibrated shot strength',
                        abs(result['calibration']-result['initial']['speed'])<1e-10,result)
        check(f'{width}x{height} no JavaScript errors',not errors,errors)
        page.close()
    browser.close()
passed=sum(ok for _,ok in checks)
(ROOT/'POOL_WORLD_6.0_INWARD_JAW_SWEEP_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),
                'failures':[label for label,ok in checks if not ok],
                'limitations':'Chromium only; physical Samsung/human acceptance release-blocking.'},indent=2))
print('INWARD JAW SWEEP SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
