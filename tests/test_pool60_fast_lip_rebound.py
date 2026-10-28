"""Fast pocket-mouth near misses must rebound without a one-frame rail snap.

Deterministic Chromium geometry and 120Hz physics tests. They do not establish
physical Samsung Galaxy A37 frame rate, smoothness or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=True)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        label=f'{width}x{height}'
        for top in (True,False):
            for side in (-1,1):
                for speed in (.7,1.5,2.8):
                    data=page.evaluate("""({top,side,speed})=>{
                        rack();breakShot=false;
                        const b=balls[1],rail=top?T+rad:B-rad;
                        b.x=W/2+side*15;b.y=rail+(top?-1:1);
                        b.vx=side*speed;b.vy=(top?-1:1)*speed*.3;
                        b.spin=0;
                        shot={player:1,breakShot:false,firstHit:1,
                            railAfterContact:false,pocketed:[],scratch:false,
                            targetEight:false};
                        const before={x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                            kinetic:b.vx*b.vx+b.vy*b.vy};
                        constrainRail(b);
                        const result={before,x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                            kinetic:b.vx*b.vx+b.vy*b.vy,
                            rail:shot.railAfterContact,potted:b.potted,
                            lo:T+rad,hi:B-rad};
                        shot=null;rack();return result;
                    }""",{'top':top,'side':side,'speed':speed})
                    tag=f'{label} {"top" if top else "bottom"} side {side} {speed}'
                    check(tag+' missed pocket lip returns to playable cloth',
                          data['lo']-1e-5<=data['y']<=data['hi']+1e-5,data)
                    check(tag+' missed lip produces an inward rebound',
                          data['vy']>0 if top else data['vy']<0,data)
                    check(tag+' actual rebound counts as post-contact rail',
                          data['rail'],data)
                    check(tag+' no phantom pot or added kinetic energy',
                          not data['potted'] and
                          data['kinetic']<=data['before']['kinetic']+1e-8,data)
                for speed in (.6,1.3,2.5):
                    data=page.evaluate("""({top,side,speed})=>{
                        rack();breakShot=false;
                        const b=balls[1],rail=top?T+rad:B-rad;
                        b.x=W/2+side*10;b.y=rail+(top?-1:1);
                        b.vx=-side*speed*.6;b.vy=(top?-1:1)*speed*1.8;
                        shot={player:1,breakShot:false,firstHit:1,
                            railAfterContact:false,pocketed:[],scratch:false,
                            targetEight:false};
                        const initial={x:b.x,y:b.y,vx:b.vx,vy:b.vy};
                        constrainRail(b);
                        const open={x:b.x,y:b.y,vx:b.vx,vy:b.vy,
                            rail:shot.railAfterContact};
                        for(let i=0;i<45&&!b.potted;i++)physics(1/120);
                        const result={initial,open,potted:b.potted,
                            pocketed:shot.pocketed.slice(),rail:shot.railAfterContact};
                        shot=null;rack();return result;
                    }""",{'top':top,'side':side,'speed':speed})
                    tag=f'{label} genuine {"top" if top else "bottom"} pot {side} {speed}'
                    check(tag+' genuine pocket mouth stays open',
                          all(abs(data['open'][k]-data['initial'][k])<1e-7
                              for k in ('x','y','vx','vy')) and
                          not data['open']['rail'],data)
                    check(tag+' actual ball enters circular pocket well',
                          data['potted'] and 1 in data['pocketed'],data)
        check(label+' no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_FAST_LIP_REBOUND_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
        'limitations':'Synthetic Chromium; physical Samsung and human acceptance remain release-blocking.'},indent=2))
print('FAST LIP REBOUND',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
