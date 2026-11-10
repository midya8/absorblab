"""Independent all-set-partition oracle and direct pair-equivalence replay.

No import of lumping.py, signature grouping, restricted-growth generator or
first-hit Gauss-Jordan code. Uses the existing independent cofactor/path checker.
"""

from fractions import Fraction as F
from itertools import combinations
from .lumping_input import validate, LIMITS
from .input import equal
from .verify import replay as first_hit_replay


def all_partitions(universe):
    if not universe:
        yield []
        return
    first = min(universe)
    rest = sorted(universe - {first})
    for mask in range(2 ** len(rest)):
        head = {first} | {a for i, a in enumerate(rest) if mask >> i & 1}
        for tail in all_partitions(universe - head):
            yield [sorted(head)] + tail


def expected(raw):
    data = validate(raw)
    chain = data["chain"]
    names = [x["name"] for x in chain["states"]]
    n = len(names)
    ids = set(range(n))
    p = [
        [
            sum(
                (
                    F(t["prob"])
                    for t in chain["states"][i]["transitions"]
                    if t["to"] == names[j]
                ),
                F(0),
            )
            for j in range(n)
        ]
        for i in range(n)
    ]
    status = [
        (
            "success"
            if x in chain["success"]
            else "failure" if x in chain["failure"] else "nonterminal"
        )
        for x in names
    ]
    colors = list(zip(data["observations"], status))
    parts = list(all_partitions(ids))
    word = lambda part: tuple(
        next(k for k, b in enumerate(part) if i in b) for i in range(n)
    )
    parts.sort(key=word)

    def sums(part):
        return [[sum((p[i][j] for j in b), F(0)) for b in part] for i in range(n)]

    def details(part):
        matrix = sums(part)
        pairs = []
        for b in part:
            for i, j in combinations(b, 2):
                pairs.append(
                    {
                        "left": i,
                        "right": j,
                        "same_observation": colors[i] == colors[j],
                        "unequal_blocks": [
                            {
                                "block": k,
                                "members": xs[:],
                                "left_mass": str(matrix[i][k]),
                                "right_mass": str(matrix[j][k]),
                            }
                            for k, xs in enumerate(part)
                            if matrix[i][k] != matrix[j][k]
                        ],
                    }
                )
        return matrix, pairs

    def finer(part, target):
        return all(
            all(any(i in b and j in b for b in target) for i in a for j in a)
            for a in part
        )

    def admissible(part):
        _, pairs = details(part)
        return all(x["same_observation"] and not x["unequal_blocks"] for x in pairs)

    allowed = [part for part in parts if admissible(part)]
    greatest = [
        part for part in allowed if all(finer(other, part) for other in allowed)
    ]
    assert len(greatest) == 1
    final = greatest[0]
    initial = next(
        part
        for part in parts
        if all(
            any(i in b and j in b for b in part) == (colors[i] == colors[j])
            for i in ids
            for j in ids
        )
    )
    enc = lambda m: [[str(x) for x in row] for row in m]
    rounds = []
    current = initial
    while True:
        m, pairs = details(current)
        relation = {
            (i, j)
            for b in current
            for i in b
            for j in b
            if all(
                sum((p[i][k] for k in d), F(0)) == sum((p[j][k] for k in d), F(0))
                for d in current
            )
        }
        nxt = next(
            part
            for part in parts
            if all(
                any(i in b and j in b for b in part) == ((i, j) in relation)
                for i in ids
                for j in ids
            )
        )
        rounds.append(
            {
                "round": len(rounds),
                "blocks": current,
                "masses": enc(m),
                "pairs": pairs,
                "next_blocks": nxt,
                "fixed": nxt == current,
            }
        )
        if nxt == current:
            break
        current = nxt
    assert current == final
    state_blocks = list(word(final))
    m = sums(final)
    q = [m[min(b)] for b in final]
    qn = len(final)
    quotient = {
        "states": [
            {
                "name": "q" + str(k),
                "transitions": [
                    {"to": "q" + str(j), "prob": str(v)} for j, v in enumerate(row) if v
                ],
            }
            for k, row in enumerate(q)
        ],
        "success": [
            "q" + str(k) for k, b in enumerate(final) if status[b[0]] == "success"
        ],
        "failure": [
            "q" + str(k) for k, b in enumerate(final) if status[b[0]] == "failure"
        ],
        "horizon": chain["horizon"],
    }
    atlas = []
    for part in parts:
        matrix, pairs = details(part)
        stable = all(not x["unequal_blocks"] for x in pairs)
        respect = all(x["same_observation"] for x in pairs)
        atlas.append(
            {
                "blocks": part,
                "masses": enc(matrix),
                "respects_observations": respect,
                "stable": stable,
                "allowed": stable and respect,
                "first_observation_conflict": next(
                    (
                        {"left": x["left"], "right": x["right"]}
                        for x in pairs
                        if not x["same_observation"]
                    ),
                    None,
                ),
                "first_mass_conflict": next(
                    (
                        {
                            "left": x["left"],
                            "right": x["right"],
                            **x["unequal_blocks"][0],
                        }
                        for x in pairs
                        if x["unequal_blocks"]
                    ),
                    None,
                ),
                "refines_final": finer(part, final),
            }
        )
    identity = [
        {
            "state": i,
            "source_block": state_blocks[i],
            "destination_block": j,
            "original_mass": str(m[i][j]),
            "quotient_prob": str(q[state_blocks[i]][j]),
            "equal": m[i][j] == q[state_blocks[i]][j],
        }
        for i in range(n)
        for j in range(qn)
    ]

    def multiply(a, b):
        return [
            [
                sum((a[i][k] * b[k][j] for k in range(len(b))), F(0))
                for j in range(len(b[0]))
            ]
            for i in range(len(a))
        ]

    # Matrix powers computed once for every starting state, versus generator vectors.
    powers = [[[F(i == j) for j in range(n)] for i in range(n)]]
    smallpowers = [[[F(i == j) for j in range(qn)] for i in range(qn)]]
    for _ in range(chain["horizon"]):
        powers.append(multiply(powers[-1], p))
        smallpowers.append(multiply(smallpowers[-1], q))
    forecasts = []
    for root in range(n):
        rows = []
        for step, (big, small) in enumerate(zip(powers, smallpowers)):
            orig = big[root]
            agg = [sum((orig[i] for i in b), F(0)) for b in final]
            red = small[state_blocks[root]]
            rows.append(
                {
                    "step": step,
                    "original_states": list(map(str, orig)),
                    "original_blocks": list(map(str, agg)),
                    "quotient_blocks": list(map(str, red)),
                    "equal": agg == red,
                }
            )
        forecasts.append(
            {"start": root, "quotient_start": state_blocks[root], "rows": rows}
        )
    orig = first_hit_replay(chain)
    small = first_hit_replay(quotient)
    hit = []
    for i in range(n):
        a = {k: v for k, v in orig["states"][i].items() if k != "name"}
        b = {k: v for k, v in small["states"][state_blocks[i]].items() if k != "name"}
        assert a == b
        hit.append(
            {
                "state": i,
                "block": state_blocks[i],
                "original": a,
                "quotient": b,
                "equal": a == b,
            }
        )
    witnesses = []
    for i, j in combinations(range(n), 2):
        if colors[i] != colors[j]:
            w = {
                "kind": "observation",
                "left": i,
                "right": j,
                "left_color": list(colors[i]),
                "right_color": list(colors[j]),
            }
        elif state_blocks[i] == state_blocks[j]:
            w = {"kind": "equivalent", "left": i, "right": j, "block": state_blocks[i]}
        else:
            r = next(
                r
                for r in rounds
                if any(i in b and j in b for b in r["blocks"])
                and not any(i in b and j in b for b in r["next_blocks"])
            )
            c = next(
                k
                for k, (x, y) in enumerate(zip(r["masses"][i], r["masses"][j]))
                if x != y
            )
            w = {
                "kind": "split",
                "left": i,
                "right": j,
                "round": r["round"],
                "destination_block": c,
                "destination_members": r["blocks"][c],
                "left_mass": r["masses"][i][c],
                "right_mass": r["masses"][j][c],
            }
        witnesses.append(w)
    return {
        "schema": "absorblab-lumping-v1",
        "input": data,
        "colors": [list(c) for c in colors],
        "original_matrix": enc(p),
        "initial_blocks": initial,
        "rounds": rounds,
        "final_blocks": final,
        "state_blocks": state_blocks,
        "quotient_chain": quotient,
        "quotient_observations": [data["observations"][b[0]] for b in final],
        "quotient_matrix": enc(q),
        "intertwining": identity,
        "partition_atlas": atlas,
        "pair_witnesses": witnesses,
        "forecasts": forecasts,
        "first_hit": hit,
        "limits": LIMITS[:],
    }


def verify_lumping(report):
    if type(report) is not dict or "input" not in report:
        raise ValueError("missing lumping input")
    equal(expected(report["input"]), report)
    return True
