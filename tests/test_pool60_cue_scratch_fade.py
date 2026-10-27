"""A scratched cue ball must fade as one coherent sphere, including its measle dots.

A canvas compositing regression previously let the six cue-ball dots ignore the
parent pocket-sink opacity. Synthetic Chromium frames are NOT a Samsung device
frame-rate, shot-feel, or human acceptance test.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in ((360,800),(390,844),(844,390),(768,1024)):
        label=f'{width}x{height}'
        page=browser.new_page(viewport={'width':width,'height':height},
                              is_mobile=width<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        data=page.evaluate("""()=>{
          const originalPhysics=physics,originalSettled=settled;
          const oldFill=ctx.fill.bind(ctx),oldImage=ctx.drawImage.bind(ctx);
          const frames=[],all=[];
          let stamp=0;
          ctx.fill=function(...args){
            if(ctx.fillStyle==='#ad3b42')
              all.push({t:stamp,kind:'dot',alpha:ctx.globalAlpha,
                        scale:Math.hypot(ctx.getTransform().a,ctx.getTransform().b)});
            return oldFill(...args);
          };
          ctx.drawImage=function(img,...args){
            if(img===shellSprites[0])
              all.push({t:stamp,kind:'shell',alpha:ctx.globalAlpha,
                        scale:Math.hypot(ctx.getTransform().a,ctx.getTransform().b)});
            return oldImage(img,...args);
          };
          physics=()=>{};settled=()=>false;soundOn=false;
          function at(t){
            stamp=t;frame(t);
            const records=all.filter(r=>r.t===t);
            const shell=records.filter(r=>r.kind==='shell');
            const dots=records.filter(r=>r.kind==='dot');
            const f={t,shell,dots,alphaAfter:ctx.globalAlpha};
            frames.push(f);return f;
          }
          try{
            rack();breakShot=false;showPower(70);shoot();
            const before={power,turn,position:[balls[0].x,balls[0].y],
                          speed:shotSpeed(power,false)};
            pocketBall(balls[0]);
            const scratch={potted:balls[0].potted,record:[...shot.pocketed],
                           foul:shot.scratch,power,turn};
            last=1000;accumulator=0;
            const early=at(1030),mid=at(1110),late=at(1170),end=at(1200);
            const after={power,turn,position:[balls[0].x,balls[0].y],
                         speed:shotSpeed(power,false)};
            rack();last=1200;
            const live=at(1230);
            return {before,scratch,after,early,mid,late,end,live,
                    frames,remainingGhosts:pocketVisuals.length};
          }finally{
            ctx.fill=oldFill;ctx.drawImage=oldImage;
            physics=originalPhysics;settled=originalSettled;
          }
        }""")
        early,mid,late,end,live=[data[k] for k in ('early','mid','late','end','live')]
        for name,frame in [('early',early),('middle',mid),('late',late)]:
            shell=frame['shell'];dots=frame['dots']
            check(label+f' {name} scratched cue shell is drawn once',
                  len(shell)==1,frame)
            check(label+f' {name} scratched cue measle dots remain visible',
                  len(dots)>=1,frame)
            check(label+f' {name} dots respect the parent fade',
                  len(shell)==1 and len(dots)>=1 and
                  all(0<=d['alpha']<=shell[0]['alpha']*.82+1e-6 for d in dots),
                  frame)
            check(label+f' {name} scratch rendering restores canvas opacity',
                  abs(frame['alphaAfter']-1)<1e-8,frame)
        check(label+' cue shell fades progressively',
              len(early['shell'])==len(mid['shell'])==len(late['shell'])==1
              and early['shell'][0]['alpha']>mid['shell'][0]['alpha']>late['shell'][0]['alpha']>0,
              {'early':early['shell'],'mid':mid['shell'],'late':late['shell']})
        check(label+' cue dots fade progressively with shell',
              all(f['dots'] for f in (early,mid,late)) and
              max(d['alpha'] for d in early['dots'])>
              max(d['alpha'] for d in mid['dots'])>
              max(d['alpha'] for d in late['dots']),
              {'early':early['dots'],'mid':mid['dots'],'late':late['dots']})
        check(label+' late scratch dots are nearly transparent',
              late['dots'] and max(d['alpha'] for d in late['dots'])<.12,
              late['dots'])
        check(label+' completed scratch sink has no remaining ghost',
              not end['shell'] and not end['dots'],end)
        check(label+' normal live cue ball stays fully opaque',
              len(live['shell'])==1 and abs(live['shell'][0]['alpha']-1)<1e-8,
              live)
        check(label+' live cue measle dots remain correctly visible',
              len(live['dots'])>=1 and all(.4<=d['alpha']<=.82 for d in live['dots']),
              live['dots'])
        check(label+' scratch updates only authoritative foul and pocket record',
              data['scratch']['potted'] and data['scratch']['foul']
              and data['scratch']['record']==[0]
              and data['scratch']['power']==data['before']['power']
              and data['scratch']['turn']==data['before']['turn'],
              data['scratch'])
        check(label+' visual animation never changes power, turn or cue position',
              data['before']==data['after'],
              {'before':data['before'],'after':data['after']})
        check(label+' no Chromium exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_CUE_SCRATCH_FADE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limits':'Synthetic Chromium canvas only; physical Samsung and human acceptance not established.'
},indent=2))
print('CUE SCRATCH FADE',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
