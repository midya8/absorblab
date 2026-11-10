"""Exact rank-one first-hit response and success-conditioned path traffic."""
from fractions import Fraction as F
from .response_input import validate, LIMITS
from .linear import invert, encode, matvec


def _solve(raw, good, bad):
    n = len(raw)
    terminal = good | bad
    p = [[F(i == j) for j in range(n)] if i in terminal else row[:] for i, row in enumerate(raw)]
    reached = set(terminal)
    while True:
        after = reached | {i for i in range(n) if any(p[i][j] for j in reached)}
        if after == reached:
            break
        reached = after
    us = [i for i in range(n) if i in reached - terminal]
    a = [[F(i == j) - p[i][j] for j in us] for i in us]
    inverse, _ = invert(a)
    h, f = [F(i in good) for i in range(n)], [F(i in bad) for i in range(n)]
    for target, boundary in ((h, good), (f, bad)):
        rhs = [sum((p[i][j] for j in boundary), F(0)) for i in us]
        for i, value in zip(us, matvec(inverse, rhs)):
            target[i] = value
    visits = [[F(0) for _ in range(n)] for _ in range(n)]
    for r, i in enumerate(us):
        for c, j in enumerate(us):
            visits[i][j] = inverse[r][c]
    return p, us, a, inverse, h, f, visits


def _snapshot(raw, good, bad):
    p, us, a, inverse, h, f, visits = _solve(raw, good, bad)
    n = len(p)
    roots = []
    for r in range(n):
        conditional = None
        if h[r]:
            cv = [visits[r][j] * h[j] / h[r] for j in range(n)]
            edges = [[visits[r][j] * p[j][k] * h[k] / h[r] for k in range(n)] for j in range(n)]
            outgoing = [sum(row, F(0)) for row in edges]
            incoming = [sum((edges[j][k] for j in range(n)), F(0)) for k in range(n)]
            conditional = {
                "visits": [str(v) for v in cv], "edges": encode(edges),
                "outgoing": [str(v) for v in outgoing], "incoming": [str(v) for v in incoming],
                "mean_time": str(sum(cv, F(0))),
                "total_edges": str(sum(outgoing, F(0))),
                "success_arrivals": str(sum((incoming[j] for j in good), F(0))),
            }
        roots.append({"success": str(h[r]), "failure": str(f[r]), "never": str(1 - h[r] - f[r]),
                      "restricted_visits": [str(v) for v in visits[r]], "conditional": conditional})
    return {"stopped_matrix": encode(p), "transient_indices": us, "matrix": encode(a),
            "inverse": encode(inverse), "roots": roots}


def _residuals(p, row, donor, receiver, numerator, denominator, boundary):
    # Coefficients are in delta=t-anchor. Multiplying the harmonic equation
    # by the common denominator yields a quadratic polynomial identity.
    n = len(p)
    out = []
    for i in range(n):
        if i in boundary:
            out.append(["0", "0", "0"])
            continue
        values = [numerator[i][0], numerator[i][1], F(0)]
        for j in range(n):
            slope = F(i == row) * (F(j == receiver) - F(j == donor))
            values[0] -= p[i][j] * numerator[j][0]
            values[1] -= p[i][j] * numerator[j][1] + slope * numerator[j][0]
            values[2] -= slope * numerator[j][1]
        out.append([str(v) for v in values])
    return out


def analyze_response(request):
    data = validate(request)
    chain = data["chain"]
    names = [s["name"] for s in chain["states"]]
    n = len(names)
    row, donor, receiver = [names.index(data[k]) for k in ("row", "donor", "receiver")]
    good, bad = [{names.index(v) for v in chain[k]} for k in ("success", "failure")]
    raw = [[F(0) for _ in names] for _ in names]
    for i, state in enumerate(chain["states"]):
        for edge in state["transitions"]:
            raw[i][names.index(edge["to"])] = F(edge["prob"])
    lower, upper = -raw[row][receiver], raw[row][donor]
    anchor = (lower + upper) / 2

    def at(t):
        changed = [v[:] for v in raw]
        changed[row][donor] -= t
        changed[row][receiver] += t
        return changed

    p, us, a, inverse, h, f, visits = _solve(at(anchor), good, bad)
    column = [visits[r][row] for r in range(n)]
    kappa = column[receiver] - column[donor]
    denominator = [F(1), -kappa]
    numerators = {}
    for key, values in (("success", h), ("failure", f)):
        contrast = values[receiver] - values[donor]
        numerators[key] = [[values[r], column[r] * contrast - values[r] * kappa] for r in range(n)]
    numerators["never"] = [[denominator[c] - numerators["success"][r][c] - numerators["failure"][r][c] for c in range(2)] for r in range(n)]
    curves = []
    for r in range(n):
        curves.append({"state": names[r], **{key: [str(v) for v in nums[r]] for key, nums in numerators.items()}})
    residuals = {key: _residuals(p, row, donor, receiver, numerators[key], denominator, good | bad)
                 for key in ("success", "failure")}
    if any(F(x) for records in residuals.values() for record in records for x in record):
        raise ArithmeticError("nonzero harmonic polynomial residual")
    samples = sorted({lower + (upper - lower) * F(i, 12) for i in range(13)} | {F(0), anchor, F(data["at"])})
    snapshots = []
    for t in samples:
        delta = t - anchor
        den = denominator[0] + delta * denominator[1]
        concrete = _snapshot(at(t), good, bad)
        derivatives = None
        if lower < t < upper:
            if not den:
                raise ArithmeticError("singular interior denominator")
            derivatives = []
            for r in range(n):
                entry = {}
                for key in ("success", "failure", "never"):
                    b0, b1 = numerators[key][r]
                    determinant = b1 - b0 * denominator[1]
                    entry[key] = {"first": str(determinant / den ** 2),
                                  "second": str(-2 * determinant * denominator[1] / den ** 3)}
                    predicted = (b0 + delta * b1) / den
                    if predicted != F(concrete["roots"][r][key]):
                        raise ArithmeticError("interior response differs from direct solve")
                derivatives.append(entry)
        snapshots.append({"transfer": str(t), "interior": lower < t < upper, "derivatives": derivatives, **concrete})
    endpoints = []
    for t in (lower, upper):
        delta = t - anchor
        den = 1 + delta * denominator[1]
        actual = next(v for v in snapshots if F(v["transfer"]) == t)
        limits = []
        for r in range(n):
            entry = {}
            for key in ("success", "failure", "never"):
                b0, b1 = numerators[key][r]
                num = b0 + delta * b1
                if den:
                    value = num / den
                elif num == 0 and denominator[1]:
                    value = b1 / denominator[1]
                else:
                    raise ArithmeticError("unbounded probability limit")
                entry[key] = str(value)
            limits.append(entry)
        endpoints.append({"transfer": str(t), "interior_limits": limits,
                          "discontinuous": [any(F(limits[r][key]) != F(actual["roots"][r][key]) for key in limits[r]) for r in range(n)]})
    return {"schema": "absorblab-response-v1", "input": data, "limits": LIMITS[:], "names": names,
            "domain": {"lower": str(lower), "upper": str(upper), "anchor": str(anchor)},
            "anchor": {"stopped_matrix": encode(p), "transient_indices": us, "matrix": encode(a), "inverse": encode(inverse),
                       "row_visit_column": [str(v) for v in column], "feedback": str(kappa)},
            "response": {"denominator": [str(v) for v in denominator], "curves": curves, "harmonic_residuals": residuals},
            "samples": snapshots, "endpoints": endpoints}
