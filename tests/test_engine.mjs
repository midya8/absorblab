import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { analyze, parseJSON, validate, Q } from "../docs/engine.js";
const code = `import json,itertools,random
from fractions import Fraction as F
from absorblab import analyze
rs=[c['input']for c in json.load(open('docs/controls.json'))]
opts=[[(0,F(1))],[(1,F(1))],[(0,F(1,2)),(1,F(1,2))]]
for rows in itertools.product(opts,repeat=2):
 for status in itertools.product(range(3),repeat=2):rs.append({'states':[{'name':'s'+str(i),'transitions':[{'to':'s'+str(j),'prob':str(p)}for j,p in row]}for i,row in enumerate(rows)],'success':['s'+str(i)for i,s in enumerate(status)if s==1],'failure':['s'+str(i)for i,s in enumerate(status)if s==2],'horizon':3})
rng=random.Random(79221)
for k in range(120):
 n=2+k%5;rows=[]
 for i in range(n):
  ts=rng.sample(range(n),rng.randint(1,n));ws=[rng.randint(1,5)for _ in ts];rows.append({'name':'s'+str(i),'transitions':[{'to':'s'+str(j),'prob':str(F(w,sum(ws)))}for j,w in zip(ts,ws)]})
 status=[rng.randrange(3)for _ in range(n)];rs.append({'states':rows,'success':['s'+str(i)for i,s in enumerate(status)if s==1],'failure':['s'+str(i)for i,s in enumerate(status)if s==2],'horizon':k%13})
print(json.dumps([{'input':r,'report':analyze(r)}for r in rs]))`;
test("independent BigInt determinant/power reports match complete native certificates", () => {
  const records = JSON.parse(
    execFileSync(process.env.PYTHON || "python", ["-c", code], {
      maxBuffer: 128 * 1024 * 1024,
    }),
  );
  let states = 0,
    forecasts = 0,
    ops = 0;
  for (const r of records) {
    const before = JSON.stringify(r.input);
    assert.deepEqual(analyze(r.input), r.report);
    assert.equal(JSON.stringify(r.input), before);
    states += r.report.states.length;
    forecasts += r.report.forecasts.reduce((a, x) => a + x.rows.length, 0);
    ops += r.report.linear_system.elimination.length;
  }
  console.log(
    JSON.stringify({
      reports: records.length,
      states,
      forecast_rows: forecasts,
      elimination_stages: ops,
    }),
  );
});
test("strict parser, schema, prototype identifiers and large exact fractions", () => {
  for (const raw of [
    "NaN",
    "Infinity",
    '{"a":1,"a":2}',
    '{"a":NaN}',
    "{}\u00a0",
    " ".repeat(65537),
    "[1,]",
    '{"a":1,}',
  ])
    assert.throws(() => parseJSON(raw));
  const c = JSON.parse(fs.readFileSync("docs/controls.json"))[0].input;
  for (const r of [
    {},
    null,
    [],
    { ...c, horizon: true },
    { ...c, horizon: 13 },
    { ...c, success: ["missing"] },
    { ...c, failure: ["goal"] },
  ])
    assert.throws(() => validate(r));
  const r = {
    states: [
      { name: "__proto__", transitions: [{ to: "constructor", prob: "1" }] },
      { name: "constructor", transitions: [{ to: "__proto__", prob: "1" }] },
    ],
    success: ["constructor"],
    failure: [],
    horizon: 2,
  };
  assert.equal(analyze(r).states[0].success_probability, "1");
  assert.equal(String(new Q(2n, 4n)), "1/2");
  assert.equal(
    String(new Q(999999999999999999n).mul(new Q(3n))),
    "2999999999999999997",
  );
});

test("JSON numeric spelling and final newline cannot widen native schema", () => {
  for (const raw of ["1.0", "1e0", "1E+0"]) assert.throws(() => parseJSON(raw));
  const c = JSON.parse(fs.readFileSync("docs/controls.json"))[0].input;
  for (const suffix of ["\n", "\r", " "]) {
    let x = structuredClone(c);
    x.states[0].name += suffix;
    assert.throws(() => validate(x));
    x = structuredClone(c);
    x.states[0].transitions[0].prob += suffix;
    assert.throws(() => validate(x));
  }
});
