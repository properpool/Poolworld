from pathlib import Path
p=Path(__file__).parent/'POOL_WORLD_5.8_STAGING_MATCH.html'
s=p.read_text()
s=s.replace('Match Engine v5.8','Match Engine v5.9').replace('Local match engine · v5.8','Local match engine · v5.9')
start=s.index('function collideJaw(b){')
end=s.index('\nconst colors=',start)
s=s[:start]+'''// Fixed cushion/jaw contact with a dissipative rigid-sphere impulse.
// Ball mass=1, moment of inertia I=.4*m*r^2. Spin is omega*r.
// A tangent impulse consumes surface slip and transfers translational/rotational
// energy; Coulomb limit ensures a bounded response at the rubber contact.
function reflectCushion(b,nx,ny,restitution,friction){
  const vn=b.vx*nx+b.vy*ny;
  if(vn>=0)return false;
  const normalImpulse=-(1+restitution)*vn;
  b.vx+=normalImpulse*nx;b.vy+=normalImpulse*ny;
  const tx=-ny,ty=nx;
  const slip=b.vx*tx+b.vy*ty-b.spin;
  const maxTangent=friction*normalImpulse;
  const tangentImpulse=Math.max(-maxTangent,Math.min(maxTangent,-slip/3.5));
  b.vx+=tangentImpulse*tx;b.vy+=tangentImpulse*ty;
  b.spin-=2.5*tangentImpulse;
  if(-vn>.06){events.push(['rail',Math.min(1,-vn/5)]);if(shot&&shot.firstHit!==null)shot.railAfterContact=true;}
  return true;
}
function collideJaw(b){
  for(const [jx,jy] of jaws){
    let dx=b.x-jx,dy=b.y-jy,dist2=dx*dx+dy*dy;
    const min=rad+jawRadius;
    if(dist2>=min*min)continue;
    let d=Math.sqrt(dist2),nx,ny;
    if(d<1e-7){const speed=Math.hypot(b.vx,b.vy);nx=speed?-b.vx/speed:1;ny=speed?-b.vy/speed:0;d=0;}
    else{nx=dx/d;ny=dy/d;}
    b.x+=nx*(min-d+.001);b.y+=ny*(min-d+.001);
    reflectCushion(b,nx,ny,.76,.04);
  }
}
''' +s[end:]
start=s.index('const impact=Math.abs(b[vel]);')
end=s.index('}}}',start)
s=s[:start]+'''// Inward wall normal. Rail restitution and tangent friction are
      // dissipative even for large English; spin can drive rail throw only
      // by releasing rotational energy already carried by the ball.
      const nx=axis==='x'?(pos<lo?1:-1):0;
      const ny=axis==='y'?(pos<lo?1:-1):0;
      reflectCushion(b,nx,ny,.78,.04);''' +s[end:]
# remove duplicate rail event in axis block, handled by shared collision function
old="if(Math.abs(b[vel])>.06){events.push(['rail',Math.abs(b[vel])/5]);if(shot&&shot.firstHit!==null)shot.railAfterContact=true}"
assert old in s
s=s.replace(old,'',1)
Path(__file__).parent.joinpath('POOL_WORLD_5.9_STAGING_MATCH.html').write_text(s)
print('patched',len(s))
