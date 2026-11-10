import { analyze, parseJSON } from "./engine.js";
const $ = (id) => document.getElementById(id),
  controls = await (await fetch("controls.json")).json();
let report = null;
function options(id, values) {
  $(id).replaceChildren(
    ...values.map((text, i) => {
      const e = document.createElement("option");
      e.value = i;
      e.textContent = text;
      return e;
    }),
  );
}
function cards(id, rows) {
  $(id).replaceChildren(
    ...rows.map(([title, body, trap]) => {
      const box = document.createElement("article");
      box.className = "card" + (trap ? " trap" : "");
      const h = document.createElement("h3"),
        p = document.createElement("p");
      h.textContent = title;
      p.textContent = body;
      box.append(h, p);
      return box;
    }),
  );
}
const list = (xs) => (xs.length ? xs.join(", ") : "none"),
  time = (v) => (v.kind === "finite" ? v.value : "infinite"),
  conditional = (v) =>
    v === null ? "undefined (zero success probability)" : v;
function selected() {
  if (!report) return;
  const i = Number($("state").value),
    s = report.states[i],
    row = report.conditioned[i];
  $("metrics").replaceChildren(
    ...[
      ["Success", s.success_probability],
      ["Failure", s.failure_probability],
      ["Never terminal", s.never_terminal_probability],
    ].map(([k, v]) => {
      const e = document.createElement("div");
      e.className = "metric";
      const span = document.createElement("span"),
        strong = document.createElement("strong");
      span.textContent = k;
      strong.textContent = v;
      e.append(span, strong);
      return e;
    }),
  );
  cards("state-view", [
    [
      s.name + " / time given success",
      s.conditional_success
        ? `Mean: ${s.conditional_success.mean}. Second moment: ${s.conditional_success.second_moment}. Variance: ${s.conditional_success.variance}.`
        : "Undefined: success has probability zero.",
    ],
    [
      "Unconditional first-hit times",
      `Stopped success: ${time(s.unconditional_success_time)}. Any terminal: ${time(s.unconditional_terminal_time)}. Mean given a terminal hit: ${s.conditional_terminal_mean ?? "undefined"}.`,
    ],
    [
      "Weighted success moments",
      `E[T; success] = ${s.success_time_numerator}. E[T²; success] = ${s.success_second_moment_numerator}. These are weighted numerators, not conditional means.`,
    ],
  ]);
  cards(
    "conditioned",
    row.edges.map((e) => [
      `${s.name} → ${e.to}`,
      `Original: ${e.original_prob}. First-hit stopped: ${e.stopped_prob}. Future success h(${e.to}): ${e.success_weight}. Joint success mass: ${e.joint_success_mass}. Given eventual success: ${conditional(e.conditioned_prob)}.`,
    ]),
  );
  forecast();
  const p = report.support.paths[i];
  cards("path", [
    [
      `Terminal path from ${s.name}`,
      p.path === null
        ? "No positive-support terminal path."
        : p.path.length
          ? `${p.path.map((e) => e.from + " → " + e.to + " (" + e.prob + ")").join("; ")}. Product probability: ${p.probability}.`
          : "Already terminal at time zero; probability 1.",
    ],
  ]);
}
function forecast() {
  if (!report) return;
  const i = Number($("state").value),
    r = report.forecasts[i].rows[Number($("step").value)];
  cards("forecast", [
    [
      `After ${r.step} transitions`,
      `First success this step: ${r.new_success}. First failure this step: ${r.new_failure}. Success so far: ${r.success_by_step}. Failure so far: ${r.failure_by_step}. Still active: ${r.still_active}.`,
    ],
    [
      "Successful trajectories not yet finished",
      `Future success mass: ${r.future_success_mass}. Given eventual success, finished by now: ${conditional(r.conditional_success_by_step)}. Remaining: ${conditional(r.conditional_remaining)}.`,
    ],
  ]);
  cards(
    "active",
    report.states.map((s, j) => [s.name + " / active mass", r.active_mass[j]]),
  );
}
function support() {
  if (!report) return;
  const r = report.support.rounds[Number($("support").value)];
  cards("support-view", [
    [
      `Round ${r.index}`,
      `Before: ${list(r.before)}. After: ${list(r.after)}. Added: ${list(r.added)}.`,
    ],
    [
      "Boundary outside the restricted system",
      `Can hit a terminal: ${list(report.support.can_hit_terminal)}. Zero terminal-hit states: ${list(report.support.zero_terminal_states)}.`,
    ],
  ]);
}
function stage() {
  if (!report) return;
  const l = report.linear_system;
  $("stage").textContent = l.elimination.length
    ? JSON.stringify(l.elimination[Number($("elimination").value)], null, 2)
    : "No transient unknowns. The empty system needs no row operation.";
}
function invalidate() {
  report = null;
  window.absorbReport = null;
  $("results").hidden = true;
  $("download").disabled = true;
  $("json").textContent = "";
  $("status").textContent =
    "Input changed. Analyze to replace the certificate.";
}
function run() {
  invalidate();
  try {
    report = analyze(parseJSON($("input").value));
    window.absorbReport = report;
    options(
      "state",
      report.states.map((s) => s.name),
    );
    options(
      "step",
      report.forecasts[0].rows.map((r) => String(r.step)),
    );
    options(
      "support",
      report.support.rounds.map((r) => "Round " + r.index),
    );
    options(
      "elimination",
      report.linear_system.elimination.map((r) => "Column " + r.column),
    );
    $("elimination").disabled = report.linear_system.elimination.length === 0;
    cards(
      "components",
      report.components.map((c) => [
        list(c.states),
        `Closed: ${c.closed}. Terminal kind: ${c.terminal_kind}. Nonterminal trap: ${c.nonterminal_trap}.`,
        c.nonterminal_trap,
      ]),
    );
    const l = report.linear_system;
    cards("system", [
      ["Unknowns", list(l.unknowns)],
      ["I-Q", JSON.stringify(l.matrix)],
      ["Exact inverse", JSON.stringify(l.inverse)],
      [
        "Boundary right-hand sides",
        `Success: ${l.success_rhs.join(", ") || "empty"}. Failure: ${l.failure_rhs.join(", ") || "empty"}.`,
      ],
    ]);
    $("limits").replaceChildren(
      ...report.limits.map((x) => {
        const li = document.createElement("li");
        li.textContent = x;
        return li;
      }),
    );
    $("json").textContent = JSON.stringify(report, null, 2);
    selected();
    support();
    stage();
    $("results").hidden = false;
    $("download").disabled = false;
    $("status").textContent =
      "Exact certificate ready. All calculations ran locally.";
  } catch (e) {
    $("status").textContent = "Invalid input: " + e.message;
  }
}
options(
  "control",
  controls.map((c) => c.title),
);
function choose() {
  const c = controls[Number($("control").value)];
  $("input").value = JSON.stringify(c.input, null, 2);
  $("why").textContent = c.why;
  run();
}
$("control").addEventListener("change", choose);
$("input").addEventListener("input", () => {
  $("why").textContent =
    "Custom supplied chain. No example interpretation applies.";
  invalidate();
});
$("run").addEventListener("click", run);
$("state").addEventListener("change", selected);
$("step").addEventListener("change", forecast);
$("support").addEventListener("change", support);
$("elimination").addEventListener("change", stage);
$("download").addEventListener("click", () => {
  if (!report) return;
  const u = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    ),
    a = document.createElement("a");
  a.href = u;
  a.download = "absorblab-certificate.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
});
choose();
