"""Scratched cue ball must not appear twice during pocket-sink recovery.

A fast scratch can settle in the same frame as pocket capture. The live cue is
respawned for ball-in-hand while the pocket ghost is still fading. Rendering
both produces two white balls and a visible teleport. Browser-only validation;
physical Samsung A37 and independent human acceptance remain release-blocking.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name,ok,detail):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:print('FAIL',name,json.dumps(detail),flush=True)

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
        tag=f'{width}x{height}'
        for scenario in ('scratch','scratch-quick-place','object-pot'):
            state=page.evaluate("""(scenario)=>{
                freshRack();breakShot=false;showPower(75);
                shot={player:turn,breakShot:false,firstHit:null,
                    railAfterContact:false,pocketed:[],scratch:false,
                    targetEight:false};
                shooting=true;
                if(scenario==='object-pot'){shot.firstHit=1;shot.railAfterContact=true}
                const target=scenario==='object-pot'?balls[1]:balls[0];
                pocketBall(target);
                resolveShot();
                let drawn=[];
                const original=drawBall;
                drawBall=function(b,orientation){
                    if(b.id===0)drawn.push(pocketVisuals.includes(b)?'sink':'live');
                    return original(b,orientation);
                };
                try{render()}finally{drawBall=original}
                const bounds=canvas.getBoundingClientRect(),cue=balls[0];
                return {drawn,ghosts:pocketVisuals.map(g=>g.id),
                    cueAlive:!cue.potted,ballInHand,shotEnded:!shooting&&!shot,
                    cueX:cue.x,cueY:cue.y,rect:{
                        x:bounds.left+cue.x*bounds.width/W,
                        y:bounds.top+cue.y*bounds.height/H},
                    power};
            }""",scenario)
            label=f'{tag} {scenario}'
            check(label+' shot resolves and retains selected strength',
                state['shotEnded'] and abs(state['power']-75)<1e-7,state)
            check(label+' scratch grants legal ball-in-hand',
                (state['ballInHand'] and state['cueAlive']) if scenario!='object-pot'
                else (not state['ballInHand'] and state['cueAlive']),state)
            check(label+' draws exactly one cue ball during pocket transition',
                state['drawn'].count('sink')+state['drawn'].count('live')==1,state)
            if scenario=='scratch':
                check(label+' sinking white ball is shown, not duplicate live ball',
                    state['drawn']==['sink'],state)
                after=page.evaluate("""()=>{
                    for(const g of pocketVisuals)g.elapsed=POCKET_SINK_DURATION;
                    for(let i=pocketVisuals.length-1;i>=0;i--)
                        if(pocketVisuals[i].elapsed>=POCKET_SINK_DURATION)
                            pocketVisuals.splice(i,1);
                    let drawn=[];const original=drawBall;
                    drawBall=function(b,q){if(b.id===0)drawn.push('live');return original(b,q)};
                    try{render()}finally{drawBall=original}
                    return {drawn,ghosts:pocketVisuals.length,ballInHand};
                }""")
                check(label+' live cue appears after sink completes',
                    after['drawn']==['live'] and after['ghosts']==0 and
                    after['ballInHand'],after)
            if scenario=='scratch-quick-place':
                page.mouse.move(state['rect']['x'],state['rect']['y'])
                page.mouse.down()
                during=page.evaluate("""()=>({
                    ghosts:pocketVisuals.filter(g=>g.id===0).length,
                    placementPointer,ballInHand,shooting
                })""")
                check(label+' quick placement dismisses stale scratch ghost',
                    during['ghosts']==0 and during['placementPointer'] is not None
                    and during['ballInHand'] and not during['shooting'],during)
                page.mouse.up()
                final=page.evaluate("""()=>({
                    ballInHand,shooting,ghosts:pocketVisuals.filter(g=>g.id===0).length
                })""")
                check(label+' quick placement completes without extra shot',
                    not final['ballInHand'] and not final['shooting'] and
                    final['ghosts']==0,final)
        check(tag+' no JavaScript exceptions',not errors,errors)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_SCRATCH_GHOST_RESULTS.json').write_text(
    json.dumps({'passed':passed,'total':len(checks),'checks':checks,
      'limits':'Synthetic Chromium visual/interaction checks only; physical Samsung Galaxy A37 and independent human acceptance remain release-blocking.'},indent=2))
print('SCRATCH GHOST TRANSITION',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
