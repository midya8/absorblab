from pathlib import Path
import json


def chain(rows, success, failure, horizon=8):
    return {
        "states": [
            {"name": name, "transitions": [{"to": to, "prob": p} for to, p in ts]}
            for name, ts in rows
        ],
        "success": success,
        "failure": failure,
        "horizon": horizon,
    }


def controls():
    cs = []

    def add(id, title, why, rows, good, bad, horizon=8):
        cs.append(
            {
                "id": id,
                "title": title,
                "why": why,
                "input": chain(rows, good, bad, horizon),
            }
        )

    add(
        "global",
        "Conditioning looks beyond the next edge",
        "Original start choices are equal, but risky succeeds only 1/4 of the time. Conditional on eventual success, risky gets 1/5, direct goal 4/5. Mean time to any terminal is 3/2; mean given success is 6/5; unconditional stopped-success time is infinite.",
        [
            ("start", [("goal", "1/2"), ("risky", "1/2")]),
            ("risky", [("goal", "1/4"), ("fail", "3/4")]),
            ("goal", [("goal", "1")]),
            ("fail", [("fail", "1")]),
        ],
        ["goal"],
        ["fail"],
    )
    add(
        "retry",
        "Almost sure does not mean a bounded deadline",
        "Each retry has success probability 1/4. Eventual success is certain and the mean is 4, but every finite deadline still has a positive survival probability.",
        [("retry", [("retry", "3/4"), ("goal", "1/4")]), ("goal", [("goal", "1")])],
        ["goal"],
        [],
    )
    add(
        "competing",
        "Retries before either outcome",
        "At each step, retry with 1/2, succeed with 1/8 and fail with 3/8. Eventual success is 1/4; conditioned on success, waiting still has mean 2.",
        [
            ("retry", [("retry", "1/2"), ("goal", "1/8"), ("fail", "3/8")]),
            ("goal", [("goal", "1")]),
            ("fail", [("fail", "1")]),
        ],
        ["goal"],
        ["fail"],
    )
    add(
        "trap",
        "A nonterminal closed class is not absorption",
        "Start reaches success, failure or a two-state nonterminal recurrent class with equal probability. Success plus failure is only 2/3; the restricted inverse excludes the trap instead of choosing an arbitrary harmonic value.",
        [
            ("start", [("goal", "1/3"), ("fail", "1/3"), ("left", "1/3")]),
            ("left", [("right", "1")]),
            ("right", [("left", "1")]),
            ("goal", [("goal", "1")]),
            ("fail", [("fail", "1")]),
        ],
        ["goal"],
        ["fail"],
    )
    add(
        "terminal",
        "First hit ignores later outgoing rows",
        "Goal points to failure and failure points to goal in the supplied chain. Both stop at the first hit, so goal starts succeed in zero steps and failure starts cannot later succeed.",
        [
            ("start", [("goal", "1")]),
            ("goal", [("fail", "1")]),
            ("fail", [("goal", "1")]),
        ],
        ["goal"],
        ["fail"],
    )
    add(
        "no-terminal",
        "No terminals: every conditional success is undefined",
        "A closed two-state cycle has no success or failure terminal. Never hitting any terminal has probability one; it is not a numerical singular-system error.",
        [("left", [("right", "1")]), ("right", [("left", "1")])],
        [],
        [],
    )
    add(
        "all-terminal",
        "Every root is already stopped",
        "Success roots have zero first-hit time; failure-root success conditioning remains undefined. Supplied outgoing edges do not undo first-hit success or failure.",
        [("a", [("b", "1")]), ("b", [("a", "1")])],
        ["a"],
        ["b"],
    )
    add(
        "rare",
        "Rare success can have a very long finite mean",
        "A positive 1/1000000 success probability per retry makes eventual success certain, mean 1000000 and variance 999999000000. Small finite-horizon mass is not zero eventual success.",
        [
            ("retry", [("retry", "999999/1000000"), ("goal", "1/1000000")]),
            ("goal", [("goal", "1")]),
        ],
        ["goal"],
        [],
        12,
    )
    add(
        "five",
        "Five original transitions before first success",
        "A deterministic six-state chain reaches the final goal after exactly five transitions. The goal root itself is time zero.",
        [("s" + str(i), [("s" + str(min(i + 1, 5)), "1")]) for i in range(6)],
        ["s5"],
        [],
        6,
    )
    add(
        "multiple",
        "Two success terminals, one first-hit event",
        "Success is reaching either declared goal before failure. It is not a requirement to visit both goals.",
        [
            ("start", [("a", "1/3"), ("b", "1/3"), ("fail", "1/3")]),
            ("a", [("fail", "1")]),
            ("b", [("fail", "1")]),
            ("fail", [("start", "1")]),
        ],
        ["a", "b"],
        ["fail"],
    )
    add(
        "unreachable",
        "An isolated success does not rescue a trap root",
        "The success state exists but cannot be reached from the closed nonterminal component. Zero hit probability means no success-conditioned row or mean is defined.",
        [
            ("left", [("right", "1")]),
            ("right", [("left", "1")]),
            ("goal", [("goal", "1")]),
        ],
        ["goal"],
        [],
    )
    add(
        "cyclic",
        "A cyclic transient block still has an exact inverse",
        "Two nonterminal states communicate and both can exit. Full equations include repeated visits, not just the mass of simple paths.",
        [
            ("a", [("a", "1/4"), ("b", "1/2"), ("goal", "1/4")]),
            ("b", [("a", "1/3"), ("fail", "2/3")]),
            ("goal", [("goal", "1")]),
            ("fail", [("fail", "1")]),
        ],
        ["goal"],
        ["fail"],
    )
    return cs


if __name__ == "__main__":
    p = Path(__file__).resolve().parents[1]
    (p / "docs/controls.json").write_text(json.dumps(controls(), indent=2) + "\n")
    (p / "examples/conditioning.json").write_text(
        json.dumps(controls()[0]["input"], indent=2) + "\n"
    )
