// ===== أدوات =====
const $=s=>document.querySelector(s);
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const P=(t,a,b)=>clamp((t-a)/(b-a));
const lerp=(a,b,k)=>a+(b-a)*k;
const eOut=k=>1-Math.pow(1-k,3);
const eIn=k=>k*k*k;
const eIO=k=>k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
const eExpo=k=>k>=1?1:1-Math.pow(2,-10*k);
const back=(k,s=1.7)=>1+(s+1)*Math.pow(k-1,3)+s*Math.pow(k-1,2);
function rng(seed){return()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
const R=rng(42);

const put=(el,cx,cy,w,h,z=0,ry=0,rx=0,s=1,rz=0)=>{
  el.style.transform=`translate3d(${cx-w/2}px,${cy-h/2}px,${z}px) rotateY(${ry}deg) rotateX(${rx}deg) rotateZ(${rz}deg) scale(${s})`;
};
document.querySelectorAll('.o').forEach(e=>e.style.transformOrigin='50% 50%');

// ===== المتجر: تحويل إحداثياته لإحداثيات العالم =====
const SC=1.4, SX=540, SY=960;
const sw=(lx,ly,s=SC)=>[SX+(lx-300)*s, SY+(ly-625)*s];

// ===== البطاقات الطائرة =====
const CARDS=[
 {id:'#cStore',w:580,h:300,p:[520,430,60,-10,6],t0:0.15,to:[300,361],ts:1.32},
 {id:'#cProd', w:390,h:520,p:[285,930,140,14,2],t0:0.5, to:[440,790],ts:0.95},
 {id:'#cOrd',  w:470,h:420,p:[785,1010,-40,-14,2],t0:0.85,to:[70,98],ts:0.12},
 {id:'#cCust', w:480,h:270,p:[360,1450,80,10,-4],t0:1.2, to:[300,1340],ts:1.6},
 {id:'#cNote', w:470,h:124,p:[765,1570,200,-8,0],t0:1.5, to:[70,98],ts:0.1},
 {id:'#cCats', w:560,h:96, p:[560,175,-60,4,8],t0:1.75,to:[300,535],ts:1.37},
];
CARDS.forEach(c=>c.el=$(c.id));
const HUB=[540,1000];

// روابط SVG
const svg=$('#links');
svg.innerHTML=CARDS.map((c,i)=>`<line id="lg${i}" stroke="rgba(62,230,245,.25)" stroke-width="10" stroke-linecap="round"/>
 <line id="ln${i}" stroke="#9ef4ff" stroke-width="2.5" stroke-linecap="round"/>
 <circle id="pd${i}" r="7" fill="#dffcff"/>`).join('')+
 `<circle id="hubG" cx="${HUB[0]}" cy="${HUB[1]}" r="60" fill="rgba(62,230,245,.25)"/><circle id="hub" cx="${HUB[0]}" cy="${HUB[1]}" r="16" fill="#e8fdff"/>`;

// إشعارات حول الجوال
const NTS=[
 {id:'#n0',p:[300,500,240,8],t0:9.0},
 {id:'#n1',p:[790,800,200,-8],t0:9.5},
 {id:'#n2',p:[295,1330,260,8],t0:10.0},
 {id:'#n3',p:[785,1610,220,-8],t0:10.5},
];
NTS.forEach(n=>n.el=$(n.id));

// ===== جسيمات =====
const bgc=$('#bgc').getContext('2d'), fx=$('#fx').getContext('2d');
const DUST=[...Array(150)].map(()=>({x:R()*1080,y:R()*1920,s:0.6+R()*2.4,a:0.15+R()*0.5,v:8+R()*30,ph:R()*6.28,big:R()<0.12}));
const LP=window.LOGO_PTS, LX=130, LY=600;
const PTS=LP.map(([x,y,teal])=>({sx:260+R()*560,sy:330+R()*1270,tx:LX+x,ty:LY+y,teal,s0:11.0+R()*0.28,d:0.62+R()*0.18,amp:(R()-.5)*520,sz:1.4+R()*1.8}));
const SPARKS=[...Array(260)].map(()=>{const a=R()*6.283,sp=250+R()*900;return{a,sp,x:LX+R()*820,y:LY+R()*316,sz:1+R()*2.2,life:0.5+R()*0.7}});

function streak(ctx,t,t0,dur,ang,off,w,alpha){
  const k=P(t,t0,t0+dur); if(k<=0||k>=1) return;
  const L=2600, cx=lerp(-900,1980,eIO(k))+off, cy=960+off*0.4;
  ctx.save(); ctx.translate(cx,cy); ctx.rotate(ang);
  const g=ctx.createLinearGradient(-L/2,0,L/2,0);
  g.addColorStop(0,'rgba(62,230,245,0)'); g.addColorStop(.5,`rgba(190,250,255,${alpha*Math.sin(Math.PI*k)})`); g.addColorStop(1,'rgba(62,230,245,0)');
  ctx.fillStyle=g; ctx.fillRect(-L/2,-w/2,L,w); ctx.restore();
}

function drawBG(t){
  const c=bgc; c.clearRect(0,0,1080,1920);
  c.globalCompositeOperation='lighter';
  DUST.forEach(d=>{
    const y=((d.y-t*d.v)%1920+1920)%1920, x=d.x+Math.sin(t*0.7+d.ph)*18;
    if(d.big){const g=c.createRadialGradient(x,y,0,x,y,d.s*14);g.addColorStop(0,`rgba(62,230,245,${d.a*0.12})`);g.addColorStop(1,'rgba(62,230,245,0)');c.fillStyle=g;c.fillRect(x-d.s*14,y-d.s*14,d.s*28,d.s*28);}
    else{c.fillStyle=`rgba(150,240,255,${d.a*(0.6+0.4*Math.sin(t*2+d.ph))})`;c.beginPath();c.arc(x,y,d.s,0,6.283);c.fill();}
  });
  // خطوط ضوء خفيفة دائمة
  streak(c,t,((t/5)|0)*5+0.8,3.2,-0.5,-200,2,0.18);
  c.globalCompositeOperation='source-over';
}

function drawFX(t){
  const c=fx; c.clearRect(0,0,1080,1920); c.globalCompositeOperation='lighter';
  // خطوط ضوء الانتقالات
  for(const [t0,off] of [[3.75,0],[7.8,120],[11.75,-80],[0.0,200]]){
    streak(c,t,t0,0.6,-0.52,off,5,0.9); streak(c,t,t0+0.05,0.6,-0.52,off+70,2,0.7); streak(c,t,t0+0.1,0.6,-0.52,off-90,1.5,0.6);
  }
  // جسيمات تتجمع لتكوّن الشعار
  if(t>=11.0 && t<12.6){
    const fade=1-P(t,12.02,12.5);
    PTS.forEach(p=>{
      const k=eIO(P(t,p.s0,p.s0+p.d));
      const pre=P(t,11.0,p.s0);
      let x=lerp(p.sx,p.tx,k), y=lerp(p.sy,p.ty,k);
      const dx=p.tx-p.sx, dy=p.ty-p.sy, L=Math.hypot(dx,dy)||1;
      const sw=Math.sin(Math.PI*k)*p.amp;
      x+=-dy/L*sw + (1-k)*Math.sin(t*3+p.amp)*20*pre; y+=dx/L*sw;
      const col=k>0.8&&p.teal?`rgba(40,190,215,${fade})`:`rgba(${lerp(120,235,k)|0},${lerp(235,252,k)|0},255,${fade*(0.5+0.5*Math.min(1,pre*3+k))})`;
      c.fillStyle=col; c.beginPath(); c.arc(x,y,p.sz*(1+0.6*Math.sin(Math.PI*k)),0,6.283); c.fill();
    });
  }
  // شرارات + موجة عند الضربة
  if(t>=12.0 && t<13.4){
    const e=t-12.0;
    SPARKS.forEach(s=>{const k=e/s.life; if(k>=1)return;
      const d=s.sp*eOut(clamp(k))*0.45;
      c.fillStyle=`rgba(190,250,255,${(1-k)*0.9})`; c.beginPath(); c.arc(s.x+Math.cos(s.a)*d,s.y+Math.sin(s.a)*d,s.sz*(1-k*0.5),0,6.283); c.fill();});
    const rk=P(t,12.0,12.7);
    if(rk<1){c.strokeStyle=`rgba(62,230,245,${(1-rk)*0.8})`;c.lineWidth=6*(1-rk)+1;c.beginPath();c.ellipse(540,758,lerp(60,900,eOut(rk)),lerp(30,520,eOut(rk)),0,0,6.283);c.stroke();}
  }
  c.globalCompositeOperation='source-over';
}

// ===== الإطار =====
window.render=function(t){
  drawBG(t); drawFX(t);
  $('#glowA').style.transform=`translate(${Math.sin(t*0.5)*60}px,${Math.cos(t*0.4)*80}px) scale(${1+0.1*Math.sin(t*0.8)})`;

  // --- الكاميرا ---
  let ry=lerp(10,-6,eIO(P(t,0,3.9))), rx=lerp(8,3,eIO(P(t,0,3.9))), cz=lerp(-200,80,eOut(P(t,0,3.9)));
  if(t>=3.9){ry=lerp(-6,5,eIO(P(t,3.9,5.0)));rx=3;cz=lerp(80,0,eIO(P(t,3.9,4.8)));
    ry=lerp(ry,-4,eIO(P(t,5.2,7.8)));}
  if(t>=7.9){ry=lerp(-4,-18,eIO(P(t,7.9,8.9)));rx=lerp(3,6,P(t,7.9,8.9));
    ry=lerp(ry,-7,eIO(P(t,8.9,11.0)));cz=lerp(0,60,P(t,8.9,11.0));}
  $('#world').style.transformOrigin='540px 960px';
  $('#world').style.transform=`translateZ(${cz}px) rotateX(${rx}deg) rotateY(${ry}deg)`;

  // --- البطاقات ---
  CARDS.forEach((c,i)=>{
    const ki=P(t,c.t0,c.t0+0.7), kf=eIO(P(t,4.0+i*0.05,4.6+i*0.05));
    if(t<c.t0||kf>=1){c.el.style.display='none';return}
    c.el.style.display='block';
    const e=eExpo(ki);
    let [x,y,z,ryy,rxx]=c.p;
    y+=Math.sin(t*1.4+i*1.7)*12; ryy+=Math.sin(t*0.9+i)*3;
    z=lerp(-1500,z,e); ryy+=lerp(i%2?-40:40,0,e);
    const [tx,ty]=sw(c.to[0],c.to[1]);
    x=lerp(x,tx,kf); y=lerp(y,ty,kf); z=lerp(z,0,kf); ryy=lerp(ryy,0,kf); rxx=lerp(rxx,0,kf);
    const s=lerp(lerp(.7,1,e),c.ts,kf);
    put(c.el,x,y,c.w,c.h,z,ryy,rxx,s);
    c.el.style.opacity=clamp(ki*2.5)*(1-P(kf,0.65,1));
  });

  // --- الروابط ---
  const lk=P(t,2.85,3.45), lo=1-P(t,3.95,4.15);
  svg.style.display=(t>2.85&&t<4.15)?'block':'none';
  svg.style.transform='translate3d(0,0,-30px)';
  CARDS.forEach((c,i)=>{
    const k=eOut(P(lk,i*0.08,0.6+i*0.08));
    const cx=c.p[0], cy=c.p[1]+Math.sin(t*1.4+i*1.7)*12;
    const x2=lerp(cx,HUB[0],k), y2=lerp(cy,HUB[1],k);
    for(const id of ['#lg'+i,'#ln'+i]){const l=$(id);l.setAttribute('x1',cx);l.setAttribute('y1',cy);l.setAttribute('x2',x2);l.setAttribute('y2',y2);l.style.opacity=lo;}
    const pk=((t-3.2-i*0.07)/0.45)%1, pd=$('#pd'+i);
    if(t>3.2&&k>=1){pd.setAttribute('cx',lerp(cx,HUB[0],pk));pd.setAttribute('cy',lerp(cy,HUB[1],pk));pd.style.opacity=lo;}else pd.style.opacity=0;
  });
  const hk=P(t,3.3,3.95);
  $('#hub').setAttribute('r',lerp(6,26,hk)+Math.sin(t*20)*2*hk);
  $('#hubG').setAttribute('r',lerp(20,110,hk)+lerp(0,500,eOut(P(t,3.95,4.15))));
  $('#hubG').style.opacity=lerp(.6,0,P(t,3.95,4.15));

  // --- المتجر/الجوال ---
  const pw=$('#phoneWrap');
  const sIn=P(t,4.05,4.5);
  if(t<4.05||t>11.4){pw.style.display='none'}else{
    pw.style.display='block';
    let s=lerp(1.25,SC,eOut(sIn));
    s=lerp(s,1.0,eIO(P(t,7.95,8.9)));
    put(pw,540,960,640,1290,0,0,0,s);
    pw.style.opacity=eOut(sIn);
    // الأقسام تظهر بالتتابع
    ['#sHdr','#sSearch','#sHero','#sCats','#sH2','#sGrid','#sRev','#sNav'].forEach((id,i)=>{
      const k=P(t,4.2+i*0.07,4.55+i*0.07), el=$(id);
      el.style.opacity=eOut(k); el.style.transform=`translateY(${lerp(40,0,back(k,1.4))}px) scale(${lerp(.94,1,eOut(k))})`;
    });
    const ph=eOut(P(t,8.1,8.8));
    $('#phone').style.opacity=ph; $('#refl').style.opacity=ph; $('#isl').style.opacity=ph;
    $('#phone').style.transform=`translate3d(0,0,-2px) scale(${lerp(1.06,1,ph)})`;
    $('#store').style.borderRadius=lerp(64,64,ph)+'px';
    // تمرير الصفحة
    const scr=lerp(0,-330,eIO(P(t,6.3,7.2)))+lerp(0,330,eIO(P(t,8.2,9.1)));
    $('#sIn').style.transform=`translateY(${scr}px)`;
    // لمعة
    $('#sweep').style.left=lerp(-400,800,P(t,4.75,5.35))+'px';
    // ضغطة "أضف" وطيران للسلة
    const add=$('#addBtn');
    const pr=Math.max(0,Math.sin(Math.PI*P(t,5.35,5.55)));
    add.style.transform=`scale(${1-0.2*pr})`;
    const rp=P(t,5.45,5.95), tap=$('#tapR');
    const A=offIn(add,$('#store')), C=offIn($('.cart'),$('#store'));
    const ax=A[0]+26, ay=A[1]+26+scr, cx=C[0]+30, cy=C[1]+30+scr;
    if(rp>0&&rp<1){tap.style.opacity=1-rp;tap.style.left=(ax-60)+'px';tap.style.top=(ay-60)+'px';tap.style.transform=`scale(${lerp(.3,1.6,eOut(rp))})`}else tap.style.opacity=0;
    const fk=P(t,5.5,6.0), fd=$('#flyDot');
    if(fk>0&&fk<1){const e=eIO(fk);fd.style.opacity=1;fd.style.left=(lerp(ax,cx,e)-15)+'px';fd.style.top=(lerp(ay,cy,e)-15-Math.sin(Math.PI*e)*260)+'px';fd.style.transform=`scale(${lerp(1.2,.5,e)})`}else fd.style.opacity=0;
    let n=2; if(t>=6.0)n=3; if(t>=9.05)n=4; if(t>=10.55)n=5;
    const bd=$('#badge'); bd.textContent=n;
    const bb=Math.max(P(t,6.0,6.35)<1&&t>=6.0?Math.sin(Math.PI*P(t,6.0,6.35)):0, t>=9.05&&t<9.4?Math.sin(Math.PI*P(t,9.05,9.4)):0, t>=10.55&&t<10.9?Math.sin(Math.PI*P(t,10.55,10.9)):0);
    bd.style.transform=`scale(${1+0.6*bb})`;
  }

  // --- الإشعارات حول الجوال ---
  NTS.forEach((n,i)=>{
    const k=P(t,n.t0,n.t0+0.55);
    if(t<n.t0||t>11.4){n.el.style.display='none';return}
    n.el.style.display='flex';
    const [x,y,z,r]=n.p;
    put(n.el,x,y+Math.sin(t*1.6+i)*10,470,128,lerp(-300,z,eExpo(k)),r*(1-0.5*eOut(k)),0,lerp(.55,1,back(k,1.8)));
    n.el.style.opacity=clamp(k*3);
  });

  // --- تلاشي المشهد نحو الجسيمات ---
  const so=P(t,11.0,11.4);
  $('#scene').style.opacity=1-eIn(so);
  $('#scene').style.filter=so>0?`blur(${so*14}px) brightness(${1+so})`:'none';

  // --- الخاتمة ---
  const end=$('#end');
  end.style.display=t<11.85?'none':'block';
  if(t>=11.85){
    end.style.transformOrigin='540px 960px';
    end.style.transform=`scale(${lerp(1,1.035,P(t,12.0,18))})`;
    const lk=P(t,11.9,12.15);
    $('#logo').style.opacity=eOut(lk);
    $('#logo').style.transform=`scale(${lerp(1.06,1,eOut(P(t,12.0,12.7)))})`;
    $('#logoGlow').style.opacity=(0.35+0.2*Math.sin(t*2.2))*eOut(lk)+lerp(.6,0,P(t,12.0,12.8));
    [...document.querySelectorAll('#l1 span')].forEach((w,i)=>{
      const k=P(t,12.6+i*0.14,13.1+i*0.14);
      w.style.opacity=eOut(k); w.style.filter=`blur(${lerp(18,0,eOut(k))}px)`;
      w.style.transform=`translateY(${lerp(50,0,eExpo(k))}px) scale(${lerp(1.15,1,eOut(k))})`;
    });
    const k2=P(t,13.45,13.95);
    $('#l2').style.opacity=eOut(k2); $('#l2').style.transform=`translateY(${lerp(30,0,eOut(k2))}px)`;
    $('#l2').style.filter=`blur(${lerp(10,0,eOut(k2))}px)`;
    const k3=P(t,14.05,14.6), url=$('#url');
    url.style.opacity=eOut(clamp(k3*2));
    url.style.transform=`translateX(-50%) scale(${lerp(.6,1,back(k3,2))})`;
    const sh=Math.max(P(t,14.6,15.2),0);
    $('#urlSh').style.left=(t<16.4?lerp(-200,700,sh):lerp(-200,700,P(t,16.4,17.0)))+'px';
  }
  const fl=P(t,12.0,12.45);
  $('#flash').style.opacity=t>=12.0?0.85*(1-eOut(fl)):0;
};
function offIn(el,root){let x=0,y=0;while(el&&el!==root){x+=el.offsetLeft;y+=el.offsetTop;el=el.offsetParent}return[x,y]}
window.render(0);
