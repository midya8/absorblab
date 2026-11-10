import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { analyzeLumping, parseJSON } from "../docs/lumping-engine.js";
const cases = JSON.parse(
  execFileSync(
    "python",
    [
      "-c",
      "import json;from tools.lumping_cases import controls,seeded,exhaustive;print(json.dumps(list(exhaustive())+seeded()+[c['input']for c in controls()]))",
    ],
    { maxBuffer: 20e6 },
  ),
);
test("527 exact native/independent/JavaScript full lumping reports", () => {
  let partitions = 0,
    rounds = 0,
    identities = 0;
  for (let i = 0; i < cases.length; i += 20) {
    const batch = cases.slice(i, i + 20),
      expected = JSON.parse(
        execFileSync(
          "python",
          [
            "-c",
            "import json,sys;from absorblab.lumping import analyze_lumping;from absorblab.lumping_verify import verify_lumping;rs=[analyze_lumping(x)for x in json.load(sys.stdin)];assert all(verify_lumping(r)for r in rs);print(json.dumps(rs))",
          ],
          { input: JSON.stringify(batch), maxBuffer: 100e6 },
        ),
      );
    for (let j = 0; j < batch.length; j++) {
      const r = analyzeLumping(batch[j]);
      assert.deepEqual(r, expected[j], "case " + (i + j));
      partitions += r.partition_atlas.length;
      rounds += r.rounds.length;
      identities += r.intertwining.length;
    }
  }
  console.log(
    JSON.stringify({
      reports: cases.length,
      partitions,
      refinement_states: rounds,
      intertwining_obligations: identities,
    }),
  );
});
test("strict contract, parser and no mutation", () => {
  const d = cases[0],
    before = structuredClone(d);
  analyzeLumping(d);
  assert.deepEqual(d, before);
  for (const d of [
    null,
    [],
    {},
    { chain: {}, observations: [] },
    { ...before, extra: 1 },
    { ...before, observations: [true] },
  ])
    assert.throws(() => analyzeLumping(d));
  for (const s of [
    '{"x":0,"x":0}',
    '{"chain":{},"observations":[],"x":1.0}',
    "NaN",
    " ".repeat(65537),
  ])
    assert.throws(() => parseJSON(s));
});
