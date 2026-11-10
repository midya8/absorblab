"""Established finite-chain first-hit equations, with exact evidence."""

from fractions import Fraction as F
from functools import reduce
from .input import validate, LIMITS
from .linear import invert, encode, matvec


def analyze(request):
    data = validate(request)
    states = data["states"]
    names = [s["name"] for s in states]
    n = len(names)
    ix = {v: i for i, v in enumerate(names)}
    good = {ix[v] for v in data["success"]}
    bad = {ix[v] for v in data["failure"]}
    terminal = good | bad
    original = [[F(0) for _ in states] for _ in states]
    for i, s in enumerate(states):
        for t in s["transitions"]:
            original[i][ix[t["to"]]] = F(t["prob"])
    p = [
        row[:] if i not in terminal else [F(i == j) for j in range(n)]
        for i, row in enumerate(original)
    ]
    adj = [[j for j, v in enumerate(row) if v] for row in p]
    reached = set(terminal)
    rounds = []
    while True:
        after = reached | {i for i in range(n) if any(j in reached for j in adj[i])}
        rounds.append(
            {
                "index": len(rounds),
                "before": [names[i] for i in range(n) if i in reached],
                "after": [names[i] for i in range(n) if i in after],
                "added": [names[i] for i in range(n) if i in after - reached],
            }
        )
        if after == reached:
            break
        reached = after
    unknown = [i for i in range(n) if i in reached - terminal]
    paths = []
    for root in range(n):
        queue = [(root, [])]
        seen = {root}
        found = None
        for i, path in queue:
            if i in terminal:
                found = path
                break
            for j in adj[i]:
                if j not in seen:
                    seen.add(j)
                    queue.append(
                        (
                            j,
                            path
                            + [
                                {"from": names[i], "to": names[j], "prob": str(p[i][j])}
                            ],
                        )
                    )
        paths.append(
            {
                "start": names[root],
                "path": found,
                "probability": str(reduce(lambda a, e: a * F(e["prob"]), found, F(1)))
                if found is not None
                else None,
            }
        )
    # Tarjan SCCs on the stopped support, ordered by original state positions.
    ids = {}
    low = {}
    stack = []
    on = set()
    components = []

    def visit(v):
        ids[v] = low[v] = len(ids)
        stack.append(v)
        on.add(v)
        for w in adj[v]:
            if w not in ids:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], ids[w])
        if low[v] == ids[v]:
            c = []
            while True:
                w = stack.pop()
                on.remove(w)
                c.append(w)
                if w == v:
                    break
            components.append(sorted(c))

    for i in range(n):
        if i not in ids:
            visit(i)
    comps = []
    for c in sorted(components, key=lambda c: c[0]):
        closed = all(j in c for i in c for j in adj[i])
        comps.append(
            {
                "states": [names[i] for i in c],
                "closed": closed,
                "terminal_kind": "success"
                if c[0] in good
                else "failure"
                if c[0] in bad
                else "none",
                "nonterminal_trap": closed and not (set(c) & terminal),
            }
        )
    a = [[F(i == j) - p[i][j] for j in unknown] for i in unknown]
    inv, steps = invert(a)
    b1 = [sum((p[i][j] for j in good), F(0)) for i in unknown]
    b0 = [sum((p[i][j] for j in bad), F(0)) for i in unknown]
    h = [F(i in good) for i in range(n)]
    f = [F(i in bad) for i in range(n)]
    for i, v in zip(unknown, matvec(inv, b1)):
        h[i] = v
    for i, v in zip(unknown, matvec(inv, b0)):
        f[i] = v
    g = [F(0) for _ in states]
    m2 = g[:]
    gb = g[:]
    for i, v in zip(unknown, matvec(inv, [h[i] for i in unknown])):
        g[i] = v
    for i, v in zip(unknown, matvec(inv, [2 * g[i] - h[i] for i in unknown])):
        m2[i] = v
    for i, v in zip(unknown, matvec(inv, [h[i] + f[i] for i in unknown])):
        gb[i] = v
    rows = []
    conditioned = []
    for i in range(n):
        rows.append(
            {
                "name": names[i],
                "success_probability": str(h[i]),
                "failure_probability": str(f[i]),
                "never_terminal_probability": str(1 - h[i] - f[i]),
                "success_time_numerator": str(g[i]),
                "success_second_moment_numerator": str(m2[i]),
                "conditional_success": {
                    "mean": str(g[i] / h[i]),
                    "second_moment": str(m2[i] / h[i]),
                    "variance": str(m2[i] / h[i] - (g[i] / h[i]) ** 2),
                }
                if h[i]
                else None,
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
        conditioned.append(
            {
                "state": names[i],
                "defined": bool(h[i]),
                "edges": [
                    {
                        "to": names[j],
                        "original_prob": str(original[i][j]),
                        "stopped_prob": str(p[i][j]),
                        "success_weight": str(h[j]),
                        "joint_success_mass": str(p[i][j] * h[j]),
                        "conditioned_prob": str(p[i][j] * h[j] / h[i])
                        if h[i]
                        else None,
                    }
                    for j in range(n)
                ],
                "row_sum": str(sum((p[i][j] * h[j] / h[i] for j in range(n)), F(0)))
                if h[i]
                else None,
            }
        )
    forecasts = []
    for root in range(n):
        active = [F(i == root and root not in terminal) for i in range(n)]
        cs = F(root in good)
        cf = F(root in bad)
        history = []
        ns = cs
        nf = cf
        for k in range(data["horizon"] + 1):
            history.append(
                {
                    "step": k,
                    "active_mass": [str(v) for v in active],
                    "new_success": str(ns),
                    "new_failure": str(nf),
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
            nxt = [F(0) for _ in states]
            ns = nf = F(0)
            for i, mass in enumerate(active):
                for j, v in enumerate(p[i]):
                    if j in good:
                        ns += mass * v
                    elif j in bad:
                        nf += mass * v
                    else:
                        nxt[j] += mass * v
            active = nxt
            cs += ns
            cf += nf
        forecasts.append({"start": names[root], "rows": history})
    return {
        "schema": "absorblab-v1",
        "input": data,
        "limits": LIMITS[:],
        "original_matrix": encode(original),
        "stopped_matrix": encode(p),
        "support": {
            "rounds": rounds,
            "can_hit_terminal": [names[i] for i in range(n) if i in reached],
            "zero_terminal_states": [names[i] for i in range(n) if i not in reached],
            "paths": paths,
        },
        "components": comps,
        "linear_system": {
            "unknowns": [names[i] for i in unknown],
            "matrix": encode(a),
            "success_rhs": [str(v) for v in b1],
            "failure_rhs": [str(v) for v in b0],
            "inverse": encode(inv),
            "elimination": steps,
        },
        "states": rows,
        "conditioned": conditioned,
        "forecasts": forecasts,
    }
