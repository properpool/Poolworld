"""Samsung-scale touchscreen aiming, cut shots and six pockets with scattered live balls.

These are controlled physical fixtures with genuine Chromium pointer/touch input,
not human acceptance or measurements on a Samsung handset.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json, math, sys

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html'
checks=[]

def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),'detail':detail})
 print(('PASS' if ok else 'FAIL'),name,detail,flush=True)

def table_touch(page,x,y):
 r=page.locator('#table').bounding_box()
 page.touchscreen.tap(r['x']+x/1100*r['width'],r['y']+y/570*r['height'])

def touch_shoot(page):
 r=page.locator('#shoot').bounding_box()
 page.touchscreen.tap(r['x']+r['width']/2,r['y']+r['height']/2)

# Each ball is well away from the pocket, and the cue must cut the target
# rather than hit it from directly behind the object-to-pocket line.
fixtures=[
 ('top-left',320,240,79,78),
 ('top-middle',520,270,550,70),
 ('top-right',780,235,1021,78),
 ('bottom-left',330,330,79,492),
 ('bottom-middle',560,300,550,500),
 ('bottom-right',760,330,1021,492),
]
SETUP="""([ox,oy,hx,hy,cut])=>{
 rack();breakShot=false;
 const ulen=Math.hypot(hx-ox,hy-oy),ux=(hx-ox)/ulen,uy=(hy-oy)/ulen;
 const a=cut*Math.PI/180,dx=ux*Math.cos(a)-uy*Math.sin(a),dy=ux*Math.sin(a)+uy*Math.cos(a);
 const ghost=[ox-ux*2*rad,oy-uy*2*rad],cue=[ghost[0]-dx*110,ghost[1]-dy*110];
 const c=balls[0],t=balls.find(b=>b.id===1);
 c.x=cue[0];c.y=cue[1];t.x=ox;t.y=oy;
 const distSeg=(px,py,ax,ay,bx,by)=>{
  const vx=bx-ax,vy=by-ay,d=vx*vx+vy*vy;
  const f=d?Math.max(0,Math.min(1,((px-ax)*vx+(py-ay)*vy)/d)):0;
  return Math.hypot(px-ax-f*vx,py-ay-f*vy);
 };
 const spots=[];
 for(const y of [130,210,290,370,450])for(const x of [160,280,400,520,640,760,880,960]){
  if(Math.hypot(x-cue[0],y-cue[1])<48||Math.hypot(x-ox,y-oy)<48)continue;
  if(distSeg(x,y,cue[0],cue[1],ghost[0],ghost[1])<48)continue;
  if(distSeg(x,y,ox,oy,hx,hy)<48)continue;
  if(spots.some(p=>Math.hypot(x-p[0],y-p[1])<2*rad+4))continue;
  spots.push([x,y]);
 }
 const others=balls.filter(b=>b.id!==0&&b.id!==1);
 if(spots.length<others.length)throw Error('Insufficient scattered obstacle positions');
 others.forEach((b,i)=>{b.x=spots[i][0];b.y=spots[i][1]});
 aim=0;showPower(65);render();
 return {cue,ghost,aimPoint:[cue[0]+dx*95,cue[1]+dy*95],obstacles:others.length,
  cueLegal:canPlace(cue[0],cue[1]),object:[ox,oy],cut};
}"""

with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
 for w,h in [(390,844),(844,390)]:
  page=browser.new_page(viewport={'width':w,'height':h},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(SOURCE.read_text(),wait_until='load')

  # A fingertip landing near the cue must not snap the direction.
  r=page.locator('#table').bounding_box()
  cue=page.evaluate('() => ({x:balls[0].x,y:balls[0].y})')
  px=r['x']+cue['x']/1100*r['width']
  py=r['y']+cue['y']/570*r['height']
  page.evaluate('aim=0')
  page.touchscreen.tap(px+12,py+4)
  check(f'{w} near-cue finger landing preserves aim',abs(page.evaluate('aim'))<1e-10)
  page.touchscreen.tap(px+75,py+24)
  check(f'{w} deliberate distant table tap changes aim',abs(page.evaluate('aim'))>.1)

  # A cancelled precision gesture must revert, not silently commit.
  page.locator('#precision').click()
  box=page.locator('#table').bounding_box()
  x=box['x']+box['width']*.5;y=box['y']+box['height']*.5
  page.mouse.move(x,y);page.mouse.down()
  before=page.evaluate('aim')
  page.mouse.move(x+38,y,steps=5)
  check(f'{w} precision gesture changes angle before cancellation',abs(page.evaluate('aim')-before)>.03)
  page.locator('#table').dispatch_event('pointercancel',{'pointerId':1,'pointerType':'mouse'})
  check(f'{w} cancelled precision gesture restores angle',abs(page.evaluate('aim')-before)<1e-10 and page.evaluate('aimPointer===null && !dragAim'))
  page.mouse.up()
  page.locator('#precision').click()

  for name,ox,oy,hx,hy in fixtures:
   for cut in [-12,12]:
    setup=page.evaluate(SETUP,[ox,oy,hx,hy,cut])
    check(f'{w} {name} {cut:+} scattered balls and legal cue',
      setup['obstacles']==14 and setup['cueLegal'],setup)
    table_touch(page,*setup['aimPoint'])
    aim=page.evaluate('aim')
    expected=math.atan2(setup['ghost'][1]-setup['cue'][1],setup['ghost'][0]-setup['cue'][0])
    check(f'{w} {name} {cut:+} touch aim matches ghost-ball angle',
      abs(math.atan2(math.sin(aim-expected),math.cos(aim-expected)))<.001,{'aim':aim,'expected':expected})
    touch_shoot(page)
    state=page.evaluate("""() => {
     const fired=shooting,initialSpeed=Math.hypot(balls[0].vx,balls[0].vy);
     let n=0;while(!settled()&&n++<4500)physics(STEP);
     const firstHit=shot?.firstHit, potted=balls.find(b=>b.id===1).potted;
     const done=settled();if(done)resolveShot();
     return {fired,initialSpeed,firstHit,potted,done,steps:n,turn,group:groups[1],gameOver};
    }""")
    check(f'{w} {name} {cut:+} real-touch cut pot with live scattered balls',
      state['fired'] and state['firstHit']==1 and state['potted'] and state['done']
      and state['turn']==1 and state['group']=='solids' and not state['gameOver'],state)
  check(f'{w} no browser exceptions',not errors,errors)
  page.close()
 browser.close()
summary={'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,
 'limits':'Controlled layouts and Chromium touchscreen emulation only. No physical Samsung or human acceptance.'}
(ROOT/'POOL_WORLD_6.0_SCATTERED_TOUCH_RESULTS.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',summary['passed'],'/',summary['total'])
if summary['passed']!=summary['total']:sys.exit(1)
