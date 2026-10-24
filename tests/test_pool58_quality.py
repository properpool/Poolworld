from pathlib import Path
from playwright.sync_api import sync_playwright
import json,math,statistics
P=Path(__file__).resolve().parent.parent/'POOL_WORLD_5.8_STAGING_MATCH.html'
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    print(('PASS' if ok else 'FAIL')+' '+name+(f' {detail}' if detail is not None else ''))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
    for width,height in [(320,720),(360,780),(390,844),(412,915),(768,1024),(844,390)]:
        page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=2,is_mobile=True,has_touch=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(P.read_text(),wait_until='load')
        dims=page.evaluate('''() => ({overflow:document.documentElement.scrollWidth>innerWidth,
           board:document.getElementById('table').getBoundingClientRect().toJSON(),
           shoot:document.getElementById('shoot').getBoundingClientRect().toJSON(),
           left:document.getElementById('aimLeft').getBoundingClientRect().toJSON(),
           right:document.getElementById('aimRight').getBoundingClientRect().toJSON()})''')
        check(f'no horizontal overflow {width}x{height}',not dims['overflow'])
        check(f'usable pool canvas {width}x{height}',dims['board']['width']>=180 and dims['board']['height']>=90,{'width':round(dims['board']['width']),'height':round(dims['board']['height'])})
        check(f'no JS errors {width}x{height}',not errors,errors)
        if width in (320,390,844):
            page.evaluate('aim=0')
            page.locator('#aimLeft').click()
            a=page.evaluate('aim')
            check(f'fine aim left click {width}',abs(a+math.pi/360)<1e-9,a)
            page.locator('#aimRight').click()
            check(f'fine aim right click {width}',abs(page.evaluate('aim'))<1e-9)
            box=page.locator('#table').bounding_box()
            x,y=700,285
            page.touchscreen.tap(box['x']+x*box['width']/1100,box['y']+y*box['height']/570)
            check(f'touch-to-aim {width}',abs(page.evaluate('aim'))<.01)
        page.close()
    page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page.set_content(P.read_text(),wait_until='load')
    illegal=page.evaluate('''() => {
       rack();breakShot=false;groups={1:'solids',2:'stripes'};
       for(let i=1;i<=6;i++)balls.find(b=>b.id===i).potted=true;
       const s={player:1,breakShot:false,firstHit:7,railAfterContact:true,pocketed:[7,8],scratch:false,targetEight:false};
       balls.find(b=>b.id===7).potted=true;balls.find(b=>b.id===8).potted=true;shot=s;resolveShot();
       return {gameOver,winner,turn};
    }''')
    check('last group ball plus eight in same shot is a loss',illegal['gameOver'] and illegal['winner']==2,illegal)
    legal=page.evaluate('''() => {
       rack();breakShot=false;groups={1:'solids',2:'stripes'};
       for(let i=1;i<=7;i++)balls.find(b=>b.id===i).potted=true;
       shot={player:1,breakShot:false,firstHit:8,railAfterContact:true,pocketed:[8],scratch:false,targetEight:true};
       balls.find(b=>b.id===8).potted=true;resolveShot();return {gameOver,winner};
    }''')
    check('legal eight remains a win',legal['gameOver'] and legal['winner']==1,legal)
    energy=page.evaluate('''() => {
      rack();for(const b of balls)if(b.id!==0&&b.id!==1)b.potted=true;
      const c=balls[0],o=balls.find(b=>b.id===1);
      c.x=400;c.y=285;c.vx=3;c.vy=0;c.spin=0;c.follow=0;
      o.x=400+rad*2-.1;o.y=285;o.vx=0;o.vy=0;
      shot={player:1,breakShot:false,firstHit:null,railAfterContact:false,pocketed:[],scratch:false};
      const before=c.vx*c.vx+o.vx*o.vx;physics(STEP);
      return {before,after:c.vx*c.vx+c.vy*c.vy+o.vx*o.vx+o.vy*o.vy,firstHit:shot.firstHit};
    }''')
    check('head-on collision conserves/bounds kinetic energy',energy['firstHit']==1 and energy['after']<=energy['before']*1.02,energy)
    frame=page.evaluate('''() => new Promise(resolve=>{
      const times=[];let previous=0;
      function measure(t){if(previous)times.push(t-previous);previous=t;
        if(times.length<90)requestAnimationFrame(measure);
        else {times.sort((a,b)=>a-b);resolve({median_ms:times[44],p95_ms:times[85],max_ms:times[89]})}}
      requestAnimationFrame(measure);
    })''')
    check('90 rendered frames measured in mobile browser',frame['median_ms']>0 and frame['p95_ms']>0,frame)
    page.close();browser.close()
passed=sum(v['passed'] for v in checks)
result={'passed':passed,'total':len(checks),'checks':checks,'mobile_frame_timing_is_emulation_only':True}
(P.parent/'POOL_WORLD_5.8_QUALITY_RESULTS.json').write_text(json.dumps(result,indent=2))
print('SUMMARY',passed,'/',len(checks))
if passed!=len(checks):raise SystemExit(1)
