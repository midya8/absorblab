import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {analyzeResponse,validate,parseJSON} from '../docs/response-engine.js';
const native=spawnSync(process.env.PYTHON||'python',['-c',`
import json
from tools.response_cases import differential_cases
from absorblab.response import analyze_response
print(json.dumps([analyze_response(x) for x in differential_cases()]))
`],{cwd:new URL('..',import.meta.url),encoding:'utf8',maxBuffer:64*1024*1024});
assert.equal(native.status,0,native.stderr);
const reports=JSON.parse(native.stdout);
test('146 complete BigInt reports match exact native response/endpoint/traffic certificates',()=>{
 let samples=0,curves=0,edges=0,derivatives=0;
 assert.equal(reports.length,146);
 for(const expected of reports){
  const request=structuredClone(expected.input),before=structuredClone(request),actual=analyzeResponse(request);
  assert.deepEqual(actual,expected);assert.deepEqual(request,before);
  samples+=actual.samples.length;curves+=actual.response.curves.length;
  for(const s of actual.samples)for(const r of s.roots)if(r.conditional)edges+=r.conditional.edges.flat().length;
  for(const s of actual.samples)if(s.derivatives)derivatives+=s.derivatives.length*3;
 }
 console.log(JSON.stringify({reports:reports.length,samples,curves,conditionalEdgeCells:edges,derivativePairs:derivatives}));
});
test('strict schema and duplicate/noninteger JSON controls are rejected',()=>{
 const base=reports[0].input;
 for(const [key,value]of [['at',0],['at','1e-2'],['at','1/0'],['at','0.1'],['at','2'],['at','-2'],['at','1/1000001'],['donor','missing'],['row','s1'],['receiver','s0']])assert.throws(()=>validate({...structuredClone(base),[key]:value}));
 assert.throws(()=>validate({...structuredClone(base),extra:true}));
 for(const source of ['{"a":1,"a":2}','{"a":1.0}','{"a":NaN}'])assert.throws(()=>parseJSON(source));
});
test('default discontinuity and retry curvature remain visible',()=>{
 const out=analyzeResponse(reports[0].input);assert.equal(out.endpoints[0].discontinuous[0],true);assert.equal(out.endpoints[0].interior_limits[0].success,'1');assert.equal(out.samples[0].roots[0].success,'0');assert.equal(out.samples[0].roots[0].conditional,null);
 const retry=analyzeResponse(reports[1].input).samples.find(x=>x.transfer==='0');assert.deepEqual(retry.derivatives[0].success,{first:'1',second:'-4'});
});
