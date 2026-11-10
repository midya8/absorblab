import { analyzeLumping, parseJSON } from "./lumping-engine.js";
const $ = (id) => document.getElementById(id),
  el = (tag, text) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    return e;
  },
  fmt = (x) => (typeof x === "object" ? JSON.stringify(x) : String(x)),
  yes = (x) => (x ? "yes" : "no"),
  part = (bs) =>
    bs.map((b) => "{" + b.map((i) => "s" + i).join(",") + "}").join(" | ");
let controls = [],
  report = null;
function options(id, rows) {
  $(id).replaceChildren(
    ...rows.map(([v, t]) => {
      const o = el("option", t);
      o.value = String(v);
      return o;
    }),
  );
}
function cards(id, rows) {
  $(id).replaceChildren(
    ...rows.map(([title, body, trap]) => {
      const c = el("article");
      c.className = "card" + (trap ? " trap" : "");
      c.append(el("h3", title), el("p", body));
      return c;
    }),
  );
}
function table(id, headers, rows) {
  const h = el("thead"),
    tr = el("tr"),
    b = el("tbody");
  for (const x of headers) {
    const th = el("th", x);
    th.scope = "col";
    tr.append(th);
  }
  h.append(tr);
  for (const x of rows) {
    const row = el("tr");
    if (x.selected) row.className = "selected";
    for (const v of x.cells ?? x) row.append(el("td", fmt(v)));
    b.append(row);
  }
  $(id).replaceChildren(h, b);
}
const palette = [
  "#bed9ce",
  "#f0d6ab",
  "#c9d4ed",
  "#e1c5d4",
  "#d3dfb3",
  "#d7d5ce",
];
function graph(id, matrix, labels, groups) {
  const svg = $(id),
    NS = "http://www.w3.org/2000/svg",
    add = (tag, attrs, parent = svg) => {
      const e = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
      parent.append(e);
      return e;
    };
  svg.replaceChildren();
  const n = labels.length,
    points = labels.map((_, i) =>
      n === 1
        ? [200, 200]
        : [
            200 + 120 * Math.cos(-Math.PI / 2 + (2 * Math.PI * i) / n),
            200 + 120 * Math.sin(-Math.PI / 2 + (2 * Math.PI * i) / n),
          ],
    ),
    defs = add("defs", {}),
    marker = add(
      "marker",
      {
        id: id + "-arrow",
        viewBox: "0 0 10 10",
        refX: 9,
        refY: 5,
        markerWidth: 7,
        markerHeight: 7,
        orient: "auto",
      },
      defs,
    );
  add("path", { d: "M0,0 L10,5 L0,10 z", fill: "#7f9188" }, marker);
  for (let a = 0; a < n; a++)
    for (let b = 0; b < n; b++)
      if (matrix[a][b] !== "0") {
        const [x, y] = points[a],
          [u, v] = points[b];
        let d, tx, ty;
        if (a === b) {
          const radial = Math.hypot(x - 200, y - 200),
            ux = radial ? (x - 200) / radial : 0,
            uy = radial ? (y - 200) / radial : -1;
          const px = -uy,
            py = ux;
          d = `M${x + 18 * ux + 16 * px},${y + 18 * uy + 16 * py} C${x + 67 * ux + 48 * px},${y + 67 * uy + 48 * py} ${x + 67 * ux - 48 * px},${y + 67 * uy - 48 * py} ${x + 18 * ux - 16 * px},${y + 18 * uy - 16 * py}`;
          tx = x + 61 * ux;
          ty = y + 61 * uy;
        } else {
          const dx = u - x,
            dy = v - y,
            len = Math.hypot(dx, dy),
            sx = x + (27 * dx) / len,
            sy = y + (27 * dy) / len,
            ex = u - (29 * dx) / len,
            ey = v - (29 * dy) / len,
            opp = matrix[b][a] !== "0",
            cx = (sx + ex) / 2 - ((opp ? 22 : 0) * dy) / len,
            cy = (sy + ey) / 2 + ((opp ? 22 : 0) * dx) / len;
          d = opp
            ? `M${sx},${sy} Q${cx},${cy} ${ex},${ey}`
            : `M${sx},${sy} L${ex},${ey}`;
          tx = (sx + ex) / 2 - ((opp ? 24 : 9) * dy) / len;
          ty = (sy + ey) / 2 + ((opp ? 24 : 9) * dx) / len;
        }
        add("path", {
          d,
          class: "edge",
          "marker-end": `url(#${id}-arrow)`,
          "data-source": a,
          "data-target": b,
          "data-prob": matrix[a][b],
        });
        add("text", {
          x: tx,
          y: ty,
          class: "edge-label",
          "text-anchor": "middle",
        }).textContent = matrix[a][b];
      }
  for (let i = 0; i < n; i++) {
    const [x, y] = points[i],
      g = add("g", { "data-state": i, "data-block": groups[i] });
    add(
      "circle",
      {
        cx: x,
        cy: y,
        r: 25,
        class: "node",
        fill: palette[groups[i] % palette.length],
      },
      g,
    );
    add("text", { x, y, class: "node-label" }, g).textContent = labels[i];
    add("title", {}, g).textContent = labels[i] + " / block " + groups[i];
  }
}
function round() {
  if (!report) return;
  const r = report.rounds[Number($("round").value)],
    groups = report.colors.map((_, i) =>
      r.blocks.findIndex((b) => b.includes(i)),
    );
  cards("round-summary", [
    ["Current partition", part(r.blocks)],
    ["Next partition", part(r.next_blocks)],
    [
      "Fixed point",
      r.fixed
        ? "Every same-block pair agrees in every destination block."
        : "At least one same-block pair differs. All resulting splits occur together.",
      !r.fixed,
    ],
  ]);
  table(
    "mass-table",
    [
      "State",
      "Current block",
      "Tag / status",
      ...r.blocks.map((b, k) => "B" + k + " " + part([b])),
    ],
    r.masses.map((row, i) => [
      "s" + i,
      groups[i],
      report.colors[i].join(" / "),
      ...row,
    ]),
  );
  table(
    "pair-table",
    ["Left", "Right", "Same observation", "Unequal destination blocks"],
    r.pairs.map((p) => [
      "s" + p.left,
      "s" + p.right,
      yes(p.same_observation),
      p.unequal_blocks
        .map((x) => "B" + x.block + ": " + x.left_mass + " ≠ " + x.right_mass)
        .join("; ") || "none",
    ]),
  );
  $("round-json").textContent = JSON.stringify(r, null, 2);
  graph(
    "original-graph",
    report.original_matrix,
    report.colors.map((_, i) => "s" + i),
    groups,
  );
  graph(
    "quotient-graph",
    report.quotient_matrix,
    report.final_blocks.map((_, i) => "q" + i),
    report.final_blocks.map((_, i) => i),
  );
}
function pair() {
  if (!report) return;
  const x = report.pair_witnesses[Number($("pair").value)];
  if (!x) {
    cards("pair-summary", [
      ["No distinct pair", "A one-state chain has no distinct state pairs."],
    ]);
    $("open-split").disabled = true;
    return;
  }
  let rows;
  if (x.kind === "observation")
    rows = [
      [
        "Different observation contract",
        "s" +
          x.left +
          ": " +
          x.left_color.join(" / ") +
          "\ns" +
          x.right +
          ": " +
          x.right_color.join(" / "),
        true,
      ],
    ];
  else if (x.kind === "equivalent")
    rows = [
      [
        "Equivalent original states",
        "s" +
          x.left +
          " and s" +
          x.right +
          " both map to q" +
          x.block +
          ". Every final block mass agrees.",
      ],
    ];
  else
    rows = [
      [
        "First separating refinement",
        "Round " + x.round + " / s" + x.left + " versus s" + x.right,
        true,
      ],
      [
        "A previously visible destination block",
        part([x.destination_members]) +
          "\ns" +
          x.left +
          " sends " +
          x.left_mass +
          "; s" +
          x.right +
          " sends " +
          x.right_mass +
          ".",
        true,
      ],
    ];
  cards("pair-summary", rows);
  $("open-split").disabled = x.kind !== "split";
  $("open-split").dataset.round = x.round ?? "";
}
function partition() {
  if (!report) return;
  const i = Number($("partition").value),
    p = report.partition_atlas[i];
  cards("partition-summary", [
    ["This candidate", part(p.blocks)],
    [
      "Two separate requirements",
      "Observations respected: " +
        yes(p.respects_observations) +
        "\nEvery block mass agrees: " +
        yes(p.stable) +
        "\nAllowed: " +
        yes(p.allowed) +
        "\nRefines final partition: " +
        yes(p.refines_final),
      !p.allowed,
    ],
    [
      "First observation conflict",
      p.first_observation_conflict ? fmt(p.first_observation_conflict) : "none",
    ],
    [
      "First transition-mass conflict",
      p.first_mass_conflict ? fmt(p.first_mass_conflict) : "none",
    ],
  ]);
  table(
    "partition-masses",
    ["State", ...p.blocks.map((b, k) => "B" + k + " " + part([b]))],
    p.masses.map((r, i) => ["s" + i, ...r]),
  );
  table(
    "atlas",
    [
      "Index",
      "Partition",
      "Observations",
      "Stable",
      "Allowed",
      "Refines final",
    ],
    report.partition_atlas.map((p, k) => ({
      selected: i === k,
      cells: [
        k,
        part(p.blocks),
        yes(p.respects_observations),
        yes(p.stable),
        yes(p.allowed),
        yes(p.refines_final),
      ],
    })),
  );
  $("partition-json").textContent = JSON.stringify(p, null, 2);
}
function forecast() {
  if (!report) return;
  const i = Number($("state").value),
    k = Number($("step").value),
    f = report.forecasts[i],
    row = f.rows[k],
    hit = report.first_hit[i];
  cards("forecast-summary", [
    [
      "Starting state / final block",
      "s" +
        i +
        " (" +
        report.input.chain.states[i].name +
        ") → q" +
        f.quotient_start,
    ],
    [
      "Exact raw-chain block distribution",
      "After " +
        k +
        " transitions: " +
        yes(row.equal) +
        " / both computations agree.",
    ],
  ]);
  table(
    "forecast-table",
    ["Final block", "Members", "Original aggregated mass", "Quotient mass"],
    report.final_blocks.map((b, j) => [
      "q" + j,
      part([b]),
      row.original_blocks[j],
      row.quotient_blocks[j],
    ]),
  );
  const fields = [
    "success_probability",
    "failure_probability",
    "never_terminal_probability",
    "success_time_numerator",
    "success_second_moment_numerator",
    "conditional_success",
    "unconditional_success_time",
    "conditional_terminal_mean",
    "unconditional_terminal_time",
  ];
  table(
    "hit-table",
    ["First-hit quantity", "Original", "Quotient"],
    fields.map((key) => [key, hit.original[key], hit.quotient[key]]),
  );
}
function clear() {
  report = null;
  window.currentLumpingReport = null;
  $("results").hidden = true;
  $("download").disabled = true;
  for (const e of document.querySelectorAll(
    "#results table,#results .cards,#results svg,#report-json,#round-json,#partition-json",
  ))
    e.replaceChildren();
  $("status").textContent = "Input changed. Refine again.";
}
function run() {
  clear();
  try {
    report = analyzeLumping(parseJSON($("input").value));
    window.currentLumpingReport = report;
    $("results").hidden = false;
    $("download").disabled = false;
    $("status").textContent =
      "Exact labeled lumpability: " +
      report.partition_atlas.length +
      " partitions checked, " +
      report.rounds.length +
      " refinement states including the fixed point.";
    $("summary").replaceChildren(
      ...[
        ["Original states", report.colors.length],
        ["Quotient states", report.final_blocks.length],
        [
          "Allowed partitions",
          report.partition_atlas.filter((p) => p.allowed).length,
        ],
      ].map(([label, value]) => {
        const box = el("div");
        box.className = "metric";
        box.append(el("span", label), el("strong", value));
        return box;
      }),
    );
    options(
      "round",
      report.rounds.map((r) => [
        r.round,
        "Round " +
          r.round +
          " / " +
          r.blocks.length +
          " blocks" +
          (r.fixed
            ? " / fixed point"
            : " → " + r.next_blocks.length + " blocks"),
      ]),
    );
    options(
      "pair",
      report.pair_witnesses.map((p, i) => [
        i,
        "s" + p.left + " / s" + p.right + " / " + p.kind,
      ]),
    );
    options(
      "partition",
      report.partition_atlas.map((p, i) => [
        i,
        i + " / " + part(p.blocks) + (p.allowed ? " / allowed" : ""),
      ]),
    );
    $("partition").value = report.partition_atlas.findIndex(
      (p) => JSON.stringify(p.blocks) === JSON.stringify(report.initial_blocks),
    );
    options(
      "state",
      report.colors.map((_, i) => [
        i,
        "s" + i + " / " + report.input.chain.states[i].name,
      ]),
    );
    options(
      "step",
      report.forecasts[0].rows.map((r) => [r.step, r.step]),
    );
    table(
      "block-table",
      ["Final block", "Original indices", "Names", "Observation", "Status"],
      report.final_blocks.map((b, i) => [
        "q" + i,
        part([b]),
        b.map((j) => report.input.chain.states[j].name).join(", "),
        report.colors[b[0]][0],
        report.colors[b[0]][1],
      ]),
    );
    table(
      "identity-table",
      [
        "Original state",
        "Source block",
        "Destination block",
        "Original mass",
        "Quotient probability",
        "Equal",
      ],
      report.intertwining.map((x) => [
        "s" + x.state,
        "q" + x.source_block,
        "q" + x.destination_block,
        x.original_mass,
        x.quotient_prob,
        yes(x.equal),
      ]),
    );
    $("report-json").textContent = JSON.stringify(report, null, 2);
    $("limits").replaceChildren(...report.limits.map((x) => el("li", x)));
    round();
    pair();
    partition();
    forecast();
  } catch (e) {
    clear();
    $("status").textContent = "Invalid input: " + e.message;
  }
}
function control() {
  const c = controls[Number($("control").value)];
  $("why").textContent = c.why;
  $("input").value = JSON.stringify(c.input, null, 2);
  run();
}
$("control").addEventListener("change", control);
$("input").addEventListener("input", clear);
$("run").addEventListener("click", run);
$("round").addEventListener("change", round);
$("pair").addEventListener("change", pair);
$("partition").addEventListener("change", partition);
$("state").addEventListener("change", forecast);
$("step").addEventListener("change", forecast);
$("open-split").addEventListener("click", () => {
  $("round").value = $("open-split").dataset.round;
  round();
  $("round").scrollIntoView({ block: "start" });
});
$("download").addEventListener("click", () => {
  if (!report) return;
  const u = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2) + "\n"], {
        type: "application/json",
      }),
    ),
    a = el("a");
  a.href = u;
  a.download = "absorblab-lumping.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
});
try {
  const r = await fetch("lumping-controls.json");
  if (!r.ok) throw Error("controls unavailable");
  controls = await r.json();
  options(
    "control",
    controls.map((c, i) => [i, c.name]),
  );
  control();
} catch (e) {
  $("status").textContent = "Could not start: " + e.message;
}
