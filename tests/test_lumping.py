import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from absorblab.lumping import analyze_lumping
from absorblab.lumping_verify import verify_lumping
from tools.lumping_cases import controls, seeded, exhaustive


class LumpingTests(unittest.TestCase):
    def test_all_full_reports(self):
        cases = list(exhaustive()) + seeded() + [c["input"] for c in controls()]
        for case in cases:
            self.assertTrue(verify_lumping(analyze_lumping(case)))
        print("lumping full independent reports:", len(cases))

    def test_default_cascade(self):
        r = analyze_lumping(controls()[0]["input"])
        self.assertEqual(
            [x["blocks"] for x in r["rounds"]],
            [
                [[0, 1, 2, 3, 5], [4]],
                [[0, 1, 5], [2], [3], [4]],
                [[0, 5], [1], [2], [3], [4]],
            ],
        )
        self.assertEqual(r["final_blocks"], [[0, 5], [1], [2], [3], [4]])
        pair = next(
            x for x in r["pair_witnesses"] if x["left"] == 0 and x["right"] == 1
        )
        self.assertEqual(pair["round"], 1)
        self.assertEqual(pair["left_mass"], "1")
        self.assertEqual(pair["right_mass"], "0")

    def test_exact_not_tolerance(self):
        r = analyze_lumping(controls()[2]["input"])
        self.assertEqual(len(r["final_blocks"]), 3)
        self.assertEqual(r["rounds"][0]["masses"][1][0], "1/1000000")

    def test_different_rows_merge(self):
        r = analyze_lumping(controls()[1]["input"])
        self.assertNotEqual(r["original_matrix"][0], r["original_matrix"][2])
        self.assertEqual(r["final_blocks"], [[0, 2], [1, 3]])

    def test_terminal_status_must_be_preserved(self):
        r = analyze_lumping(controls()[3]["input"])
        self.assertEqual(r["initial_blocks"], [[0], [1]])
        self.assertEqual(r["pair_witnesses"][0]["kind"], "observation")

    def test_raw_not_stopped(self):
        r = analyze_lumping(controls()[4]["input"])
        self.assertEqual(r["first_hit"][0]["original"], r["first_hit"][1]["original"])
        self.assertNotEqual(r["state_blocks"][0], r["state_blocks"][1])

    def test_unobserved_trivial_partition(self):
        r = analyze_lumping(controls()[5]["input"])
        self.assertEqual(r["final_blocks"], [[0, 1, 2]])
        self.assertEqual(r["quotient_matrix"], [["1"]])

    def test_zero_horizon_still_refines(self):
        r = analyze_lumping(controls()[9]["input"])
        self.assertEqual(r["forecasts"][0]["rows"][0]["step"], 0)
        self.assertEqual(len(r["forecasts"][0]["rows"]), 1)
        self.assertEqual(r["final_blocks"], [[0], [1]])

    def test_full_partition_atlas(self):
        r = analyze_lumping(controls()[0]["input"])
        self.assertEqual(len(r["partition_atlas"]), 203)
        self.assertTrue(
            all(x["refines_final"] for x in r["partition_atlas"] if x["allowed"])
        )
        self.assertTrue(
            any(
                x["blocks"] == [[0, 5], [1], [2], [3], [4]]
                for x in r["partition_atlas"]
            )
        )

    def test_permutation_and_no_mutation(self):
        d = controls()[0]["input"]
        before = copy.deepcopy(d)
        r = analyze_lumping(d)
        self.assertEqual(d, before)
        perm = [4, 2, 5, 1, 0, 3]
        x = copy.deepcopy(d)
        x["chain"]["states"] = [d["chain"]["states"][i] for i in perm]
        x["observations"] = [d["observations"][i] for i in perm]
        s = analyze_lumping(x)
        expected = sorted(sorted(perm.index(i) for i in b) for b in r["final_blocks"])
        self.assertEqual(expected, s["final_blocks"])

    def test_verifier_is_independent(self):
        r = analyze_lumping(controls()[0]["input"])
        with patch(
            "absorblab.lumping.analyze_lumping", side_effect=AssertionError
        ), patch("absorblab.lumping.partitions", side_effect=AssertionError), patch(
            "absorblab.core.analyze", side_effect=AssertionError
        ):
            self.assertTrue(verify_lumping(r))

    def test_mutated_primitive_fields(self):
        r = analyze_lumping(controls()[3]["input"])

        def walk(x, p=()):
            if isinstance(x, dict):
                for k, v in x.items():
                    if p or k != "input":
                        yield from walk(v, p + (k,))
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    yield from walk(v, p + (i,))
            else:
                yield p, x

        count = 0
        for path, value in walk(r):
            x = copy.deepcopy(r)
            dst = x
            for k in path[:-1]:
                dst = dst[k]
            dst[path[-1]] = (
                not value
                if type(value) is bool
                else (
                    value + 1
                    if type(value) is int
                    else "corrupt" if type(value) is str else 0
                )
            )
            with self.assertRaises(ValueError):
                verify_lumping(x)
            count += 1
        for x in [dict(r, extra=0), {k: v for k, v in r.items() if k != "limits"}]:
            with self.assertRaises(ValueError):
                verify_lumping(x)
        print("lumping mutated noninput primitive leaves:", count)

    def test_invalid_contract(self):
        d = controls()[0]["input"]
        for x in [
            None,
            [],
            {},
            dict(d, extra=0),
            dict(d, observations=[]),
            dict(d, observations=[True] * 6),
            dict(d, observations=["bad space"] * 6),
            dict(d, chain={**d["chain"], "horizon": True}),
        ]:
            with self.assertRaises(ValueError):
                analyze_lumping(x)

    def test_cli_atomic_strict_json(self):
        cmd = [sys.executable, "-m", "absorblab.lumping_cli"]
        d = controls()[0]["input"]
        r = subprocess.run(
            cmd + ["-"], input=json.dumps(d), text=True, capture_output=True
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), analyze_lumping(d))
        v = subprocess.run(
            cmd + ["-", "--verify"], input=r.stdout, text=True, capture_output=True
        )
        self.assertEqual(v.returncode, 0, v.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            out.write_text("preserve")
            for bad in ["{}", '{"chain":{},"chain":{}}', "NaN", " " * 65537]:
                x = subprocess.run(
                    cmd + ["-", "--output", str(out)],
                    input=bad,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(x.returncode, 2)
                self.assertEqual(out.read_text(), "preserve")
                self.assertNotIn("Traceback", x.stderr)


if __name__ == "__main__":
    unittest.main()
