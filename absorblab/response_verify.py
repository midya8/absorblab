"""Independent simple-path/cofactor/conditioned-chain replay.

No import from the response generator or Gauss-Jordan implementation.
The response coefficients use Cramer's determinants at two algebraic points,
not the generator's rank-one inverse formula. Conditional traffic is solved
in the h-transformed chain, not obtained by rescaling the raw visit matrix.
"""
from fractions import Fraction as F
from .input import equal
from .response_input import validate, LIMITS
from .verify import _det, _inverse


def _enc(matrix):
    return [[str(v) for v in row] for row in matrix]


def _direct(raw, good, bad):
    n = len(raw)
    terminals = good | bad
    p = [[F(i == j) if i in terminals else raw[i][j] for j in range(n)] for i in range(n)]
    us = []
    for root in range(n):
        def reaches(i, visited):
            if i in terminals:
                return True
            return any(p[i][j] and j not in visited and reaches(j, visited | {j}) for j in range(n))
        if root not in terminals and reaches(root, {root}):
            us.append(root)
    a = [[F(i == j) - p[i][j] for j in us] for i in us]
    inverse = _inverse(a)
    vectors = []
    for terminal_set in (good, bad):
        rhs = [sum((p[i][j] for j in terminal_set), F(0)) for i in us]
        values = [F(i in terminal_set) for i in range(n)]
        for r, i in enumerate(us):
            values[i] = sum((inverse[r][c] * rhs[c] for c in range(len(us))), F(0))
        vectors.append(values)
    h, f = vectors
    eligible = [i for i in range(n) if i not in terminals and h[i]]
    conditioned_matrix = [[F(i == j) - p[i][j] * h[j] / h[i] for j in eligible] for i in eligible]
    conditioned_inverse = _inverse(conditioned_matrix)
    roots = []
    for r in range(n):
        visits = [F(0) for _ in range(n)]
        if r in us:
            for c, j in enumerate(us):
                visits[j] = inverse[us.index(r)][c]
        conditional = None
        if h[r]:
            cv = [F(0) for _ in range(n)]
            if r in eligible:
                for c, j in enumerate(eligible):
                    cv[j] = conditioned_inverse[eligible.index(r)][c]
            edges = [[cv[j] * p[j][k] * h[k] / h[j] if j in eligible else F(0) for k in range(n)] for j in range(n)]
            outgoing = [sum(edges[j], F(0)) for j in range(n)]
            incoming = [sum((edges[j][k] for j in range(n)), F(0)) for k in range(n)]
            for j in eligible:
                if outgoing[j] != cv[j] or outgoing[j] - incoming[j] != F(j == r):
                    raise ValueError("conditioned traffic balance")
            if sum((incoming[j] for j in good), F(0)) != F(r not in terminals):
                raise ValueError("success traffic arrival")
            conditional = {"visits": [str(v) for v in cv], "edges": _enc(edges),
                           "outgoing": [str(v) for v in outgoing], "incoming": [str(v) for v in incoming],
                           "mean_time": str(sum(cv, F(0))), "total_edges": str(sum(outgoing, F(0))),
                           "success_arrivals": str(sum((incoming[j] for j in good), F(0)))}
        if not (0 <= h[r] <= 1 and 0 <= f[r] <= 1 and h[r] + f[r] <= 1):
            raise ValueError("first-hit probability bounds")
        roots.append({"success": str(h[r]), "failure": str(f[r]), "never": str(1 - h[r] - f[r]),
                      "restricted_visits": [str(v) for v in visits], "conditional": conditional})
    return {"stopped_matrix": _enc(p), "transient_indices": us, "matrix": _enc(a), "inverse": _enc(inverse), "roots": roots}


def replay_response(request):
    data = validate(request)
    chain = data["chain"]
    names = [s["name"] for s in chain["states"]]
    n = len(names)
    row, donor, receiver = [names.index(data[k]) for k in ("row", "donor", "receiver")]
    good, bad = [{names.index(v) for v in chain[key]} for key in ("success", "failure")]
    raw = [[sum((F(e["prob"]) for e in s["transitions"] if e["to"] == name), F(0)) for name in names] for s in chain["states"]]
    lower, upper = -raw[row][receiver], raw[row][donor]
    anchor = (lower + upper) / 2

    def at(t):
        return [[raw[i][j] + (F(j == receiver) - F(j == donor)) * t if i == row else raw[i][j] for j in range(n)] for i in range(n)]

    concrete_anchor = _direct(at(anchor), good, bad)
    us = concrete_anchor["transient_indices"]

    def system(delta, terminal_set):
        p = at(anchor + delta)
        a = [[F(i == j) - p[i][j] for j in us] for i in us]
        b = [sum((p[i][j] for j in terminal_set), F(0)) for i in us]
        return a, b

    a0, _ = system(F(0), good)
    determinant = _det(a0)
    a1, _ = system(F(1), good)
    denominator = [F(1), (_det(a1) - determinant) / determinant]
    numerator = {}
    for key, terminal_set in (("success", good), ("failure", bad)):
        values = [[F(i in terminal_set), F(i in terminal_set) * denominator[1]] for i in range(n)]
        for c, i in enumerate(us):
            numbers = []
            for delta in (F(0), F(1)):
                a, b = system(delta, terminal_set)
                replaced = [[b[r] if j == c else a[r][j] for j in range(len(us))] for r in range(len(us))]
                numbers.append(_det(replaced) / determinant)
            values[i] = [numbers[0], numbers[1] - numbers[0]]
        numerator[key] = values
    numerator["never"] = [[denominator[j] - numerator["success"][i][j] - numerator["failure"][i][j] for j in range(2)] for i in range(n)]
    curves = [{"state": name, **{key: [str(x) for x in values[i]] for key, values in numerator.items()}} for i, name in enumerate(names)]
    # Direct determinant polynomial solutions establish these identities for
    # the full interval; a finite sample list is only additional evidence.
    residuals = {key: [["0", "0", "0"] for _ in names] for key in ("success", "failure")}
    samples = []
    transfers = {lower + (upper - lower) * F(k, 12) for k in range(13)}
    transfers.update((F(0), anchor, F(data["at"])))
    for t in sorted(transfers):
        delta = t - anchor
        den = 1 + delta * denominator[1]
        derivatives = None
        direct = _direct(at(t), good, bad)
        if lower < t < upper:
            derivatives = []
            for i in range(n):
                record = {}
                for key in ("success", "failure", "never"):
                    c0, c1 = numerator[key][i]
                    num = c0 + delta * c1
                    cross = c1 * den - num * denominator[1]
                    if num / den != F(direct["roots"][i][key]):
                        raise ValueError("determinant curve point mismatch")
                    record[key] = {"first": str(cross / den ** 2), "second": str(-2 * denominator[1] * cross / den ** 3)}
                derivatives.append(record)
        samples.append({"transfer": str(t), "interior": lower < t < upper, "derivatives": derivatives, **direct})
    endpoints = []
    for t in (lower, upper):
        delta = t - anchor
        den = 1 + delta * denominator[1]
        actual = next(v for v in samples if F(v["transfer"]) == t)
        limits = []
        for i in range(n):
            values = {}
            for key in ("success", "failure", "never"):
                c0, c1 = numerator[key][i]
                num = c0 + delta * c1
                if not den and num:
                    raise ValueError("unbounded reachability limit")
                values[key] = str(num / den if den else c1 / denominator[1])
            limits.append(values)
        endpoints.append({"transfer": str(t), "interior_limits": limits,
                          "discontinuous": [any(limits[i][key] != actual["roots"][i][key] for key in limits[i]) for i in range(n)]})
    visit_column = [F(0) for _ in names]
    if row in us:
        for i in us:
            visit_column[i] = F(concrete_anchor["inverse"][us.index(i)][us.index(row)])
    return {"schema": "absorblab-response-v1", "input": data, "limits": LIMITS[:], "names": names,
            "domain": {"lower": str(lower), "upper": str(upper), "anchor": str(anchor)},
            "anchor": {key: concrete_anchor[key] for key in ("stopped_matrix", "transient_indices", "matrix", "inverse")} | {
                "row_visit_column": [str(v) for v in visit_column], "feedback": str(-denominator[1])},
            "response": {"denominator": [str(v) for v in denominator], "curves": curves, "harmonic_residuals": residuals},
            "samples": samples, "endpoints": endpoints}


def verify_response(report):
    if type(report) is not dict or "input" not in report:
        raise ValueError("response report requires input")
    equal(replay_response(report["input"]), report)
    return True
