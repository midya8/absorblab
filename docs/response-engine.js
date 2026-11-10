/* Exact BigInt row response. No native certificate is loaded by this engine. */
import {Q, validate as validateChain} from './engine.js';
export {parseJSON} from './engine.js';
const q=x=>x instanceof Q?x:typeof x==='string'?new Q(...x.split('/').map(BigInt)):new Q(x);
const add=(a,b)=>q(a).add(b),sub=(a,b)=>q(a).sub(b),mul=(a,b)=>q(a).mul(b),div=(a,b)=>q(a).div(b);
const sum=xs=>xs.reduce(add,q(0)),enc=m=>m.map(r=>r.map(String)),zero=n=>Array.from({length:n},()=>q(0));
const cmp=(a,b)=>{a=q(a);b=q(b);const v=a.a*b.b-b.a*a.b;return v<0n?-1:v>0n?1:0;};
const square=x=>mul(x,x),cube=x=>mul(square(x),x);
export const LIMITS=[
'One to six supplied finite states and exact rational probabilities, not learned or calibrated behavior.',
'One nonterminal row transfers mass between two distinct destinations; other rows are fixed.',
'First success or failure stops the chain. Terminal outgoing transitions do not affect these first-hit quantities.',
'The open transfer interval has fixed positive support. Endpoints are solved separately and may disagree with interior limits.',
"Restricted expected visits concern the displayed concrete chain's terminal-reachable nonterminal set; visits in excluded closed classes are not claimed finite.",
'Success-conditioned traffic is undefined at zero success probability; terminal success roots have zero traffic.',
'Derivatives describe the supplied row family, not causal intervention effects, robustness, learned model uncertainty or optimal policies.',
'Classical finite-chain and rank-one inverse formulas, not new theory, a general parametric model checker or a scaling benchmark.'
];
export function validate(raw){
 if(raw===null||typeof raw!=='object'||Array.isArray(raw)||Object.keys(raw).sort().join('|')!=='at|chain|donor|receiver|row')throw Error('response request needs exactly chain, row, donor, receiver and at');
 const chain=validateChain(raw.chain),names=chain.states.map(s=>s.name);
 for(const k of ['row','donor','receiver'])if(typeof raw[k]!=='string'||!names.includes(raw[k]))throw Error(k+' must be a declared state');
 if([...chain.success,...chain.failure].includes(raw.row))throw Error('the transferred row must be nonterminal');
 if(raw.donor===raw.receiver)throw Error('donor and receiver must be distinct');
 if(typeof raw.at!=='string'||! /^-?(?:0|[1-9][0-9]{0,6})(?:\/[1-9][0-9]{0,6})?$/.test(raw.at)||raw.at.split('/').some(x=>{const v=BigInt(x);return v>1000000n||v< -1000000n;}))throw Error('at must be a bounded exact signed rational string');
 const row=chain.states[names.indexOf(raw.row)].transitions,prob=name=>q(row.find(e=>e.to===name)?.prob||0),lo=mul(-1,prob(raw.receiver)),hi=prob(raw.donor),t=q(raw.at);
 if(cmp(lo,hi)===0)throw Error('the varied destinations need positive combined mass');
 if(cmp(t,lo)<0||cmp(t,hi)>0)throw Error('at is outside the admissible probability-transfer interval');
 return {chain,row:raw.row,donor:raw.donor,receiver:raw.receiver,at:String(t)};
}
function inverse(a){
 const n=a.length,m=a.map((r,i)=>[...r,...Array.from({length:n},(_,j)=>q(i===j?1:0))]);
 for(let c=0;c<n;c++){
  const pivot=m.findIndex((r,i)=>i>=c&&r[c].nonzero);if(pivot<0)throw Error('singular restricted system');
  [m[pivot],m[c]]=[m[c],m[pivot]];const divisor=m[c][c];m[c]=m[c].map(v=>div(v,divisor));
  for(let r=0;r<n;r++)if(r!==c){const factor=m[r][c];m[r]=m[r].map((v,j)=>sub(v,mul(factor,m[c][j])));}
 }
 return m.map(r=>r.slice(n));
}
function solve(raw,good,bad){
 const n=raw.length,terminal=new Set([...good,...bad]);
 const p=raw.map((r,i)=>terminal.has(i)?Array.from({length:n},(_,j)=>q(i===j?1:0)):r.slice());
 const reach=p.map((r,i)=>r.map((v,j)=>i===j||v.nonzero));
 for(let k=0;k<n;k++)for(let i=0;i<n;i++)for(let j=0;j<n;j++)reach[i][j]=reach[i][j]||(reach[i][k]&&reach[k][j]);
 const us=Array.from({length:n},(_,i)=>i).filter(i=>!terminal.has(i)&&[...terminal].some(j=>reach[i][j]));
 const matrix=us.map(i=>us.map(j=>sub(i===j?1:0,p[i][j]))),inv=inverse(matrix),vectors=[];
 for(const boundary of [good,bad]){
  const rhs=us.map(i=>sum([...boundary].map(j=>p[i][j]))),v=Array.from({length:n},(_,i)=>q(boundary.has(i)?1:0));
  us.forEach((i,r)=>v[i]=sum(inv[r].map((x,c)=>mul(x,rhs[c]))));vectors.push(v);
 }
 const visits=Array.from({length:n},()=>zero(n));us.forEach((i,r)=>us.forEach((j,c)=>visits[i][j]=inv[r][c]));
 return {p,us,matrix,inv,h:vectors[0],f:vectors[1],visits};
}
function snapshot(raw,good,bad){
 const {p,us,matrix,inv,h,f,visits}=solve(raw,good,bad),n=p.length;
 const roots=Array.from({length:n},(_,r)=>{
  let conditional=null;
  if(h[r].nonzero){
   const cv=Array.from({length:n},(_,j)=>div(mul(visits[r][j],h[j]),h[r]));
   const edges=Array.from({length:n},(_,j)=>Array.from({length:n},(_,k)=>div(mul(mul(visits[r][j],p[j][k]),h[k]),h[r])));
   const outgoing=edges.map(sum),incoming=Array.from({length:n},(_,k)=>sum(edges.map(row=>row[k])));
   conditional={visits:cv.map(String),edges:enc(edges),outgoing:outgoing.map(String),incoming:incoming.map(String),mean_time:String(sum(cv)),total_edges:String(sum(outgoing)),success_arrivals:String(sum([...good].map(j=>incoming[j])))};
  }
  return {success:String(h[r]),failure:String(f[r]),never:String(sub(sub(1,h[r]),f[r])),restricted_visits:visits[r].map(String),conditional};
 });
 return {stopped_matrix:enc(p),transient_indices:us,matrix:enc(matrix),inverse:enc(inv),roots};
}
export function analyzeResponse(rawRequest){
 const input=validate(rawRequest),chain=input.chain,names=chain.states.map(s=>s.name),n=names.length;
 const [row,donor,receiver]=['row','donor','receiver'].map(k=>names.indexOf(input[k]));
 const [good,bad]=['success','failure'].map(k=>new Set(chain[k].map(v=>names.indexOf(v))));
 const raw=chain.states.map(s=>names.map(name=>q(s.transitions.find(e=>e.to===name)?.prob||0)));
 const lower=mul(-1,raw[row][receiver]),upper=raw[row][donor],anchor=div(add(lower,upper),2);
 const at=t=>raw.map((r,i)=>r.map((p,j)=>i===row?add(p,mul((j===receiver?1:0)-(j===donor?1:0),t)):p));
 const a=solve(at(anchor),good,bad),column=a.visits.map(r=>r[row]),kappa=sub(column[receiver],column[donor]);
 const denominator=[q(1),mul(-1,kappa)],numerators={};
 for(const [key,values] of [['success',a.h],['failure',a.f]]){
  const contrast=sub(values[receiver],values[donor]);numerators[key]=values.map((v,r)=>[v,sub(mul(column[r],contrast),mul(v,kappa))]);
 }
 numerators.never=names.map((_,r)=>denominator.map((v,c)=>sub(sub(v,numerators.success[r][c]),numerators.failure[r][c])));
 const curves=names.map((state,r)=>({state,...Object.fromEntries(Object.entries(numerators).map(([k,v])=>[k,v[r].map(String)]))}));
 const residuals={};
 for(const key of ['success','failure'])residuals[key]=names.map((_,i)=>{
  if(good.has(i)||bad.has(i))return ['0','0','0'];
  const vals=[...numerators[key][i],q(0)];
  for(let j=0;j<n;j++){
   const slope=q(i===row?(j===receiver?1:0)-(j===donor?1:0):0),[b0,b1]=numerators[key][j];
   vals[0]=sub(vals[0],mul(a.p[i][j],b0));vals[1]=sub(vals[1],add(mul(a.p[i][j],b1),mul(slope,b0)));vals[2]=sub(vals[2],mul(slope,b1));
  }
  if(vals.some(v=>v.nonzero))throw Error('nonzero harmonic polynomial residual');return vals.map(String);
 });
 const points=Array.from({length:13},(_,i)=>add(lower,mul(sub(upper,lower),div(i,12))));points.push(q(0),anchor,q(input.at));
 const unique=[...new Set(points.map(String))].map(q).sort(cmp);
 const samples=unique.map(t=>{
  const delta=sub(t,anchor),den=add(1,mul(delta,denominator[1])),interior=cmp(lower,t)<0&&cmp(t,upper)<0,direct=snapshot(at(t),good,bad);let derivatives=null;
  if(interior){
   if(!den.nonzero)throw Error('singular interior denominator');
   derivatives=names.map((_,r)=>Object.fromEntries(['success','failure','never'].map(key=>{
    const [b0,b1]=numerators[key][r],cross=sub(b1,mul(b0,denominator[1])),predicted=div(add(b0,mul(delta,b1)),den);
    if(cmp(predicted,direct.roots[r][key]))throw Error('interior response differs from direct solve');
    return [key,{first:String(div(cross,square(den))),second:String(div(mul(mul(-2,cross),denominator[1]),cube(den)))}];
   })));
  }
  return {transfer:String(t),interior,derivatives,...direct};
 });
 const endpoints=[lower,upper].map(t=>{
  const delta=sub(t,anchor),den=add(1,mul(delta,denominator[1])),actual=samples.find(x=>cmp(x.transfer,t)===0);
  const interior_limits=names.map((_,r)=>Object.fromEntries(['success','failure','never'].map(key=>{
   const [b0,b1]=numerators[key][r],num=add(b0,mul(delta,b1));if(!den.nonzero&&num.nonzero)throw Error('unbounded probability limit');
   return [key,String(den.nonzero?div(num,den):div(b1,denominator[1]))];
  })));
  return {transfer:String(t),interior_limits,discontinuous:interior_limits.map((v,r)=>Object.keys(v).some(key=>v[key]!==actual.roots[r][key]))};
 });
 return {schema:'absorblab-response-v1',input,limits:LIMITS.slice(),names,domain:{lower:String(lower),upper:String(upper),anchor:String(anchor)},
 anchor:{stopped_matrix:enc(a.p),transient_indices:a.us,matrix:enc(a.matrix),inverse:enc(a.inv),row_visit_column:column.map(String),feedback:String(kappa)},
 response:{denominator:denominator.map(String),curves,harmonic_residuals:residuals},samples,endpoints};
}
