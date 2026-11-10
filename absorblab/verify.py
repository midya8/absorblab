"""Independent determinant/cofactor and simple-path full-record replay.

Imports only schema/equality helpers. No generator or Gauss-Jordan module.
"""

from fractions import Fraction as F
from itertools import permutations
from .input import validate, equal, LIMITS


def _det(a):
    n = len(a)
    total = F(0)
    for p in permutations(range(n)):
        v = F(
            -1 if sum(p[i] > p[j] for i in range(n) for j in range(i + 1, n)) % 2 else 1
        )
        for i, j in enumerate(p):
            v *= a[i][j]
        total += v
    return total


def _inverse(a):
    n = len(a)
    d = _det(a)
    if not d:
        raise ValueError("singular restricted first-hit system")
    return [
        [
            F((-1) ** (i + j))
            * _det([[a[r][c] for c in range(n) if c != i] for r in range(n) if r != j])
            / d
            for j in range(n)
        ]
        for i in range(n)
    ]


def _enc(a):
    return [[str(v) for v in r] for r in a]


def replay(request):
    data = validate(request)
    ss = data["states"]
    names = [s["name"] for s in ss]
    n = len(ss)
    targets = set(data["success"]) | set(data["failure"])
    good = [i for i, v in enumerate(names) if v in data["success"]]
    bad = [i for i, v in enumerate(names) if v in data["failure"]]
    terminals = good + bad
    orig = []
    p = []
    for i, s in enumerate(ss):
        row = [
            sum((F(t["prob"]) for t in s["transitions"] if t["to"] == v), F(0))
            for v in names
        ]
        orig.append(row)
        p.append([F(i == j) for j in range(n)] if i in terminals else row[:])
    # All vertex-simple paths, not the generator's reverse closure/BFS.
    reachable = []
    witnesses = []
    dist = []
    for root in range(n):
        reach = set()
        hits = []

        def walk(i, nodes):
            reach.add(i)
            if i in terminals:
                hits.append(nodes)
                return
            for j in range(n):
                if p[i][j] and j not in nodes:
                    walk(j, nodes + [j])

        walk(root, [root])
        reachable.append(reach)
        if not hits:
            witnesses.append({"start": names[root], "path": None, "probability": None})
            dist.append(None)
        else:
            best = min(hits, key=lambda xs: (len(xs), xs))
            path = []
            prob = F(1)
            for i, j in zip(best, best[1:]):
                path.append({"from": names[i], "to": names[j], "prob": str(p[i][j])})
                prob *= p[i][j]
            witnesses.append(
                {"start": names[root], "path": path, "probability": str(prob)}
            )
            dist.append(len(best) - 1)
    rounds = []
    k = 0
    while True:
        before = [names[i] for i, v in enumerate(dist) if v is not None and v <= k]
        after = [names[i] for i, v in enumerate(dist) if v is not None and v <= k + 1]
        rounds.append(
            {
                "index": k,
                "before": before,
                "after": after,
                "added": [v for v in after if v not in before],
            }
        )
        if before == after:
            break
        k += 1
    comps = []
    used = set()
    for i in range(n):
        if i in used:
            continue
        c = [j for j in range(n) if j in reachable[i] and i in reachable[j]]
        used.update(c)
        closed = all(not p[v][w] or w in c for v in c for w in range(n))
        comps.append(
            {
                "states": [names[j] for j in c],
                "closed": closed,
                "terminal_kind": "success"
                if i in good
                else "failure"
                if i in bad
                else "none",
                "nonterminal_trap": closed and not any(j in terminals for j in c),
            }
        )
    us = [i for i, d in enumerate(dist) if d is not None and i not in terminals]
    a = [[F(i == j) - p[i][j] for j in us] for i in us]
    inv = _inverse(a)
    b = [sum((p[i][j] for j in good), F(0)) for i in us]
    c = [sum((p[i][j] for j in bad), F(0)) for i in us]

    def solve(rhs):
        return [
            sum((inv[i][j] * rhs[j] for j in range(len(us))), F(0))
            for i in range(len(us))
        ]

    h = [F(i in good) for i in range(n)]
    f = [F(i in bad) for i in range(n)]
    for i, v in zip(us, solve(b)):
        h[i] = v
    for i, v in zip(us, solve(c)):
        f[i] = v
    # Check exact inverse/residuals separately from determinant construction.
    for i in range(len(us)):
        for j in range(len(us)):
            if sum((a[i][k] * inv[k][j] for k in range(len(us))), F(0)) != F(i == j):
                raise ValueError("inverse residual")
    for i in range(n):
        if not (0 <= h[i] <= 1 and 0 <= f[i] <= 1 and h[i] + f[i] <= 1):
            raise ValueError("invalid probability solution")
        if i not in terminals and (
            h[i] != sum((p[i][j] * h[j] for j in range(n)), F(0))
            or f[i] != sum((p[i][j] * f[j] for j in range(n)), F(0))
        ):
            raise ValueError("harmonic residual")
    g = [F(0)] * n
    m = [F(0)] * n
    gb = [F(0)] * n
    for i, v in zip(us, solve([h[i] for i in us])):
        g[i] = v
    for i, v in zip(us, solve([2 * g[i] - h[i] for i in us])):
        m[i] = v
    for i, v in zip(us, solve([h[i] + f[i] for i in us])):
        gb[i] = v
    rows = []
    conditioned = []
    for i in range(n):
        cond = None
        if h[i]:
            cond = {
                "mean": str(g[i] / h[i]),
                "second_moment": str(m[i] / h[i]),
                "variance": str(m[i] / h[i] - g[i] ** 2 / h[i] ** 2),
            }
        rows.append(
            {
                "name": names[i],
                "success_probability": str(h[i]),
                "failure_probability": str(f[i]),
                "never_terminal_probability": str(1 - h[i] - f[i]),
                "success_time_numerator": str(g[i]),
                "success_second_moment_numerator": str(m[i]),
                "conditional_success": cond,
                "unconditional_success_time": {
                    "kind": "finite" if h[i] == 1 else "infinite",
                    "value": str(g[i]) if h[i] == 1 else None,
                },
                "conditional_terminal_mean": str(gb[i] / (h[i] + f[i]))
                if h[i] + f[i]
                else None,
                "unconditional_terminal_time": {
                    "kind": "finite" if h[i] + f[i] == 1 else "infinite",
                    "value": str(gb[i]) if h[i] + f[i] == 1 else None,
                },
            }
        )
        edges = [
            {
                "to": names[j],
                "original_prob": str(orig[i][j]),
                "stopped_prob": str(p[i][j]),
                "success_weight": str(h[j]),
                "joint_success_mass": str(p[i][j] * h[j]),
                "conditioned_prob": str(p[i][j] * h[j] / h[i]) if h[i] else None,
            }
            for j in range(n)
        ]
        conditioned.append(
            {
                "state": names[i],
                "defined": h[i] != 0,
                "edges": edges,
                "row_sum": str(sum((F(e["conditioned_prob"]) for e in edges), F(0)))
                if h[i]
                else None,
            }
        )
    # Dense stopped-chain powers retain terminal mass rather than transferring
    # active mass and collecting edge hits as the generator does.
    forecasts = []
    for root in range(n):
        v = [F(i == root) for i in range(n)]
        history = []
        previous_s = previous_f = F(0)
        for step in range(data["horizon"] + 1):
            cs = sum((v[i] for i in good), F(0))
            cf = sum((v[i] for i in bad), F(0))
            active = [F(0) if i in terminals else v[i] for i in range(n)]
            history.append(
                {
                    "step": step,
                    "active_mass": [str(x) for x in active],
                    "new_success": str(cs - previous_s),
                    "new_failure": str(cf - previous_f),
                    "success_by_step": str(cs),
                    "failure_by_step": str(cf),
                    "still_active": str(sum(active)),
                    "future_success_mass": str(h[root] - cs),
                    "conditional_success_by_step": str(cs / h[root])
                    if h[root]
                    else None,
                    "conditional_remaining": str((h[root] - cs) / h[root])
                    if h[root]
                    else None,
                }
            )
            previous_s, previous_f = cs, cf
            v = [sum((v[i] * p[i][j] for i in range(n)), F(0)) for j in range(n)]
        forecasts.append({"start": names[root], "rows": history})
    # Canonical elementary row-operation evidence is replayed, not trusted.
    z = [a[i][:] + [F(i == j) for j in range(len(us))] for i in range(len(us))]
    ops = []
    for k in range(len(us)):
        before = _enc(z)
        swap = min(i for i in range(k, len(us)) if z[i][k])
        z[k], z[swap] = z[swap], z[k]
        div = z[k][k]
        z[k] = [v / div for v in z[k]]
        norm = _enc(z)
        factors = [F(0) if i == k else z[i][k] for i in range(len(us))]
        z = [
            row
            if i == k
            else [row[j] - factors[i] * z[k][j] for j in range(2 * len(us))]
            for i, row in enumerate(z)
        ]
        ops.append(
            {
                "column": k,
                "swap_row": swap,
                "before": before,
                "divisor": str(div),
                "normalized": norm,
                "factors": [str(v) for v in factors],
                "after": _enc(z),
            }
        )
    return {
        "schema": "absorblab-v1",
        "input": data,
        "limits": LIMITS[:],
        "original_matrix": _enc(orig),
        "stopped_matrix": _enc(p),
        "support": {
            "rounds": rounds,
            "can_hit_terminal": [names[i] for i, d in enumerate(dist) if d is not None],
            "zero_terminal_states": [names[i] for i, d in enumerate(dist) if d is None],
            "paths": witnesses,
        },
        "components": comps,
        "linear_system": {
            "unknowns": [names[i] for i in us],
            "matrix": _enc(a),
            "success_rhs": [str(v) for v in b],
            "failure_rhs": [str(v) for v in c],
            "inverse": _enc(inv),
            "elimination": ops,
        },
        "states": rows,
        "conditioned": conditioned,
        "forecasts": forecasts,
    }


def verify(report):
    if type(report) is not dict or "input" not in report:
        raise ValueError("report requires input")
    equal(replay(report["input"]), report)
    return True
