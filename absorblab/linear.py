"""Exact Gauss-Jordan inverse, retaining each complete elementary stage."""

from fractions import Fraction as F


def encode(a):
    return [[str(v) for v in row] for row in a]


def invert(a):
    n = len(a)
    m = [list(row) + [F(i == j) for j in range(n)] for i, row in enumerate(a)]
    steps = []
    for k in range(n):
        before = encode(m)
        pivot = next((j for j in range(k, n) if m[j][k]), None)
        if pivot is None:
            raise ValueError("singular restricted matrix")
        m[k], m[pivot] = m[pivot], m[k]
        divisor = m[k][k]
        m[k] = [v / divisor for v in m[k]]
        normalized = encode(m)
        factors = [m[i][k] if i != k else F(0) for i in range(n)]
        for i in range(n):
            if i != k:
                m[i] = [v - factors[i] * u for v, u in zip(m[i], m[k])]
        steps.append(
            {
                "column": k,
                "swap_row": pivot,
                "before": before,
                "divisor": str(divisor),
                "normalized": normalized,
                "factors": [str(v) for v in factors],
                "after": encode(m),
            }
        )
    return [row[n:] for row in m], steps


def matvec(a, x):
    return [sum((u * v for u, v in zip(row, x)), F(0)) for row in a]
