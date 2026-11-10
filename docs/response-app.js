import {analyzeResponse,parseJSON} from './response-engine.js';
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
let controls=[],report=null;
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
function tile(title,value,detail='',problem=false){const el=node('div',undefined,'tile'+(problem?' problem':''));el.append(node('h3',title),node('p',value,'value'));if(detail)el.append(node('p',detail,'meta'));return el;}
function options(select,items,selected=0){select.replaceChildren();items.forEach((label,i)=>{const el=node('option',label);el.value=String(i);select.append(el);});select.value=String(selected);}
const decimal=s=>{const [a,b='1']=s.split('/');return Number(a)/Number(b);};
const formula=a=>'('+a[0]+') + ('+a[1]+') δ';
function plot(root,selected){
 const svg=$('plot'),w=Math.max(272,svg.clientWidth),h=280,left=40,right=w-30,top=30,bottom=h-52;
 svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.replaceChildren();
 const add=(tag,attrs,text)=>{const el=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,String(v));if(text!==undefined)el.textContent=text;svg.append(el);return el;};
 const lo=decimal(report.domain.lower),hi=decimal(report.domain.upper),x=t=>left+(decimal(t)-lo)/(hi-lo)*(right-left),y=p=>bottom-decimal(p)*(bottom-top);
 for(const p of ['0','1/2','1']){add('line',{x1:left,y1:y(p),x2:right,y2:y(p),class:'axis'});add('text',{x:left-8,y:y(p)+4,'text-anchor':'end'},p);}
 const interior=report.samples.filter(s=>s.interior),points=interior.map(s=>[x(s.transfer),y(s.roots[root].success)]);
 const limits=report.endpoints.map((e,i)=>[i?right:left,y(e.interior_limits[root].success)]);
 add('polyline',{points:[limits[0],...points,limits[1]].map(p=>p.join(',')).join(' '),class:'trace'});
 for(const e of report.endpoints){const actual=report.samples.find(s=>s.transfer===e.transfer);if(e.discontinuous[root])add('line',{x1:x(e.transfer),x2:x(e.transfer),y1:y(actual.roots[root].success),y2:y(e.interior_limits[root].success),class:'gap'});add('circle',{cx:x(e.transfer),cy:y(e.interior_limits[root].success),r:6,class:'limit'});}
 for(const s of report.samples)add('circle',{cx:x(s.transfer),cy:y(s.roots[root].success),r:3.5,class:'actual'});
 add('circle',{cx:x(selected.transfer),cy:y(selected.roots[root].success),r:8,class:'selected'});
 add('text',{x:left,y:h-25,'text-anchor':'start'},report.domain.lower);add('text',{x:right,y:h-25,'text-anchor':'end'},report.domain.upper);add('text',{x:(left+right)/2,y:h-7,'text-anchor':'middle'},'probability transfer t');
}
function render(){
 if(!report)return;
 const r=Number($('root').value),s=report.samples[Number($('sample').value)],v=s.roots[r],conditional=v.conditional;
 $('domain').replaceChildren(tile('Transfer interval',report.domain.lower+' to '+report.domain.upper,'t is removed from '+report.input.donor+' and added to '+report.input.receiver+' in row '+report.input.row+'.'),tile('Interior anchor',report.domain.anchor,'δ = t - '+report.domain.anchor+'. Both varied edges are positive in the open interval.'));
 $('summary').replaceChildren(tile('Success first',v.success),tile('Failure first',v.failure),tile('Never terminal',v.never));
 $('point-note').textContent=s.interior?'Interior chain: direct exact solve agrees with the rational response.':'Endpoint chain: support is recomputed and solved directly. The interior curve is not substituted for this answer.';
 $('endpoint-cards').replaceChildren(...report.endpoints.map((e,i)=>{const actual=report.samples.find(p=>p.transfer===e.transfer).roots[r];return tile((i?'Upper':'Lower')+' endpoint t = '+e.transfer,'Actual '+actual.success,'Interior success limit '+e.interior_limits[r].success+'. '+(e.discontinuous[r]?'Boundary mismatch: at least one terminal probability changes discontinuously.':'No terminal-probability mismatch for this root.'),e.discontinuous[r]);}));
 $('curves').replaceChildren(...['success','failure','never'].map(key=>{const el=node('div',undefined,'tile');el.append(node('h3',key[0].toUpperCase()+key.slice(1)),node('p','Numerator','meta'),node('p',formula(report.response.curves[r][key]),'value'),node('p','Denominator','meta'),node('p',formula(report.response.denominator),'value'),node('p','Probability = numerator / denominator, on the open interval.','meta'));return el;}));
 const deriv=s.derivatives?.[r];$('derivatives').replaceChildren(...(deriv?['success','failure','never'].map(key=>tile(key+' derivative',deriv[key].first,'Second derivative: '+deriv[key].second+'. Exact derivative with respect to t.')):[tile('Boundary derivative','Not reported','Interior derivatives are not automatically endpoint derivatives.') ]));
 $('traffic-note').textContent=conditional?'Condition on eventual first-hit success from '+report.names[r]+'. Visits include time zero at a nonterminal root and exclude terminal visits. Traversals stop on first success.':'Success has probability zero from '+report.names[r]+'. Conditional visits, edges and timing are undefined, not invented zeros.';
 $('traffic-summary').replaceChildren(tile('Conditional mean steps',conditional?.mean_time??'Undefined'),tile('Expected edge traversals',conditional?.total_edges??'Undefined'),tile('Success arrivals',conditional?.success_arrivals??'Undefined','One for a successful nonterminal start; zero when already at success.'));
 $('visits').replaceChildren(...report.names.map((name,j)=>tile(name,conditional?conditional.visits[j]:'Undefined','Conditional expected visits. Restricted unconditioned visits: '+v.restricted_visits[j]+'.')));
 $('edges').replaceChildren(...report.names.map((name,j)=>{const el=node('div',undefined,'tile');el.append(node('h3','From '+name));report.names.forEach((to,k)=>{const row=node('div',undefined,'edge-row');row.append(node('span','to '+to),node('strong',conditional?conditional.edges[j][k]:'Undefined'));el.append(row);});return el;}));
 const named=indices=>indices.length?indices.map(i=>report.names[i]).join(', '):'none';
 $('support').textContent='Anchor terminal-reachable nonterminals: '+named(report.anchor.transient_indices)+'. Selected concrete chain: '+named(s.transient_indices)+'.';
 $('anchor-json').textContent=JSON.stringify(report.anchor,null,2);$('residual-json').textContent=JSON.stringify(report.response.harmonic_residuals,null,2);$('report-json').textContent=JSON.stringify(report,null,2);$('limits').replaceChildren(...report.limits.map(text=>node('li',text)));
 plot(r,s);
}
function solve(){
 try{
  const source=$('input').value;if(new TextEncoder().encode(source).length>65536)throw Error('request exceeds 65536 bytes');
  const next=analyzeResponse(parseJSON(source));report=next;globalThis.RESPONSE_REPORT=report;
  options($('root'),report.names);options($('sample'),report.samples.map(s=>s.transfer+(s.interior?' / interior':' / endpoint')),report.samples.findIndex(s=>s.transfer===report.input.at));
  $('results').hidden=false;$('download').disabled=false;$('status').textContent='Exact response ready. '+report.samples.length+' concrete chains, with separately solved endpoints.';$('status').className='';render();
 }catch(error){report=null;globalThis.RESPONSE_REPORT=null;$('results').hidden=true;$('download').disabled=true;$('status').textContent='Not solved: '+error.message;$('status').className='problem-text';}
}
function loadControl(){const c=controls[Number($('control').value)];$('why').textContent=c.name;$('input').value=JSON.stringify(c.request,null,2);solve();}
$('control').addEventListener('change',loadControl);$('run').addEventListener('click',solve);$('root').addEventListener('change',render);$('sample').addEventListener('change',render);
$('input').addEventListener('input',()=>{report=null;globalThis.RESPONSE_REPORT=null;$('results').hidden=true;$('download').disabled=true;$('status').textContent='Input changed. Run the new request to replace the previous result.';});
addEventListener('resize',()=>{if(report)plot(Number($('root').value),report.samples[Number($('sample').value)]);});
$('download').addEventListener('click',()=>{if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'})),a=node('a');a.href=url;a.download='absorblab-response-certificate.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
try{const response=await fetch('response-controls.json');if(!response.ok)throw Error('controls HTTP '+response.status);controls=await response.json();if(!Array.isArray(controls)||controls.length!==12)throw Error('expected twelve original controls');options($('control'),controls.map(x=>x.name));loadControl();}catch(error){$('status').textContent='Controls unavailable: '+error.message;$('status').className='problem-text';}
