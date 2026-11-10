"""Original synthetic row-transfer controls, not imported benchmarks."""
from fractions import Fraction as F


def request(rows, good, bad, row=0, donor=0, receiver=1, at="0", horizon=6):
    names = ["s" + str(i) for i in range(len(rows))]
    chain = {"states": [{"name": names[i], "transitions": [{"to": names[j], "prob": str(F(v))} for j, v in enumerate(r) if F(v)]} for i, r in enumerate(rows)],
             "success": [names[i] for i in good], "failure": [names[i] for i in bad], "horizon": horizon}
    return {"chain": chain, "row": names[row], "donor": names[donor], "receiver": names[receiver], "at": at}


def controls():
    return [
        ("An exit can disappear", request([["1/2", "1/2"], [0, 1]], [1], [])),
        ("Retry versus success", request([["1/2", "1/4", "1/4"], [1, 0, 0], [1, 0, 0]], [1], [2])),
        ("Open a previously absent exit", request([[1, 0], [0, 1]], [1], [], receiver=1)),
        ("A donor can start absent", request([[0, 1], [0, 1]], [1], [], donor=0, receiver=1)),
        ("No terminal is reachable", request([["1/2", "1/2", 0], [1, 0, 0], [0, 0, 1]], [2], [])),
        ("No success states", request([["1/2", "1/2"], [0, 1]], [], [1])),
        ("No terminal states", request([["1/2", "1/2"], [1, 0]], [], [])),
        ("Traffic through a detour", request([[0, "1/2", "1/2", 0], [0, "1/2", 0, "1/2"], [0, 0, 1, 0], [1, 0, 0, 0]], [3], [2], donor=1, receiver=2)),
        ("An unreachable varied row", request([[0, 0, 1, 0], [0, "1/2", "1/2", 0], [0, 0, 1, 0], [0, 0, 0, 1]], [2], [3], row=1, donor=1, receiver=2)),
        ("Tiny exit, long successful traffic", request([["999999/1000000", "1/1000000"], [0, 1]], [1], [])),
        ("Two success destinations", request([["1/2", "1/4", "1/4"], [1, 0, 0], [1, 0, 0]], [1, 2], [], donor=1, receiver=2)),
        ("Nonlocal destination contrast", request([[0, "1/2", "1/2", 0], [0, "1/2", 0, "1/2"], [0, "1/4", "3/4", 0], [0, 0, 0, 1]], [3], [], donor=1, receiver=2)),
    ]


def differential_cases():
    import itertools
    import random
    out = [value for _, value in controls()]
    supports = [(1, 0), (0, 1), (F(1, 2), F(1, 2))]
    for rows in itertools.product(supports, repeat=2):
        for status in itertools.product(range(3), repeat=2):
            for row in range(2):
                if status[row] == 0:
                    out.append(request(rows, [i for i, s in enumerate(status) if s == 1], [i for i, s in enumerate(status) if s == 2], row=row))
    rng = random.Random(62719)
    for _ in range(80):
        n = rng.randrange(2, 7)
        rows = []
        for __ in range(n):
            weights = [rng.randrange(4) for ___ in range(n)]
            if not any(weights):
                weights[rng.randrange(n)] = 1
            rows.append([F(v, sum(weights)) for v in weights])
        varied = rng.randrange(n)
        donor = next(i for i, v in enumerate(rows[varied]) if v)
        receiver = rng.choice([i for i in range(n) if i != donor])
        status = [rng.randrange(3) if i != varied else 0 for i in range(n)]
        out.append(request(rows, [i for i, s in enumerate(status) if s == 1], [i for i, s in enumerate(status) if s == 2], varied, donor, receiver))
    return out
