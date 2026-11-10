// Independently written exact BigInt engine. No native reports are served.
export class Q {
  constructor(a, b = 1n) {
    a = BigInt(a);
    b = BigInt(b);
    if (b === 0n) throw Error("zero denominator");
    if (b < 0n) {
      a = -a;
      b = -b;
    }
    let x = a < 0n ? -a : a,
      y = b;
    while (y) {
      [x, y] = [y, x % y];
    }
    this.a = a / x;
    this.b = b / x;
  }
  add(v) {
    v = q(v);
    return new Q(this.a * v.b + v.a * this.b, this.b * v.b);
  }
  sub(v) {
    v = q(v);
    return new Q(this.a * v.b - v.a * this.b, this.b * v.b);
  }
  mul(v) {
    v = q(v);
    return new Q(this.a * v.a, this.b * v.b);
  }
  div(v) {
    v = q(v);
    return new Q(this.a * v.b, this.b * v.a);
  }
  get nonzero() {
    return this.a !== 0n;
  }
  toString() {
    return this.b === 1n ? String(this.a) : this.a + "/" + this.b;
  }
}
const q = (v) =>
    v instanceof Q
      ? v
      : typeof v === "string"
        ? new Q(...v.split("/").map(BigInt))
        : new Q(v),
  sum = (xs) => xs.reduce((a, b) => a.add(b), q(0)),
  enc = (a) => a.map((r) => r.map(String)),
  zero = (n) => Array.from({ length: n }, () => q(0));
function keys(x, expected) {
  return (
    x !== null &&
    typeof x === "object" &&
    !Array.isArray(x) &&
    Object.keys(x).sort().join("|") === expected
  );
}
export function validate(data) {
  if (!keys(data, "failure|horizon|states|success"))
    throw Error(
      "request requires exactly states, success, failure and horizon",
    );
  if (
    !Array.isArray(data.states) ||
    data.states.length < 1 ||
    data.states.length > 6
  )
    throw Error("states must have length 1..6");
  const names = [];
  for (const s of data.states) {
    if (
      !keys(s, "name|transitions") ||
      typeof s.name !== "string" ||
      s.name.trim() !== s.name ||
      !/^[A-Za-z_][A-Za-z_0-9]{0,23}$/.test(s.name) ||
      names.includes(s.name)
    )
      throw Error("unique short ASCII state names required");
    names.push(s.name);
  }
  const states = data.states.map((s) => {
    if (
      !Array.isArray(s.transitions) ||
      s.transitions.length < 1 ||
      s.transitions.length > 6
    )
      throw Error("each row requires 1..6 transitions");
    const seen = new Set();
    let total = q(0);
    const transitions = s.transitions.map((t) => {
      if (
        !keys(t, "prob|to") ||
        typeof t.to !== "string" ||
        !names.includes(t.to) ||
        seen.has(t.to)
      )
        throw Error("unique declared targets required");
      if (
        typeof t.prob !== "string" ||
        t.prob.trim() !== t.prob ||
        !/^[1-9][0-9]{0,6}(?:\/[1-9][0-9]{0,6})?$/.test(t.prob) ||
        t.prob.split("/").some((v) => BigInt(v) > 1000000n)
      )
        throw Error("positive bounded rational string required");
      const p = q(t.prob);
      if (p.a > p.b) throw Error("probability exceeds one");
      seen.add(t.to);
      total = total.add(p);
      return { to: t.to, prob: String(p) };
    });
    if (String(total) !== "1") throw Error("row must sum exactly to one");
    return { name: s.name, transitions };
  });
  for (const k of ["success", "failure"])
    if (
      !Array.isArray(data[k]) ||
      data[k].some((n) => typeof n !== "string" || !names.includes(n)) ||
      new Set(data[k]).size !== data[k].length
    )
      throw Error(k + " must be unique declared names");
  if (data.success.some((n) => data.failure.includes(n)))
    throw Error("success and failure must be disjoint");
  if (!Number.isInteger(data.horizon) || data.horizon < 0 || data.horizon > 12)
    throw Error("horizon must be integer 0..12");
  return {
    states,
    success: names.filter((n) => data.success.includes(n)),
    failure: names.filter((n) => data.failure.includes(n)),
    horizon: data.horizon,
  };
}
function* permutations(xs) {
  if (xs.length === 0) {
    yield [];
    return;
  }
  for (let i = 0; i < xs.length; i++)
    for (const rest of permutations(xs.filter((_, j) => j !== i)))
      yield [xs[i], ...rest];
}
function det(a) {
  let out = q(0);
  for (const p of permutations(a.map((_, i) => i))) {
    let inv = 0;
    for (let i = 0; i < p.length; i++)
      for (let j = i + 1; j < p.length; j++) inv += Number(p[i] > p[j]);
    let v = q(inv % 2 ? -1 : 1);
    for (let i = 0; i < p.length; i++) v = v.mul(a[i][p[i]]);
    out = out.add(v);
  }
  return out;
}
function inverse(a) {
  const d = det(a);
  if (!d.nonzero) throw Error("singular restricted system");
  return a.map((_, i) =>
    a.map((_, j) =>
      det(
        a.filter((_, r) => r !== j).map((row) => row.filter((_, c) => c !== i)),
      )
        .mul((i + j) % 2 ? -1 : 1)
        .div(d),
    ),
  );
}
function rowEvidence(a) {
  const n = a.length;
  let m = a.map((r, i) => [...r, ...a.map((_, j) => q(Number(i === j)))]);
  const steps = [];
  for (let k = 0; k < n; k++) {
    const before = enc(m),
      pivot = m.findIndex((r, i) => i >= k && r[k].nonzero);
    if (pivot < 0) throw Error("singular restricted system");
    [m[k], m[pivot]] = [m[pivot], m[k]];
    const divisor = m[k][k];
    m[k] = m[k].map((v) => v.div(divisor));
    const normalized = enc(m),
      factors = m.map((r, i) => (i === k ? q(0) : r[k]));
    m = m.map((r, i) =>
      i === k ? r : r.map((v, j) => v.sub(factors[i].mul(m[k][j]))),
    );
    steps.push({
      column: k,
      swap_row: pivot,
      before,
      divisor: String(divisor),
      normalized,
      factors: factors.map(String),
      after: enc(m),
    });
  }
  return steps;
}
export function analyze(raw) {
  const input = validate(raw),
    states = input.states,
    names = states.map((s) => s.name),
    n = names.length,
    good = new Set(input.success.map((s) => names.indexOf(s))),
    bad = new Set(input.failure.map((s) => names.indexOf(s))),
    terminal = new Set([...good, ...bad]);
  const original = states.map((s) =>
      names.map((v) => q(s.transitions.find((t) => t.to === v)?.prob ?? 0)),
    ),
    p = original.map((r, i) =>
      terminal.has(i) ? names.map((_, j) => q(Number(i === j))) : r.slice(),
    ),
    adj = p.map((r) => r.flatMap((v, j) => (v.nonzero ? [j] : [])));
  // Distances from explicit shortest simple paths establish support layers.
  const paths = [],
    dist = [];
  for (let root = 0; root < n; root++) {
    const queue = [{ i: root, path: [] }],
      seen = new Set([root]);
    let found = null;
    for (const { i, path } of queue) {
      if (terminal.has(i)) {
        found = path;
        break;
      }
      for (const j of adj[i])
        if (!seen.has(j)) {
          seen.add(j);
          queue.push({
            i: j,
            path: [
              ...path,
              { from: names[i], to: names[j], prob: String(p[i][j]) },
            ],
          });
        }
    }
    paths.push({
      start: names[root],
      path: found,
      probability:
        found === null
          ? null
          : String(found.reduce((a, e) => a.mul(e.prob), q(1))),
    });
    dist.push(found === null ? null : found.length);
  }
  const rounds = [];
  for (let k = 0; ; k++) {
    const before = names.filter((_, i) => dist[i] !== null && dist[i] <= k),
      after = names.filter((_, i) => dist[i] !== null && dist[i] <= k + 1),
      added = after.filter((v) => !before.includes(v));
    rounds.push({ index: k, before, after, added });
    if (!added.length) break;
  }
  const reach = p.map((r, i) => r.map((v, j) => v.nonzero || i === j));
  for (let k = 0; k < n; k++)
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) reach[i][j] ||= reach[i][k] && reach[k][j];
  const used = new Set(),
    components = [];
  for (let i = 0; i < n; i++) {
    if (used.has(i)) continue;
    const c = names.flatMap((_, j) => (reach[i][j] && reach[j][i] ? [j] : []));
    c.forEach((j) => used.add(j));
    const closed = c.every((v) => adj[v].every((w) => c.includes(w)));
    components.push({
      states: c.map((j) => names[j]),
      closed,
      terminal_kind: good.has(i) ? "success" : bad.has(i) ? "failure" : "none",
      nonterminal_trap: closed && !c.some((j) => terminal.has(j)),
    });
  }
  const us = names.flatMap((_, i) =>
      dist[i] !== null && !terminal.has(i) ? [i] : [],
    ),
    a = us.map((i) => us.map((j) => q(Number(i === j)).sub(p[i][j]))),
    inv = inverse(a),
    b = us.map((i) => sum([...good].map((j) => p[i][j]))),
    c = us.map((i) => sum([...bad].map((j) => p[i][j]))),
    solve = (rhs) => inv.map((r) => sum(r.map((v, i) => v.mul(rhs[i]))));
  const h = names.map((_, i) => q(Number(good.has(i)))),
    f = names.map((_, i) => q(Number(bad.has(i)))),
    g = zero(n),
    m = zero(n),
    gb = zero(n);
  solve(b).forEach((v, k) => (h[us[k]] = v));
  solve(c).forEach((v, k) => (f[us[k]] = v));
  solve(us.map((i) => h[i])).forEach((v, k) => (g[us[k]] = v));
  solve(us.map((i) => g[i].mul(2).sub(h[i]))).forEach((v, k) => (m[us[k]] = v));
  solve(us.map((i) => h[i].add(f[i]))).forEach((v, k) => (gb[us[k]] = v));
  const records = names.map((name, i) => {
    const hp = h[i].nonzero,
      mean = hp ? g[i].div(h[i]) : null;
    return {
      name,
      success_probability: String(h[i]),
      failure_probability: String(f[i]),
      never_terminal_probability: String(q(1).sub(h[i]).sub(f[i])),
      success_time_numerator: String(g[i]),
      success_second_moment_numerator: String(m[i]),
      conditional_success: hp
        ? {
            mean: String(mean),
            second_moment: String(m[i].div(h[i])),
            variance: String(m[i].div(h[i]).sub(mean.mul(mean))),
          }
        : null,
      unconditional_success_time: {
        kind: String(h[i]) === "1" ? "finite" : "infinite",
        value: String(h[i]) === "1" ? String(g[i]) : null,
      },
      conditional_terminal_mean: h[i].add(f[i]).nonzero
        ? String(gb[i].div(h[i].add(f[i])))
        : null,
      unconditional_terminal_time: {
        kind: String(h[i].add(f[i])) === "1" ? "finite" : "infinite",
        value: String(h[i].add(f[i])) === "1" ? String(gb[i]) : null,
      },
    };
  });
  const conditioned = names.map((state, i) => {
    const edges = names.map((to, j) => ({
      to,
      original_prob: String(original[i][j]),
      stopped_prob: String(p[i][j]),
      success_weight: String(h[j]),
      joint_success_mass: String(p[i][j].mul(h[j])),
      conditioned_prob: h[i].nonzero
        ? String(p[i][j].mul(h[j]).div(h[i]))
        : null,
    }));
    return {
      state,
      defined: h[i].nonzero,
      edges,
      row_sum: h[i].nonzero
        ? String(sum(edges.map((e) => q(e.conditioned_prob))))
        : null,
    };
  });
  const forecasts = names.map((start, root) => {
    let v = names.map((_, i) => q(Number(i === root))),
      previousS = q(0),
      previousF = q(0);
    const rows = [];
    for (let step = 0; step <= input.horizon; step++) {
      const cs = sum([...good].map((i) => v[i])),
        cf = sum([...bad].map((i) => v[i])),
        active = v.map((x, i) => (terminal.has(i) ? q(0) : x));
      rows.push({
        step,
        active_mass: active.map(String),
        new_success: String(cs.sub(previousS)),
        new_failure: String(cf.sub(previousF)),
        success_by_step: String(cs),
        failure_by_step: String(cf),
        still_active: String(sum(active)),
        future_success_mass: String(h[root].sub(cs)),
        conditional_success_by_step: h[root].nonzero
          ? String(cs.div(h[root]))
          : null,
        conditional_remaining: h[root].nonzero
          ? String(h[root].sub(cs).div(h[root]))
          : null,
      });
      previousS = cs;
      previousF = cf;
      v = names.map((_, j) => sum(v.map((x, i) => x.mul(p[i][j]))));
    }
    return { start, rows };
  });
  return {
    schema: "absorblab-v1",
    input,
    limits: LIMITS.slice(),
    original_matrix: enc(original),
    stopped_matrix: enc(p),
    support: {
      rounds,
      can_hit_terminal: names.filter((_, i) => dist[i] !== null),
      zero_terminal_states: names.filter((_, i) => dist[i] === null),
      paths,
    },
    components,
    linear_system: {
      unknowns: us.map((i) => names[i]),
      matrix: enc(a),
      success_rhs: b.map(String),
      failure_rhs: c.map(String),
      inverse: enc(inv),
      elimination: rowEvidence(a),
    },
    states: records,
    conditioned,
    forecasts,
  };
}

const LIMITS = [
  "One to six supplied finite Markov states; one to six positive rational transitions per row.",
  "Probabilities are supplied, not learned, calibrated or adversarial choices.",
  "Success and failure are disjoint terminal sets; first hit overrides outgoing transitions.",
  "Closed nonterminal classes can prevent any terminal hit; equations alone need not identify the least solution.",
  "Success conditioning is undefined when its probability is zero, never an invented zero conditional mean.",
  "Unconditional time to success is infinite if stopped success has probability below one.",
  "Finite exact coverage is not a proof, scaling benchmark, runtime guarantee or new algorithm.",
];

export function parseJSON(raw) {
  if (new TextEncoder().encode(raw).length > 65536)
    throw Error("input exceeds65536 bytes");
  let p = 0;
  const ws = () => {
    while (/[ \t\r\n]/.test(raw[p] ?? "") && p < raw.length) p++;
  };
  function string() {
    const start = p++;
    while (p < raw.length) {
      if (raw[p] === "\\") {
        p += 2;
        continue;
      }
      if (raw[p++] === '"') return JSON.parse(raw.slice(start, p));
    }
    throw Error("unterminated string");
  }
  function value() {
    ws();
    const c = raw[p];
    if (c === '"') return string();
    if (c === "{") {
      p++;
      const keys = new Set(),
        out = Object.create(null);
      ws();
      if (raw[p] === "}") {
        p++;
        return out;
      }
      while (true) {
        ws();
        if (raw[p] !== '"') throw Error("object key must be string");
        const k = string();
        if (keys.has(k)) throw Error("duplicate JSON key");
        keys.add(k);
        ws();
        if (raw[p++] !== ":") throw Error("missing colon");
        out[k] = value();
        ws();
        const sep = raw[p++];
        if (sep === "}") return out;
        if (sep !== ",") throw Error("missing comma");
      }
    }
    if (c === "[") {
      p++;
      const out = [];
      ws();
      if (raw[p] === "]") {
        p++;
        return out;
      }
      while (true) {
        out.push(value());
        ws();
        const sep = raw[p++];
        if (sep === "]") return out;
        if (sep !== ",") throw Error("missing comma");
      }
    }
    for (const [token, v] of [
      ["true", true],
      ["false", false],
      ["null", null],
    ])
      if (raw.startsWith(token, p)) {
        p += token.length;
        return v;
      }
    const number = raw
      .slice(p)
      .match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!number) throw Error("invalid JSON value");
    p += number[0].length;
    if (/[.eE]/.test(number[0])) throw Error("integer JSON number required");
    const n = Number(number[0]);
    if (!Number.isFinite(n)) throw Error("nonfinite JSON number");
    return n;
  }
  const result = value();
  ws();
  if (p !== raw.length) throw Error("trailing JSON content");
  return result;
}
