/* Independent exact BigInt/set partition engine. No native certificate loaded. */
import { Q, validate as validateChain, analyze as firstHit } from "./engine.js";
export { parseJSON } from "./engine.js";
const q = (x) =>
    x instanceof Q
      ? x
      : typeof x === "string"
        ? new Q(...x.split("/").map(BigInt))
        : new Q(x),
  sum = (xs) => xs.reduce((a, b) => a.add(b), q(0)),
  enc = (m) => m.map((r) => r.map(String)),
  same = (a, b) => JSON.stringify(a) === JSON.stringify(b),
  canonical = (bs) =>
    bs.map((b) => [...b].sort((a, b) => a - b)).sort((a, b) => a[0] - b[0]),
  finer = (a, b) =>
    a.every((x) => b.some((y) => x.every((i) => y.includes(i))));
export function validate(raw) {
  if (
    raw === null ||
    typeof raw !== "object" ||
    Array.isArray(raw) ||
    Object.keys(raw).sort().join("|") !== "chain|observations"
  )
    throw Error("lumping request needs exactly chain and observations");
  const chain = validateChain(raw.chain),
    observations = raw.observations;
  if (
    !Array.isArray(observations) ||
    observations.length !== chain.states.length ||
    observations.some(
      (x) => typeof x !== "string" || !/^[A-Za-z_][A-Za-z_0-9]{0,23}$/.test(x),
    )
  )
    throw Error("one short ASCII observation tag per state is required");
  return { chain, observations: [...observations] };
}
function allParts(n) {
  let parts = [[[0]]];
  for (let i = 1; i < n; i++) {
    const next = [];
    for (const part of parts) {
      for (let k = 0; k <= part.length; k++) {
        const p = part.map((b) => b.slice());
        if (k === p.length) p.push([i]);
        else p[k].push(i);
        next.push(p);
      }
    }
    parts = next;
  }
  return parts.sort((a, b) => {
    for (let i = 0; i < n; i++) {
      const x = a.findIndex((t) => t.includes(i)),
        y = b.findIndex((t) => t.includes(i));
      if (x !== y) return x - y;
    }
    return 0;
  });
}
export function analyzeLumping(raw) {
  const input = validate(raw),
    chain = input.chain,
    names = chain.states.map((s) => s.name),
    n = names.length,
    ids = Array.from({ length: n }, (_, i) => i),
    p = chain.states.map((s) =>
      names.map((name) =>
        q(s.transitions.find((t) => t.to === name)?.prob ?? 0),
      ),
    ),
    status = names.map((name) =>
      chain.success.includes(name)
        ? "success"
        : chain.failure.includes(name)
          ? "failure"
          : "nonterminal",
    ),
    colors = input.observations.map((o, i) => [o, status[i]]),
    initial = canonical(
      [...new Set(colors.map(JSON.stringify))].map((c) =>
        ids.filter((i) => JSON.stringify(colors[i]) === c),
      ),
    ),
    parts = allParts(n),
    masses = (bs) => p.map((row) => bs.map((b) => sum(b.map((j) => row[j]))));
  function details(bs) {
    const m = masses(bs),
      pairs = [];
    for (const b of bs)
      for (let a = 0; a < b.length; a++)
        for (let c = a + 1; c < b.length; c++) {
          const i = b[a],
            j = b[c];
          pairs.push({
            left: i,
            right: j,
            same_observation: same(colors[i], colors[j]),
            unequal_blocks: bs.flatMap((members, k) =>
              String(m[i][k]) === String(m[j][k])
                ? []
                : [
                    {
                      block: k,
                      members: [...members],
                      left_mass: String(m[i][k]),
                      right_mass: String(m[j][k]),
                    },
                  ],
            ),
          });
        }
    return { m, pairs };
  }
  const rounds = [];
  let blocks = initial;
  for (;;) {
    const { m, pairs } = details(blocks),
      groups = [];
    for (const b of blocks) {
      const map = new Map();
      for (const i of b) {
        const key = m[i].map(String).join("|");
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(i);
      }
      groups.push(...map.values());
    }
    const after = canonical(groups),
      fixed = same(after, blocks);
    rounds.push({
      round: rounds.length,
      blocks,
      masses: enc(m),
      pairs,
      next_blocks: after,
      fixed,
    });
    if (fixed) break;
    blocks = after;
  }
  const final = blocks,
    stateBlocks = ids.map((i) => final.findIndex((b) => b.includes(i))),
    m = masses(final),
    quot = m.filter((row, i) => final.some((b) => b[0] === i)),
    qn = final.length,
    quotient = {
      states: quot.map((row, k) => ({
        name: "q" + k,
        transitions: row.flatMap((v, j) =>
          v.nonzero ? [{ to: "q" + j, prob: String(v) }] : [],
        ),
      })),
      success: final.flatMap((b, k) =>
        status[b[0]] === "success" ? ["q" + k] : [],
      ),
      failure: final.flatMap((b, k) =>
        status[b[0]] === "failure" ? ["q" + k] : [],
      ),
      horizon: chain.horizon,
    },
    atlas = parts.map((bs) => {
      const { m, pairs } = details(bs),
        stable = pairs.every((x) => !x.unequal_blocks.length),
        respect = pairs.every((x) => x.same_observation),
        oc = pairs.find((x) => !x.same_observation),
        mc = pairs.find((x) => x.unequal_blocks.length);
      return {
        blocks: bs,
        masses: enc(m),
        respects_observations: respect,
        stable,
        allowed: stable && respect,
        first_observation_conflict: oc
          ? { left: oc.left, right: oc.right }
          : null,
        first_mass_conflict: mc
          ? { left: mc.left, right: mc.right, ...mc.unequal_blocks[0] }
          : null,
        refines_final: finer(bs, final),
      };
    }),
    identity = ids.flatMap((i) =>
      final.map((_, j) => ({
        state: i,
        source_block: stateBlocks[i],
        destination_block: j,
        original_mass: String(m[i][j]),
        quotient_prob: String(quot[stateBlocks[i]][j]),
        equal: String(m[i][j]) === String(quot[stateBlocks[i]][j]),
      })),
    ),
    forecasts = [];
  for (const root of ids) {
    let original = ids.map((i) => q(i === root ? 1 : 0)),
      reduced = final.map((_, k) => q(k === stateBlocks[root] ? 1 : 0));
    const rows = [];
    for (let step = 0; step <= chain.horizon; step++) {
      const agg = final.map((b) => sum(b.map((i) => original[i])));
      rows.push({
        step,
        original_states: original.map(String),
        original_blocks: agg.map(String),
        quotient_blocks: reduced.map(String),
        equal: same(agg.map(String), reduced.map(String)),
      });
      original = ids.map((j) => sum(ids.map((i) => original[i].mul(p[i][j]))));
      reduced = final.map((_, j) =>
        sum(final.map((_, i) => reduced[i].mul(quot[i][j]))),
      );
    }
    forecasts.push({ start: root, quotient_start: stateBlocks[root], rows });
  }
  const big = firstHit(chain),
    small = firstHit(quotient),
    strip = (s) =>
      Object.fromEntries(Object.entries(s).filter(([k]) => k !== "name")),
    hit = ids.map((i) => {
      const original = strip(big.states[i]),
        quotient = strip(small.states[stateBlocks[i]]);
      return {
        state: i,
        block: stateBlocks[i],
        original,
        quotient,
        equal: same(original, quotient),
      };
    }),
    witnesses = [];
  for (let left = 0; left < n; left++)
    for (let right = left + 1; right < n; right++) {
      let w;
      if (!same(colors[left], colors[right]))
        w = {
          kind: "observation",
          left,
          right,
          left_color: colors[left],
          right_color: colors[right],
        };
      else if (stateBlocks[left] === stateBlocks[right])
        w = { kind: "equivalent", left, right, block: stateBlocks[left] };
      else {
        const r = rounds.find(
            (r) =>
              r.blocks.some((b) => b.includes(left) && b.includes(right)) &&
              !r.next_blocks.some((b) => b.includes(left) && b.includes(right)),
          ),
          k = r.masses[left].findIndex((v, j) => v !== r.masses[right][j]);
        w = {
          kind: "split",
          left,
          right,
          round: r.round,
          destination_block: k,
          destination_members: r.blocks[k],
          left_mass: r.masses[left][k],
          right_mass: r.masses[right][k],
        };
      }
      witnesses.push(w);
    }
  return {
    schema: "absorblab-lumping-v1",
    input,
    colors,
    original_matrix: enc(p),
    initial_blocks: initial,
    rounds,
    final_blocks: final,
    state_blocks: stateBlocks,
    quotient_chain: quotient,
    quotient_observations: final.map((b) => input.observations[b[0]]),
    quotient_matrix: enc(quot),
    intertwining: identity,
    partition_atlas: atlas,
    pair_witnesses: witnesses,
    forecasts,
    first_hit: hit,
    limits: [...LIMITS],
  };
}
const LIMITS = [
  "One to six supplied finite Markov states and exact positive rational transitions; supplied probabilities, not learned or calibrated behavior.",
  "Each state has one supplied observation tag and a derived success/failure/nonterminal status. Both must be preserved by every allowed partition.",
  "Strong lumpability tests the original transition matrix, not the first-hit stopped matrix. Original outgoing terminal transitions remain visible for this stronger equivalence.",
  "Every same-block pair must send exactly equal mass to every block. Matching only immediate goal probabilities or averaging unequal rows does not meet this criterion.",
  "The final partition is the coarsest observation/status-respecting stable refinement, checked against all set partitions. No tolerance, nearest-state heuristic, weak or approximate lumpability.",
  "Exact quotient identities preserve block distributions for any starting state and all step counts. Displayed finite forecasts and first-hit moments are additional bounded checks, not the reason for the all-step guarantee.",
  "Finite exhaustive evidence, not a scalable reduction tool, a complete PCTL model checker, reward-preservation claim, causal intervention or verified real-world agent guarantee.",
];
