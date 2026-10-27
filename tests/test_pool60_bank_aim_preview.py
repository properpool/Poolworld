"""Chromium regression: show a physically plausible one-cushion aiming preview only on
solid rubber, never through pockets or an intervening object ball.
This is a visual aiming aid, not a physics change or physical Samsung acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys,math
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    if not ok: print('FAIL',name,detail,flush=True)
FIXTURE=r"""({kind,guideEnabled})=>{
 rack();
 balls=[makeBall(0,350,260)];
 aim=-Math.PI/3;
 if(kind==='left'){balls[0].x=320;balls[0].y=300;aim=Math.PI*1.1}
 if(kind==='pocket'){balls[0].x=550;balls[0].y=270;aim=-Math.PI/2}
 if(kind==='blocked'){balls.push(makeBall(1,390.4,190))}
 if(kind==='bounceBlocked'){balls.push(makeBall(1,500,160))}
 guide=guideEnabled;
 const records=[],orig={move:ctx.moveTo,line:ctx.lineTo,stroke:ctx.stroke};
 let path=[];
 ctx.moveTo=function(x,y){path=[['M',x,y]];return orig.move.apply(this,arguments)};
 ctx.lineTo=function(x,y){path.push(['L',x,y]);return orig.line.apply(this,arguments)};
 ctx.stroke=function(){records.push({style:String(this.strokeStyle),path:path.slice()});path=[];return orig.stroke.apply(this,arguments)};
 try{drawAim()}finally{ctx.moveTo=orig.move;ctx.lineTo=orig.line;ctx.stroke=orig.stroke}
 const bank=records.filter(v=>v.style==='#9ee8dc');
 return {bank,records:records.length,aim,kind,guideEnabled,shooting,gameOver,power,
         cue:{x:balls[0].x,y:balls[0].y},error:bank.some(v=>v.path.some(p=>p.slice(1).some(n=>!Number.isFinite(n))))};
}"""
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
      executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
      args=['--no-sandbox'])
    for w,h in ((390,844),(844,390),(768,1024),(1366,768)):
        page=browser.new_page(viewport={'width':w,'height':h},
            is_mobile=w<1000,has_touch=w<1000)
        page.evaluate('window.requestAnimationFrame=()=>0')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        tag=f'{w}x{h}'
        for kind in ('top','left','pocket','blocked','bounceBlocked'):
            r=page.evaluate(FIXTURE,{'kind':kind,'guideEnabled':True})
            bank=r['bank']
            expected=kind in ('top','left','bounceBlocked')
            check(tag+' '+kind+' bank preview present only for playable rubber',
                  (len(bank)==1)==expected,{'bank':bank,'records':r['records']})
            if expected and bank:
                p=bank[0]['path']
                check(tag+' '+kind+' bank path starts and ends with finite endpoints',
                    len(p)>=2 and p[0][0]=='M' and p[-1][0]=='L' and not r['error'],p)
                if len(p)>=2:
                    x,y=p[0][1:];ex,ey=p[-1][1:]
                    check(tag+' '+kind+' preview remains inside legal cloth',
                        91.19<=x<=1008.81 and 90.19<=y<=479.81 and
                        91.19<=ex<=1008.81 and 90.19<=ey<=479.81,(x,y,ex,ey))
                    if kind in ('top','bounceBlocked'):
                        check(tag+' '+kind+' upward approach rebounds downward',
                            abs(y-90.2)<.15 and ey>y+20 and ex>x+15,(x,y,ex,ey))
                    if kind=='left':
                        check(tag+' leftward approach rebounds rightward',
                            abs(x-91.2)<.15 and ex>x+20,(x,y,ex,ey))
                    if kind=='bounceBlocked':
                        check(tag+' rebound preview stops at first object ball',
                            ex<500 and ey<190,(x,y,ex,ey))
            check(tag+' '+kind+' preview does not alter gameplay state',
                not r['shooting'] and not r['gameOver'] and r['power']==45 and
                abs(r['cue']['x']-(320 if kind=='left' else 550 if kind=='pocket' else 350))<1e-6,r)
        no=page.evaluate(FIXTURE,{'kind':'top','guideEnabled':False})
        check(tag+' guide OFF suppresses bank preview',not no['bank'],no)
        check(tag+' no browser errors',not errors,errors)
        page.close()
    browser.close()
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,
        'limits':'Chromium visual geometry only; no physical Samsung performance or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_BANK_AIM_RESULTS.json').write_text(json.dumps(result,indent=2))
print('BANK AIM',result['passed'],'/',result['total'],flush=True)
if result['passed']!=result['total']:sys.exit(1)
