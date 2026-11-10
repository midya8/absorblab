"""Optional exact SymPy rational-matrix reference, not a runtime dependency."""

import itertools
import json
import sys
from pathlib import Path
import sympy as S

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from absorblab.lumping import analyze_lumping
from tools.lumping_cases import controls, exhaustive, seeded

counts = {
    "requests": 0,
    "partitions": 0,
    "matrix_power_checks": 0,
    "intertwining_cells": 0,
}
for data in list(exhaustive()) + seeded() + [c["input"] for c in controls()]:
    r = analyze_lumping(data)
    p = S.Matrix([[S.Rational(v) for v in row] for row in r["original_matrix"]])
    n = p.rows
    k = len(r["final_blocks"])
    q = S.Matrix([[S.Rational(v) for v in row] for row in r["quotient_matrix"]])
    c = S.Matrix(n, k, lambda i, j: int(i in r["final_blocks"][j]))
    assert p * c == c * q
    counts["intertwining_cells"] += n * k
    for a in r["partition_atlas"]:
        bs = a["blocks"]
        indicator = S.Matrix(n, len(bs), lambda i, j: int(i in bs[j]))
        mass = p * indicator
        actual = [[str(mass[i, j]) for j in range(len(bs))] for i in range(n)]
        assert actual == a["masses"]
        stable = all(
            all(mass[i, j] == mass[t, j] for j in range(len(bs)))
            for b in bs
            for i, t in itertools.combinations(b, 2)
        )
        assert stable == a["stable"]
        counts["partitions"] += 1
    for step in range(data["chain"]["horizon"] + 1):
        full = p**step
        reduced = q**step
        assert full * c == c * reduced
        counts["matrix_power_checks"] += 1
        for f in r["forecasts"]:
            i = f["start"]
            row = f["rows"][step]
            assert row["original_states"] == list(map(str, full.row(i)))
            assert row["quotient_blocks"] == list(
                map(str, reduced.row(r["state_blocks"][i]))
            )
    counts["requests"] += 1
print(json.dumps({"sympy_version": S.__version__, **counts}))
