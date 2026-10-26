"""Regression for coalesced final-release aim on actual canvas input paths.

A fast pointer can deliver pointerdown followed by pointerup with no intermediate
pointermove. The final release coordinate must control the cue angle; otherwise
the displayed direction and shot can disagree with the player's finger.
Chromium mouse/touch events and synthetic final-release event are NOT physical
Samsung A37 or independent human acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]

def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok:
        print('FAIL',name,detail,flush=True)

def angle_error(a,b):
    return abs(math.atan2(math.sin(a-b),math.cos(a-b)))

def screen(box,x,y):
    return (box['x']+x/1100*box['width'],box['y']+y/570*box['height'])

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1100,has_touch=True)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        page.evaluate("""() => {
            window.aimDraws=0;
            const original=render;
            render=function(){aimDraws++;original()};
            last=0;accumulator=0;frame(1000);aimDraws=0;
        }""")
        box=page.locator('#table').bounding_box()
        label=f'{width}x{height}'
        cdp=page.context.new_cdp_session(page)

        # Real mouse press, with a coalesced pointerup delivered at a DIFFERENT
        # location without an intermediate pointermove. The pointerup itself
        # must update the final angle, not merely clear the pointer capture.
        page.evaluate('rack();aim=0;renderDirty=false;aimDraws=0')
        x1,y1=screen(box,430,205)
        x2,y2=screen(box,700,365)
        cdp.send('Input.dispatchMouseEvent',{
            'type':'mouseMoved','x':x1,'y':y1,'buttons':0})
        cdp.send('Input.dispatchMouseEvent',{
            'type':'mousePressed','x':x1,'y':y1,
            'button':'left','buttons':1,'clickCount':1})
        pressed=page.evaluate("""() => ({
            active:dragAim&&aimPointer!==null,
            angle:aim,cue:[balls[0].x,balls[0].y]
        })""")
        initial=math.atan2(205-pressed['cue'][1],430-pressed['cue'][0])
        final=math.atan2(365-pressed['cue'][1],700-pressed['cue'][0])
        check(label+' real mouse press starts aiming',pressed['active'] and angle_error(pressed['angle'],initial)<.005,pressed)
        page.evaluate("""({x,y})=>{
            document.getElementById('table').dispatchEvent(new PointerEvent('pointerup',{
                pointerId:aimPointer,pointerType:'mouse',clientX:x,clientY:y,
                bubbles:true
            }));
        }""",{'x':x2,'y':y2})
        ended=page.evaluate("""() => ({aim,active:dragAim,ptr:aimPointer,shooting})""")
        check(label+' quick release commits final absolute angle',
            angle_error(ended['aim'],final)<.005,{'actual':ended,'expected':final})
        check(label+' mouse release clears drag without shooting',
            not ended['active'] and ended['ptr'] is None and not ended['shooting'],ended)
        painted=page.evaluate("""() => {
            frame(last+1000/60);return {draws:aimDraws,dirty:renderDirty}
        }""")
        check(label+' quick mouse release visibly repaints next frame',
            painted['draws']>=1 and not painted['dirty'],painted)
        shot=page.evaluate("""() => {
            showPower(75);breakShot=false;shoot();
            return {direction:Math.atan2(balls[0].vy,balls[0].vx),
                speed:Math.hypot(balls[0].vx,balls[0].vy),
                expected:shotSpeed(75,false)}
        }""")
        check(label+' actual shot follows final release direction',
            angle_error(shot['direction'],final)<.005 and abs(shot['speed']-shot['expected'])<1e-8,shot)
        cdp.send('Input.dispatchMouseEvent',{
            'type':'mouseReleased','x':x2,'y':y2,'button':'left','buttons':0,'clickCount':1})

        # Real touchStart on the cue ball creates a relative fine-aim gesture.
        # Simulate the browser coalescing the entire movement into pointerup.
        page.evaluate('rack();aim=Math.PI/3;renderDirty=false;aimDraws=0')
        cue=page.evaluate('({x:balls[0].x,y:balls[0].y})')
        tx,ty=screen(box,cue['x'],cue['y'])
        cdp.send('Input.dispatchTouchEvent',{
            'type':'touchStart','touchPoints':[{'x':tx+5,'y':ty+3,'id':1}]})
        touch_start=page.evaluate("""() => ({
            aim,active:dragAim&&aimFineDrag&&aimPointer!==null
        })""")
        check(label+' actual cue touch starts relative aim',
            touch_start['active'] and angle_error(touch_start['aim'],math.pi/3)<1e-7,touch_start)
        page.evaluate("""({x,y})=>{
            document.getElementById('table').dispatchEvent(new PointerEvent('pointerup',{
                pointerId:aimPointer,pointerType:'touch',clientX:x,clientY:y,
                bubbles:true
            }));
        }""",{'x':tx+77,'y':ty+3})
        fine=page.evaluate("""() => ({aim,active:dragAim,ptr:aimPointer,fine:aimFineDrag})""")
        expected=math.pi/3+72*.13*math.pi/180
        check(label+' quick cue drag commits final relative angle',
            angle_error(fine['aim'],expected)<.002,{'actual':fine,'expected':expected})
        check(label+' touch release clears fine drag',
            not fine['active'] and fine['ptr'] is None and not fine['fine'],fine)
        check(label+' final touch position affects next shot',
            page.evaluate("""() => {breakShot=false;showPower(75);shoot();
                return Math.atan2(balls[0].vy,balls[0].vx)}""") and
            angle_error(page.evaluate('Math.atan2(balls[0].vy,balls[0].vx)'),expected)<.002)
        cdp.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]})

        # Releasing outside the table must not snap aim toward the top-left
        # of the viewport while pointer capture is still active.
        page.evaluate('rack();aim=1.12;renderDirty=false')
        cdp.send('Input.dispatchTouchEvent',{
            'type':'touchStart','touchPoints':[{'x':tx+5,'y':ty+3,'id':1}]})
        page.evaluate("""() => {
            document.getElementById('table').dispatchEvent(new PointerEvent('pointerup',{
                pointerId:aimPointer,pointerType:'touch',clientX:0,clientY:0,
                bubbles:true
            }));
        }""")
        outside=page.evaluate('({aim,dragAim,aimPointer})')
        check(label+' off-table release preserves prior aim',
            angle_error(outside['aim'],1.12)<1e-8 and not outside['dragAim'] and outside['aimPointer'] is None,outside)
        cdp.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]})
        check(label+' no browser exceptions',not errors,errors)
        page.close()
    browser.close()

result={'total':len(checks),'passed':sum(c['passed'] for c in checks),'checks':checks,
    'limits':'Chromium input emulation and synthetic final release; not Samsung A37 or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_FINAL_AIM_RESULTS.json').write_text(json.dumps(result,indent=2))
print(f"Final-release aim and input-to-render: {result['passed']}/{result['total']} checks",flush=True)
if result['passed']!=result['total']:
    sys.exit(1)
