"""Pool World 5.8: bounded rigid-ball tangential impulses and draw/follow energy transfer."""
from pathlib import Path
import hashlib
src=Path(__file__).with_name('POOL_WORLD_5.7_STAGING_MATCH.html')
dst=Path(__file__).with_name('POOL_WORLD_5.8_STAGING_MATCH.html')
s=src.read_text()
assert hashlib.sha256(src.read_bytes()).hexdigest()=='aff8d8de40a317adbe9e4dcbfa278750d363a662dc377bde713698917b6b3c8c'
assert s.count('Match Engine v5.7')==1
s=s.replace('Match Engine v5.7','Match Engine v5.8').replace('Local match engine · v5.7','Local match engine · v5.8')
old="""let d=Math.sqrt(d2);if(d<.0001){dx=min;dy=0;d=min}const nx=dx/d,ny=dy/d,overlap=min-d;"""
new="""let d=Math.sqrt(d2),nx,ny;
 // An exact centre overlap must separate; use relative motion as a stable normal.
 if(d<1e-6){const rvx=b.vx-a.vx,rvy=b.vy-a.vy,rv=Math.hypot(rvx,rvy);nx=rv>1e-8?-rvx/rv:1;ny=rv>1e-8?-rvy/rv:0;d=0}
 else{nx=dx/d;ny=dy/d}
 const overlap=min-d;"""
assert s.count(old)==1;s=s.replace(old,new)
old="""const impulse=-(1+.955)*rel/2;a.vx-=impulse*nx;a.vy-=impulse*ny;b.vx+=impulse*nx;b.vy+=impulse*ny;const tx=-ny,ty=nx;const tangent=(b.vx-a.vx)*tx+(b.vy-a.vy)*ty;const fr=Math.max(-.055,Math.min(.055,tangent*.014));a.vx+=fr*tx;a.vy+=fr*ty;b.vx-=fr*tx;b.vy-=fr*ty;if(Math.abs(rel)>.11)events.push(['ball',Math.abs(rel)/5]);if(a.id===0&&Math.abs(a.follow)>.1){
       // Approximate follow/draw from the cue ball's retained longitudinal rotation.
       // A head-on draw must be able to reverse the cue after transferring momentum.
       const spinKick=Math.max(-.95,Math.min(.95,a.follow*.36));
       a.vx+=nx*spinKick;a.vy+=ny*spinKick;a.follow*=.32
      }"""
new="""// Equal-mass normal impulse, coefficient of restitution 0.955.
 const cueIncomingX=a.vx,cueIncomingY=a.vy;
 const impulse=-(1+.955)*rel/2;a.vx-=impulse*nx;a.vy-=impulse*ny;b.vx+=impulse*nx;b.vy+=impulse*ny;
 const tx=-ny,ty=nx;
 // Rigid spheres: I=2/5 m*r². `spin` is tangential surface speed (omega*r).
 // Relative surface slip includes both balls' spin; Coulomb friction transfers
 // spin and throw without creating kinetic energy. Effective tangent mass = 7.
 const slip=(b.vx-a.vx)*tx+(b.vy-a.vy)*ty-a.spin-b.spin;
 const tangentImpulse=Math.max(-.08*impulse,Math.min(.08*impulse,-slip/7));
 a.vx-=tangentImpulse*tx;a.vy-=tangentImpulse*ty;
 b.vx+=tangentImpulse*tx;b.vy+=tangentImpulse*ty;
 a.spin-=2.5*tangentImpulse;b.spin-=2.5*tangentImpulse;
 if(Math.abs(rel)>.11)events.push(['ball',Math.abs(rel)/5]);
 if(a.id===0&&Math.abs(a.follow)>.1){
  // Follow/draw uses stored longitudinal rotation, not a free velocity kick.
  // Spend no more rotational energy than is released at impact (I/m*r²=.4).
  const previousFollow=a.follow,retained=previousFollow*.32;
  const incomingSpeed=Math.hypot(cueIncomingX,cueIncomingY);
  const fx=incomingSpeed>1e-8?cueIncomingX/incomingSpeed:nx;
  const fy=incomingSpeed>1e-8?cueIncomingY/incomingSpeed:ny;
  const requested=Math.max(-.95,Math.min(.95,previousFollow*.36));
  const sign=Math.sign(requested),along=a.vx*fx+a.vy*fy;
  const released=.4*(previousFollow*previousFollow-retained*retained);
  const maxKick=Math.max(0,-sign*along+Math.sqrt(along*along+released));
  const kick=sign*Math.min(Math.abs(requested),maxKick);
  a.vx+=fx*kick;a.vy+=fy*kick;a.follow=retained;
 }"""
assert s.count(old)==1;s=s.replace(old,new)
# explicit comment in header, not sound data
s=s.replace('const STEP=1/120;let accumulator=0,last=0;',
'''// Physics: fixed 120Hz steps; translational and rotational impulses bounded.
const STEP=1/120;let accumulator=0,last=0;''')
dst.write_text(s)
# preserve all approved recordings byte-for-byte
import re
sounds=lambda x:re.findall(r'(?:ball|cue|rail|pocket):"data:audio/ogg;base64,[A-Za-z0-9+/=]+"',x)
assert sounds(src.read_text())==sounds(s) and len(sounds(s))==4
print('Created',dst, 'bytes',dst.stat().st_size,'SHA256',hashlib.sha256(dst.read_bytes()).hexdigest())
