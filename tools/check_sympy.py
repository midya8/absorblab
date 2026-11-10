"""Optional development-only exact SymPy reference; no runtime dependency."""

import itertools, json, random, sys
from pathlib import Path
from fractions import Fraction
import sympy as S

sys.path.insert(
    0,
    str(
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1]
    ),
)
from absorblab import analyze

root = Path(sys.path[0])
requests = [c["input"] for c in json.load(open(root / "docs/controls.json"))]
opts = [
    [(0, Fraction(1))],
    [(1, Fraction(1))],
    [(0, Fraction(1, 2)), (1, Fraction(1, 2))],
]
for rows in itertools.product(opts, repeat=2):
    for status in itertools.product(range(3), repeat=2):
        requests.append(
            {
                "states": [
                    {
                        "name": "s" + str(i),
                        "transitions": [
                            {"to": "s" + str(j), "prob": str(p)} for j, p in row
                        ],
                    }
                    for i, row in enumerate(rows)
                ],
                "success": ["s" + str(i) for i, s in enumerate(status) if s == 1],
                "failure": ["s" + str(i) for i, s in enumerate(status) if s == 2],
                "horizon": 0,
            }
        )
rng = random.Random(897412)
for k in range(120):
    n = 2 + k % 5
    rows = []
    for i in range(n):
        ts = rng.sample(range(n), rng.randint(1, n))
        ws = [rng.randint(1, 6) for _ in ts]
        rows.append(
            {
                "name": "s" + str(i),
                "transitions": [
                    {"to": "s" + str(j), "prob": str(Fraction(w, sum(ws)))}
                    for j, w in zip(ts, ws)
                ],
            }
        )
    status = [rng.randrange(3) for _ in range(n)]
    requests.append(
        {
            "states": rows,
            "success": ["s" + str(i) for i, s in enumerate(status) if s == 1],
            "failure": ["s" + str(i) for i, s in enumerate(status) if s == 2],
            "horizon": 0,
        }
    )
roots = conditional = 0
for req in requests:
    names = [s["name"] for s in req["states"]]
    n = len(names)
    good = {names.index(v) for v in req["success"]}
    bad = {names.index(v) for v in req["failure"]}
    p = S.zeros(n)
    for i, s in enumerate(req["states"]):
        for t in s["transitions"]:
            p[i, names.index(t["to"])] = S.Rational(t["prob"])
    for i in good | bad:
        for j in range(n):
            p[i, j] = int(i == j)
    # Reachability via a full Boolean transitive closure, not reverse rounds.
    reach = [[bool(p[i, j]) or i == j for j in range(n)] for i in range(n)]
    for k in range(n):
        for i in range(n):
            for j in range(n):
                reach[i][j] = reach[i][j] or reach[i][k] and reach[k][j]
    us = [
        i
        for i in range(n)
        if i not in good | bad and any(reach[i][j] for j in good | bad)
    ]
    a = S.eye(len(us)) - p.extract(us, us)
    inverse = a.inv(method="ADJ") if us else S.zeros(0)
    hs = [S.Rational(int(i in good)) for i in range(n)]
    hf = [S.Rational(int(i in bad)) for i in range(n)]
    if us:
        v = inverse * S.Matrix([sum(p[i, j] for j in good) for i in us])
        w = inverse * S.Matrix([sum(p[i, j] for j in bad) for i in us])
        for i, x, y in zip(us, v, w):
            hs[i] = x
            hf[i] = y
    cond = [i for i in range(n) if hs[i] > 0 and i not in good]
    transform = S.Matrix(
        len(cond),
        len(cond),
        lambda i, j: p[cond[i], cond[j]] * hs[cond[j]] / hs[cond[i]],
    )
    if cond:
        ai = S.eye(len(cond)) - transform
        means = ai.LUsolve(S.ones(len(cond), 1))
        seconds = ai.LUsolve(2 * means - S.ones(len(cond), 1))
    r = analyze(req)
    for i, s in enumerate(r["states"]):
        assert S.Rational(s["success_probability"]) == hs[i]
        assert S.Rational(s["failure_probability"]) == hf[i]
        roots += 1
        if hs[i]:
            mean = S.Rational(0) if i in good else means[cond.index(i)]
            second = S.Rational(0) if i in good else seconds[cond.index(i)]
            assert S.Rational(s["conditional_success"]["mean"]) == mean
            assert S.Rational(s["conditional_success"]["second_moment"]) == second
            assert S.Rational(s["conditional_success"]["variance"]) == second - mean**2
            conditional += 1
print(
    json.dumps(
        {
            "sympy_version": S.__version__,
            "requests": len(requests),
            "state_probability_pairs": roots,
            "conditional_moment_triplets": conditional,
            "inverse_method": "ADJ",
            "conditioned_time_solver": "LUsolve",
        }
    )
)
