"""Original small chains, no copied source examples."""

from fractions import Fraction as F
import random


def request(matrix, observations, good=(), bad=(), horizon=5):
    names = ["s" + str(i) for i in range(len(matrix))]
    return {
        "chain": {
            "states": [
                {
                    "name": names[i],
                    "transitions": [
                        {"to": names[j], "prob": str(F(v))}
                        for j, v in enumerate(row)
                        if v
                    ],
                }
                for i, row in enumerate(matrix)
            ],
            "success": [names[i] for i in good],
            "failure": [names[i] for i in bad],
            "horizon": horizon,
        },
        "observations": list(observations),
    }


def controls():
    rows = [
        (
            "A split has consequences",
            "s0,s1,s5 have equal immediate goal probability. Splitting their successors forces s1 apart later; s0 and s5 still merge. No averaging is used.",
            [
                [0, 0, 1, 0, 0, 0],
                [0, 0, 0, 1, 0, 0],
                [0, 0, 0, 0, 1, 0],
                [0, 0, 0, F(1, 2), F(1, 2), 0],
                [0, 0, 0, 0, 1, 0],
                [0, 0, 1, 0, 0, 0],
            ],
            ["work"] * 4 + ["goal", "work"],
            [4],
            [],
        ),
        (
            "Equal blocks, different rows",
            "s0 and s2 have different individual successor rows but the same mass into every observed block. Comparing entire rows is unnecessarily strict.",
            [[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
            ["a", "b", "a", "b"],
            [],
            [],
        ),
        (
            "Exact, not almost equal",
            "A rational difference of one millionth still splits states; numerical tolerance would change the equivalence.",
            [[0, 0, 1], [F(1, 1000000), 0, F(999999, 1000000)], [0, 0, 1]],
            ["work", "work", "goal"],
            [2],
            [],
        ),
        (
            "Terminal status is observable",
            "Success and failure are never merged even if the supplied tag is identical.",
            [[1, 0], [0, 1]],
            ["same", "same"],
            [0],
            [1],
        ),
        (
            "Outgoing terminal edges still count",
            "Both initial success states have identical first-hit records. Raw-chain equivalence is stronger and can split them because their outgoing transitions differ.",
            [[0, 0, 1], [0, 1, 0], [0, 0, 1]],
            ["same"] * 3,
            [0, 1],
            [],
        ),
        (
            "One unlabeled block is trivial",
            "With one tag and no terminal sets the all-state partition is stable, whatever the rows. Observations determine what must be preserved.",
            [[0, 1, 0], [F(1, 2), 0, F(1, 2)], [0, 0, 1]],
            ["same"] * 3,
            [],
            [],
        ),
        (
            "An absorbing success",
            "A one-state quotient and zero arrival time are valid, not missing evidence.",
            [[1]],
            ["goal"],
            [0],
            [],
        ),
        (
            "Closed nonterminal class",
            "Never reaching a terminal remains probability one after quotienting.",
            [[0, 1], [1, 0]],
            ["work"] * 2,
            [],
            [],
        ),
        (
            "Success and failure branches",
            "Equivalent starts share both hitting probabilities and conditional moments.",
            [
                [0, 0, F(1, 3), F(2, 3)],
                [0, 0, F(1, 3), F(2, 3)],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ],
            ["work", "work", "end", "end"],
            [2],
            [3],
        ),
        (
            "A zero-horizon audit",
            "The structural criterion is still checked at horizon zero. A finite display horizon does not establish lumpability.",
            [[0, 1], [0, 1]],
            ["same", "goal"],
            [1],
            [],
        ),
        (
            "Noncontiguous twins",
            "Equivalent indices need not form contiguous runs. Every set partition, not just interval partitions, is checked.",
            [[0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [1, 0, 0, 0]],
            ["a", "b", "a", "b"],
            [],
            [],
        ),
        (
            "All observations distinct",
            "No merge is allowed when every observation differs, even for identical probability rows.",
            [[F(1, 2), F(1, 2)], [F(1, 2), F(1, 2)]],
            ["first", "second"],
            [],
            [],
        ),
    ]
    out = [
        {
            "name": name,
            "why": why,
            "input": request(m, o, g, b, 0 if name == "A zero-horizon audit" else 5),
        }
        for name, why, m, o, g, b in rows
    ]
    return out


def seeded(count=80):
    rng = random.Random(91073)
    out = []
    for _ in range(count):
        n = rng.randrange(1, 7)
        rows = []
        for i in range(n):
            weights = [rng.randrange(4) for _ in range(n)]
            if not sum(weights):
                weights[i] = 1
            rows.append([F(v, sum(weights)) for v in weights])
        status = [rng.randrange(4) for _ in range(n)]
        out.append(
            request(
                rows,
                ["c" + str(rng.randrange(2)) for _ in range(n)],
                [i for i, s in enumerate(status) if s == 1],
                [i for i, s in enumerate(status) if s == 2],
                rng.randrange(5),
            )
        )
    return out


def exhaustive():
    from itertools import product

    # Every two-state row over {0,1/2,1}, every equality pattern of tags,
    # and every disjoint success/failure/nonterminal status assignment.
    for n in [1, 2]:
        rows = [
            [F(v, 2) for v in r] for r in product(range(3), repeat=n) if sum(r) == 2
        ]
        for matrix in product(rows, repeat=n):
            for obs in ([["same"]] if n == 1 else [["same", "same"], ["a", "b"]]):
                for statuses in product(range(3), repeat=n):
                    yield request(
                        matrix,
                        obs,
                        [i for i, s in enumerate(statuses) if s == 1],
                        [i for i, s in enumerate(statuses) if s == 2],
                        3,
                    )
    # Every deterministic three-state transition map, all five observation
    # equivalence patterns, both no terminals and a supplied goal.
    for targets in product(range(3), repeat=3):
        matrix = [[int(j == t) for j in range(3)] for t in targets]
        for obs in [
            ["a", "a", "a"],
            ["a", "a", "b"],
            ["a", "b", "a"],
            ["a", "b", "b"],
            ["a", "b", "c"],
        ]:
            for good in [[], [2]]:
                yield request(matrix, obs, good, [], 3)


if __name__ == "__main__":
    from pathlib import Path
    import json

    Path("docs/lumping-controls.json").write_text(
        json.dumps(controls(), indent=2) + "\n"
    )
    Path("examples/lumping.json").write_text(
        json.dumps(controls()[0]["input"], indent=2) + "\n"
    )
