import copy
from fractions import Fraction as F
import importlib.util
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from absorblab import analyze
from absorblab.verify import verify, replay
from absorblab.input import validate

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = json.loads((ROOT / "docs/controls.json").read_text())


def request(rows, status, horizon=3):
    n = len(rows)
    names = ["s" + str(i) for i in range(n)]
    return {
        "states": [
            {
                "name": names[i],
                "transitions": [{"to": names[j], "prob": str(p)} for j, p in row],
            }
            for i, row in enumerate(rows)
        ],
        "success": [names[i] for i, s in enumerate(status) if s == 1],
        "failure": [names[i] for i, s in enumerate(status) if s == 2],
        "horizon": horizon,
    }


class AbsorbTests(unittest.TestCase):
    def check(self, r):
        a = analyze(r)
        self.assertTrue(verify(a))
        return a

    def test_all_prescribed_controls_and_byte_reproduction(self):
        spec = importlib.util.spec_from_file_location(
            "control_source", ROOT / "tools/make_controls.py"
        )
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(
            (ROOT / "docs/controls.json").read_text(),
            json.dumps(m.controls(), indent=2) + "\n",
        )
        self.assertEqual(
            (ROOT / "examples/conditioning.json").read_text(),
            json.dumps(m.controls()[0]["input"], indent=2) + "\n",
        )
        for c in CONTROLS:
            with self.subTest(c["id"]):
                self.check(c["input"])

    def test_global_conditioning_is_not_local_failure_removal(self):
        a = self.check(CONTROLS[0]["input"])
        s = a["states"][0]
        self.assertEqual(s["success_probability"], "5/8")
        self.assertEqual(
            s["conditional_success"],
            {"mean": "6/5", "second_moment": "8/5", "variance": "4/25"},
        )
        self.assertEqual(
            s["unconditional_success_time"], {"kind": "infinite", "value": None}
        )
        self.assertEqual(
            s["unconditional_terminal_time"], {"kind": "finite", "value": "3/2"}
        )
        edges = {e["to"]: e for e in a["conditioned"][0]["edges"]}
        self.assertEqual(edges["risky"]["original_prob"], "1/2")
        self.assertEqual(edges["risky"]["conditioned_prob"], "1/5")
        self.assertEqual(edges["goal"]["conditioned_prob"], "4/5")

    def test_geometric_retry_exact_moments_and_finite_deadlines(self):
        a = self.check(CONTROLS[1]["input"])
        s = a["states"][0]
        self.assertEqual(s["success_probability"], "1")
        self.assertEqual(
            s["conditional_success"],
            {"mean": "4", "second_moment": "28", "variance": "12"},
        )
        for r in a["forecasts"][0]["rows"]:
            self.assertEqual(F(r["still_active"]), F(3, 4) ** r["step"])
            self.assertEqual(F(r["success_by_step"]), 1 - F(3, 4) ** r["step"])
            self.assertGreater(F(r["still_active"]), 0)
        a = self.check(CONTROLS[7]["input"])
        self.assertEqual(
            a["states"][0]["conditional_success"],
            {
                "mean": "1000000",
                "second_moment": "1999999000000",
                "variance": "999999000000",
            },
        )

    def test_nonterminal_trap_and_least_harmonic_solution(self):
        a = self.check(CONTROLS[3]["input"])
        s = a["states"][0]
        self.assertEqual(
            [
                s[k]
                for k in [
                    "success_probability",
                    "failure_probability",
                    "never_terminal_probability",
                ]
            ],
            ["1/3"] * 3,
        )
        self.assertEqual(a["linear_system"]["unknowns"], ["start"])
        self.assertEqual(a["support"]["zero_terminal_states"], ["left", "right"])
        self.assertEqual(
            [c["states"] for c in a["components"] if c["nonterminal_trap"]],
            [["left", "right"]],
        )
        for i in [1, 2]:
            self.assertIsNone(a["states"][i]["conditional_success"])
            self.assertFalse(a["conditioned"][i]["defined"])
        self.assertEqual(s["unconditional_terminal_time"]["kind"], "infinite")

    def test_terminal_overrides_empty_targets_and_time_zero(self):
        a = self.check(CONTROLS[4]["input"])
        self.assertEqual(a["stopped_matrix"][1], ["0", "1", "0"])
        self.assertEqual(a["original_matrix"][1], ["0", "0", "1"])
        self.assertEqual(a["states"][1]["conditional_success"]["mean"], "0")
        self.assertIsNone(a["states"][2]["conditional_success"])
        a = self.check(CONTROLS[5]["input"])
        self.assertEqual(a["linear_system"]["matrix"], [])
        self.assertEqual(a["linear_system"]["inverse"], [])
        for s in a["states"]:
            self.assertEqual(s["never_terminal_probability"], "1")
            self.assertIsNone(s["conditional_terminal_mean"])
        a = self.check(CONTROLS[6]["input"])
        self.assertEqual(a["linear_system"]["elimination"], [])

    def test_all_two_state_uniform_support_and_status_cases(self):
        count = 0
        options = [[(0, F(1))], [(1, F(1))], [(0, F(1, 2)), (1, F(1, 2))]]
        for rows in itertools.product(options, repeat=2):
            for status in itertools.product(range(3), repeat=2):
                self.check(request(rows, status))
                count += 1
        self.assertEqual(count, 81)

    def test_all_three_state_deterministic_chains_and_status_cases(self):
        count = 0
        for targets in itertools.product(range(3), repeat=3):
            for status in itertools.product(range(3), repeat=3):
                a = self.check(request([[(j, F(1))] for j in targets], status))
                count += 1
                for root, s in enumerate(a["states"]):
                    i = root
                    seen = set()
                    steps = 0
                    while status[i] == 0 and i not in seen:
                        seen.add(i)
                        i = targets[i]
                        steps += 1
                    self.assertEqual(
                        s["success_probability"], "1" if status[i] == 1 else "0"
                    )
                    self.assertEqual(
                        s["failure_probability"], "1" if status[i] == 2 else "0"
                    )
                    if status[i] == 1:
                        self.assertEqual(s["conditional_success"]["mean"], str(steps))
                        self.assertEqual(s["conditional_success"]["variance"], "0")
        self.assertEqual(count, 729)

    def test_all_three_state_uniform_nonempty_support_and_status_cases(self):
        options = [
            [(j, F(1, len(xs))) for j in xs]
            for k in [1, 2, 3]
            for xs in itertools.combinations(range(3), k)
        ]
        count = 0
        for rows in itertools.product(options, repeat=3):
            for status in itertools.product(range(3), repeat=3):
                self.check(request(rows, status, 0))
                count += 1
        self.assertEqual(count, 9261)

    def test_seeded_rational_chains_independent_complete_replay(self):
        rng = random.Random(412009)
        for k in range(120):
            n = 2 + k % 5
            rows = []
            for i in range(n):
                ts = rng.sample(range(n), rng.randint(1, n))
                weights = [rng.randint(1, 5) for _ in ts]
                total = sum(weights)
                rows.append([(j, F(w, total)) for j, w in zip(ts, weights)])
            self.check(request(rows, [rng.randrange(3) for _ in range(n)], k % 13))

    def test_acyclic_path_enumeration_checks_probability_and_moment_numerators(self):
        rng = random.Random(21149)
        for k in range(120):
            n = 3 + k % 4
            rows = []
            for i in range(n - 1):
                ts = rng.sample(range(i + 1, n), rng.randint(1, n - i - 1))
                ws = [rng.randint(1, 4) for _ in ts]
                rows.append([(j, F(w, sum(ws))) for j, w in zip(ts, ws)])
            rows.append([(n - 1, F(1))])
            status = [rng.randrange(3) for _ in range(n - 1)] + [1 if k % 2 else 2]
            a = self.check(request(rows, status))
            for root, s in enumerate(a["states"]):
                h = g = m = F(0)

                def paths(i, weight, t):
                    nonlocal h, g, m
                    if status[i] == 1:
                        h += weight
                        g += weight * t
                        m += weight * t * t
                        return
                    if status[i] == 2:
                        return
                    for j, p in rows[i]:
                        paths(j, weight * p, t + 1)

                paths(root, F(1), 0)
                self.assertEqual(
                    [
                        s["success_probability"],
                        s["success_time_numerator"],
                        s["success_second_moment_numerator"],
                    ],
                    [str(h), str(g), str(m)],
                )

    def test_mass_conservation_conditioned_row_sums_and_all_exact_residuals(self):
        for c in CONTROLS:
            a = self.check(c["input"])
            n = len(a["states"])
            p = [[F(x) for x in row] for row in a["stopped_matrix"]]
            h = [F(s["success_probability"]) for s in a["states"]]
            g = [F(s["success_time_numerator"]) for s in a["states"]]
            m = [F(s["success_second_moment_numerator"]) for s in a["states"]]
            for i, s in enumerate(a["states"]):
                if s["name"] not in a["input"]["success"] + a["input"]["failure"]:
                    self.assertEqual(g[i], h[i] + sum(p[i][j] * g[j] for j in range(n)))
                    self.assertEqual(
                        m[i],
                        h[i]
                        + 2 * sum(p[i][j] * g[j] for j in range(n))
                        + sum(p[i][j] * m[j] for j in range(n)),
                    )
                if s["conditional_success"]:
                    self.assertGreaterEqual(F(s["conditional_success"]["variance"]), 0)
                    self.assertEqual(a["conditioned"][i]["row_sum"], "1")
                for r in a["forecasts"][i]["rows"]:
                    self.assertEqual(
                        sum(
                            F(r[k])
                            for k in [
                                "success_by_step",
                                "failure_by_step",
                                "still_active",
                            ]
                        ),
                        1,
                    )
                    self.assertGreaterEqual(F(r["future_success_mass"]), 0)
                    if h[i]:
                        self.assertEqual(
                            F(r["conditional_success_by_step"])
                            + F(r["conditional_remaining"]),
                            1,
                        )

    def test_state_and_edge_permutation_semantics_and_input_isolation(self):
        rng = random.Random(98731)
        for c in CONTROLS:
            r = copy.deepcopy(c["input"])
            before = copy.deepcopy(r)
            old = self.check(r)
            self.assertEqual(r, before)
            rng.shuffle(r["states"])
            r["success"].reverse()
            r["failure"].reverse()
            for s in r["states"]:
                rng.shuffle(s["transitions"])
            new = self.check(r)
            self.assertEqual(
                {s["name"]: s for s in old["states"]},
                {s["name"]: s for s in new["states"]},
            )
        r = copy.deepcopy(CONTROLS[0]["input"])
        a = self.check(r)
        r["states"][0]["name"] = "different"
        self.assertEqual(a["input"]["states"][0]["name"], "start")
        a["states"][0]["name"] = "changed"
        self.assertEqual(a["input"]["states"][0]["name"], "start")

    def test_schema_bounds_exact_row_sums_and_normalization(self):
        base = CONTROLS[0]["input"]
        cases = []
        for v in [None, {}, [], True, 1, "1"]:
            cases.append(v)
        for field, v in [
            ("horizon", True),
            ("horizon", 13),
            ("horizon", -1),
            ("horizon", 1.0),
            ("success", ["missing"]),
            ("success", ["goal", "goal"]),
            ("failure", ["goal"]),
            ("states", []),
        ]:
            r = copy.deepcopy(base)
            r[field] = v
            cases.append(r)
        for p in [
            0,
            1,
            True,
            "0",
            "-1/2",
            "1/0",
            "1.0",
            "NaN",
            "1/1000001",
            "1000001/1000001",
            "2",
        ]:
            r = copy.deepcopy(base)
            r["states"][0]["transitions"][0]["prob"] = p
            cases.append(r)
        r = copy.deepcopy(base)
        r["extra"] = True
        cases.append(r)
        for r in cases:
            with self.assertRaises((ValueError, TypeError)):
                analyze(r)
            with self.assertRaises((ValueError, TypeError)):
                replay(r)
        r = copy.deepcopy(base)
        r["states"][0]["transitions"][0]["prob"] = "2/4"
        self.assertEqual(validate(r)["states"][0]["transitions"][0]["prob"], "1/2")

    def test_full_report_tamper_and_type_rejection(self):
        a = analyze(CONTROLS[0]["input"])
        paths = [
            ["schema"],
            ["limits"],
            ["stopped_matrix", 0, 1],
            ["support", "rounds", 0, "added"],
            ["support", "paths", 0, "probability"],
            ["components", 0, "closed"],
            ["linear_system", "matrix", 0, 0],
            ["linear_system", "inverse", 0, 0],
            ["linear_system", "success_rhs", 0],
            ["linear_system", "elimination", 0, "divisor"],
            ["linear_system", "elimination", 0, "after"],
            ["states", 0, "success_probability"],
            ["states", 0, "conditional_success", "mean"],
            ["states", 0, "conditional_success", "variance"],
            ["states", 0, "never_terminal_probability"],
            ["states", 0, "unconditional_success_time", "kind"],
            ["conditioned", 0, "edges", 1, "conditioned_prob"],
            ["conditioned", 0, "row_sum"],
            ["forecasts", 0, "rows", 1, "success_by_step"],
            ["forecasts", 0, "rows", 1, "conditional_remaining"],
        ]
        for path in paths:
            b = copy.deepcopy(a)
            node = b
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = "forged"
            with self.subTest(path=path), self.assertRaises(ValueError):
                verify(b)
        for b in [a | {"extra": 1}, a | {"schema": True}]:
            with self.assertRaises(ValueError):
                verify(b)
        b = copy.deepcopy(a)
        b["conditioned"][0]["defined"] = 1
        with self.assertRaises(ValueError):
            verify(b)

    def test_checker_has_no_generator_or_elimination_import(self):
        r = analyze(CONTROLS[0]["input"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            p.write_text(json.dumps(r))
            code = "import sys,json;sys.modules['absorblab.core']=None;sys.modules['absorblab.linear']=None;from absorblab.verify import verify;assert verify(json.load(open(sys.argv[1])))"
            out = subprocess.run(
                [sys.executable, "-c", code, str(p)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(out.returncode, 0, out.stderr)

    def test_cli_stdin_roundtrip_atomic_errors_and_byte_caps(self):
        r = CONTROLS[0]["input"]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            cmd = [sys.executable, "-m", "absorblab"]
            a = subprocess.run(
                cmd + ["-", "--output", str(p)],
                input=json.dumps(r),
                capture_output=True,
                text=True,
            )
            self.assertEqual(a.returncode, 0, a.stderr)
            self.assertEqual(a.stdout, "")
            self.assertEqual(json.loads(p.read_text()), analyze(r))
            a = subprocess.run(
                cmd + [str(p), "--verify"], capture_output=True, text=True
            )
            self.assertEqual(a.returncode, 0, a.stderr)
            self.assertEqual(
                json.loads(a.stdout), {"valid": True, "schema": "absorblab-v1"}
            )
            p.write_text("preserve")
            for raw in ["{}", "NaN", '{"states":[],"states":[]}', " " * 65537]:
                a = subprocess.run(
                    cmd + ["-", "--output", str(p)],
                    input=raw,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(a.returncode, 2)
                self.assertEqual(a.stdout, "")
                self.assertNotIn("Traceback", a.stderr)
                self.assertEqual(p.read_text(), "preserve")
            huge = Path(d) / "huge.json"
            huge.write_bytes(b" " * (16 * 1024 * 1024 + 1))
            a = subprocess.run(
                cmd + [str(huge), "--verify", "--output", str(p)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(a.returncode, 2)
            self.assertEqual(p.read_text(), "preserve")
            self.assertEqual(
                sorted(x.name for x in Path(d).iterdir()), ["huge.json", "report.json"]
            )


if __name__ == "__main__":
    unittest.main()
