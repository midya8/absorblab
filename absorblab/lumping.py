"""Exact finite raw-chain probabilistic bisimulation refinement evidence."""

from fractions import Fraction as F
from itertools import combinations
from .lumping_input import validate, LIMITS
from .core import analyze as first_hit


def encode(matrix):
    return [[str(x) for x in row] for row in matrix]


def partitions(n):
    """Canonical restricted-growth words, ordered lexicographically."""

    def go(word):
        if len(word) == n:
            yield [
                [i for i, x in enumerate(word) if x == c] for c in range(max(word) + 1)
            ]
            return
        for c in range(max(word) + 2):
            yield from go(word + [c])

    yield from go([0])


def canonical(blocks):
    return sorted([sorted(b) for b in blocks], key=lambda b: b[0])


def refines(a, b):
    return all(any(set(x) <= set(y) for y in b) for x in a)


def analyze_lumping(raw):
    data = validate(raw)
    chain = data["chain"]
    names = [s["name"] for s in chain["states"]]
    n = len(names)
    ix = {s: i for i, s in enumerate(names)}
    p = [[F(0) for _ in names] for _ in names]
    for i, s in enumerate(chain["states"]):
        for t in s["transitions"]:
            p[i][ix[t["to"]]] = F(t["prob"])
    status = [
        (
            "success"
            if s in chain["success"]
            else "failure" if s in chain["failure"] else "nonterminal"
        )
        for s in names
    ]
    colors = [(o, s) for o, s in zip(data["observations"], status)]
    initial = canonical(
        [[j for j in range(n) if colors[j] == c] for c in dict.fromkeys(colors)]
    )

    def masses(blocks):
        return [[sum((p[i][j] for j in b), F(0)) for b in blocks] for i in range(n)]

    def evidence(blocks):
        mass = masses(blocks)
        pairs = []
        for b in blocks:
            for a, c in combinations(b, 2):
                diffs = [
                    {
                        "block": j,
                        "members": t[:],
                        "left_mass": str(mass[a][j]),
                        "right_mass": str(mass[c][j]),
                    }
                    for j, t in enumerate(blocks)
                    if mass[a][j] != mass[c][j]
                ]
                pairs.append(
                    {
                        "left": a,
                        "right": c,
                        "same_observation": colors[a] == colors[c],
                        "unequal_blocks": diffs,
                    }
                )
        stable = all(not x["unequal_blocks"] for x in pairs)
        respect = all(x["same_observation"] for x in pairs)
        return mass, pairs, stable, respect

    rounds = []
    blocks = initial
    while True:
        mass, pairs, stable, respect = evidence(blocks)
        groups = []
        for b in blocks:
            seen = {}
            for i in b:
                seen.setdefault(tuple(mass[i]), []).append(i)
            groups.extend(seen.values())
        after = canonical(groups)
        rounds.append(
            {
                "round": len(rounds),
                "blocks": blocks,
                "masses": encode(mass),
                "pairs": pairs,
                "next_blocks": after,
                "fixed": after == blocks,
            }
        )
        if after == blocks:
            break
        blocks = after
    final = blocks
    state_block = [next(k for k, b in enumerate(final) if i in b) for i in range(n)]
    mass = masses(final)
    q = [mass[b[0]][:] for b in final]
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
    for part in partitions(n):
        m, ps, stable, respect = evidence(part)
        atlas.append(
            {
                "blocks": part,
                "masses": encode(m),
                "respects_observations": respect,
                "stable": stable,
                "allowed": stable and respect,
                "first_observation_conflict": next(
                    (
                        {"left": x["left"], "right": x["right"]}
                        for x in ps
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
                        for x in ps
                        if x["unequal_blocks"]
                    ),
                    None,
                ),
                "refines_final": refines(part, final),
            }
        )
    assert all(x["refines_final"] for x in atlas if x["allowed"])
    # All-step identity P*C=C*Q is recorded entry by entry, not inferred from a finite horizon.
    identity = [
        {
            "state": i,
            "source_block": state_block[i],
            "destination_block": j,
            "original_mass": str(mass[i][j]),
            "quotient_prob": str(q[state_block[i]][j]),
            "equal": mass[i][j] == q[state_block[i]][j],
        }
        for i in range(n)
        for j in range(len(final))
    ]
    forecasts = []
    for root in range(n):
        original = [F(i == root) for i in range(n)]
        reduced = [F(k == state_block[root]) for k in range(len(final))]
        rows = []
        for step in range(chain["horizon"] + 1):
            agg = [sum((original[i] for i in b), F(0)) for b in final]
            rows.append(
                {
                    "step": step,
                    "original_states": list(map(str, original)),
                    "original_blocks": list(map(str, agg)),
                    "quotient_blocks": list(map(str, reduced)),
                    "equal": agg == reduced,
                }
            )
            original = [
                sum((original[i] * p[i][j] for i in range(n)), F(0)) for j in range(n)
            ]
            reduced = [
                sum((reduced[i] * q[i][j] for i in range(len(final))), F(0))
                for j in range(len(final))
            ]
        forecasts.append(
            {"start": root, "quotient_start": state_block[root], "rows": rows}
        )
    old = first_hit(chain)
    small = first_hit(quotient)
    hit = []
    for i in range(n):
        a = {k: v for k, v in old["states"][i].items() if k != "name"}
        b = {k: v for k, v in small["states"][state_block[i]].items() if k != "name"}
        assert a == b
        hit.append(
            {
                "state": i,
                "block": state_block[i],
                "original": a,
                "quotient": b,
                "equal": a == b,
            }
        )
    witnesses = []
    for a, b in combinations(range(n), 2):
        if colors[a] != colors[b]:
            w = {
                "kind": "observation",
                "left": a,
                "right": b,
                "left_color": list(colors[a]),
                "right_color": list(colors[b]),
            }
        elif state_block[a] == state_block[b]:
            w = {"kind": "equivalent", "left": a, "right": b, "block": state_block[a]}
        else:
            r = next(
                r
                for r in rounds
                if any(a in t and b in t for t in r["blocks"])
                and not any(a in t and b in t for t in r["next_blocks"])
            )
            c = next(
                i
                for i, (x, y) in enumerate(zip(r["masses"][a], r["masses"][b]))
                if x != y
            )
            w = {
                "kind": "split",
                "left": a,
                "right": b,
                "round": r["round"],
                "destination_block": c,
                "destination_members": r["blocks"][c],
                "left_mass": r["masses"][a][c],
                "right_mass": r["masses"][b][c],
            }
        witnesses.append(w)
    return {
        "schema": "absorblab-lumping-v1",
        "input": data,
        "colors": [list(c) for c in colors],
        "original_matrix": encode(p),
        "initial_blocks": initial,
        "rounds": rounds,
        "final_blocks": final,
        "state_blocks": state_block,
        "quotient_chain": quotient,
        "quotient_observations": [data["observations"][b[0]] for b in final],
        "quotient_matrix": encode(q),
        "intertwining": identity,
        "partition_atlas": atlas,
        "pair_witnesses": witnesses,
        "forecasts": forecasts,
        "first_hit": hit,
        "limits": LIMITS[:],
    }
