"""Pocketed balls must visibly fall into a well instead of vanishing instantly.

Chromium canvas interception checks the rendered ball transforms, the independent
match state, animation completion after settlement, and reset/undo cancellation.
No claim is made about physical Samsung performance or human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name, condition, detail=None):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
    if not condition: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for w,h in ((360,800),(390,844),(844,390),(768,1024)):
        page=browser.new_page(viewport={'width':w,'height':h},
                              is_mobile=w<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        label=f'{w}x{h}'
        result=page.evaluate("""()=>{
          const oldDraw=drawBall,oldPhysics=physics,oldSettled=settled;
          const records=[];
          let current=0;
          drawBall=function(b,...rest){
            const m=ctx.getTransform(),scale=Math.hypot(m.a,m.b);
            // Only count an animated sink, never an ordinary live rack ball.
            if(!b.potted && (b.id===1||b.id===9) &&
               (scale<.999 || ctx.globalAlpha<.999)){
              records.push({t:current,id:b.id,scale,
                            alpha:ctx.globalAlpha,x:b.x,y:b.y});
            }
            return oldDraw(b,...rest);
          };
          physics=()=>{};
          settled=()=>false;
          soundOn=false;
          function at(t){current=t;frame(t);
            return records.filter(r=>r.t===t);}
          function start(){
            rack();breakShot=false;showPower(70);shoot();
            last=1000;accumulator=0;slowFrameStreak=0;
          }
          try {
            start();
            const before={cue:balls[0].x,turn,power};
            pocketBall(balls.find(b=>b.id===1));
            const early=at(1030),middle=at(1100),late=at(1160),gone=at(1230);
            const after={cue:balls[0].x,turn,power,potted:balls.find(b=>b.id===1).potted,
                         pocketed:[...shot.pocketed]};
            start();
            pocketBall(balls.find(b=>b.id===1));
            pocketBall(balls.find(b=>b.id===9));
            const simultaneous=at(1030);
            rack();
            const afterRack=at(1060);
            start();
            const snapshotBefore=snapshot();
            pocketBall(balls.find(b=>b.id===1));
            at(1030);
            restore(snapshotBefore);
            const afterUndo=at(1060);
            start();
            pocketBall(balls.find(b=>b.id===1));
            settled=()=>true;
            const settledDraw=at(1030);
            const settledState={shooting,shot,turn};
            const idleDraw=at(1100),idleEnd=at(1230);
            return {early,middle,late,gone,before,after,simultaneous,
                    afterRack,afterUndo,settledDraw,settledState,idleDraw,idleEnd};
          }finally{
            drawBall=oldDraw;physics=oldPhysics;settled=oldSettled;
          }
        }""")
        first=lambda key:next((x for x in result[key] if x['id']==1),None)
        a,b,c=first('early'),first('middle'),first('late')
        check(label+' pocketed ball remains visible at initial sink',
              a is not None and .05<a['scale']<1 and .05<a['alpha']<1,a)
        check(label+' pocketed ball shrinks progressively',
              all(x is not None for x in (a,b,c)) and a['scale']>b['scale']>c['scale']>0,
              {'early':a,'middle':b,'late':c})
        check(label+' pocketed ball fades progressively',
              all(x is not None for x in (a,b,c)) and a['alpha']>b['alpha']>c['alpha']>=0,
              {'early':a,'middle':b,'late':c})
        check(label+' sink ends and no ghost remains',
              first('gone') is None,result['gone'])
        before,after=result['before'],result['after']
        check(label+' sink never changes cue position or selected power',
              before['cue']==after['cue'] and before['power']==after['power'],
              {'before':before,'after':after})
        check(label+' pocket physics and match record remain authoritative',
              after['potted'] and after['pocketed']==[1] and after['turn']==before['turn'],
              after)
        check(label+' simultaneous pocketed balls each animate',
              {r['id'] for r in result['simultaneous']}=={1,9},
              result['simultaneous'])
        check(label+' NEW RACK removes stale pocket visuals',
              not result['afterRack'],result['afterRack'])
        check(label+' RETRY SHOT removes stale pocket visuals',
              not result['afterUndo'],result['afterUndo'])
        check(label+' pocket animation survives shot settlement',
              not result['settledState']['shooting'] and first('settledDraw') is not None,
              {'state':result['settledState'],'draw':result['settledDraw']})
        check(label+' idle frames continue pocket fall',
              first('idleDraw') is not None,result['idleDraw'])
        check(label+' idle animation ends without lingering ghost',
              not result['idleEnd'],result['idleEnd'])
        check(label+' no Chromium JavaScript errors',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_POCKET_SINK_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Chromium canvas rendering, not Samsung A37 device/human acceptance'
},indent=2))
print('Pocket sink visuals:',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
