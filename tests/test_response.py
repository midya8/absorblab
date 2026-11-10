import copy
from fractions import Fraction as F
import importlib.util
import itertools
from pathlib import Path
import random
import unittest
from absorblab.response import analyze_response
from absorblab.response_verify import replay_response, verify_response
from absorblab.response_input import validate
from absorblab.input import equal

spec = importlib.util.spec_from_file_location("response_cases", Path(__file__).resolve().parents[1] / "tools/response_cases.py")
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


class ResponseTests(unittest.TestCase):
    def test_twelve_original_controls_full_record(self):
        for name, request in cases.controls():
            with self.subTest(name=name):
                source = copy.deepcopy(request)
                equal(analyze_response(request), replay_response(request))
                self.assertEqual(source, request)
    def test_support_changing_endpoint_is_not_limit(self):
        out = analyze_response(cases.controls()[0][1])
        self.assertEqual(out["endpoints"][0]["interior_limits"][0]["success"], "1")
        self.assertEqual(out["samples"][0]["roots"][0]["success"], "0")
        self.assertEqual(out["samples"][0]["roots"][0]["never"], "1")
        self.assertIsNone(out["samples"][0]["roots"][0]["conditional"])
        self.assertTrue(out["endpoints"][0]["discontinuous"][0])
        self.assertIsNone(out["samples"][0]["derivatives"])
    def test_exact_nonlinear_derivatives_not_finite_differences(self):
        out = analyze_response(cases.controls()[1][1])
        zero = next(x for x in out["samples"] if x["transfer"] == "0")
        self.assertEqual(zero["roots"][0]["success"], "1/2")
        self.assertEqual(zero["derivatives"][0]["success"], {"first": "1", "second": "-4"})
        # Direct geometric retry formula for every displayed point.
        for point in out["samples"]:
            t = F(point["transfer"])
            self.assertEqual(F(point["roots"][0]["success"]), (F(1, 4) + t) / (F(1, 2) + t))
    def test_visit_and_edge_counts_include_time_zero(self):
        out = analyze_response(cases.controls()[0][1])
        zero = next(x for x in out["samples"] if x["transfer"] == "0")
        traffic = zero["roots"][0]["conditional"]
        self.assertEqual(traffic["visits"], ["2", "0"])
        self.assertEqual(traffic["edges"], [["1", "1"], ["0", "0"]])
        self.assertEqual(traffic["mean_time"], "2")
        terminal = zero["roots"][1]["conditional"]
        self.assertEqual(terminal["mean_time"], "0")
        self.assertEqual(terminal["success_arrivals"], "0")
    def test_uniform_two_state_status_support_atlas(self):
        supports = [(1, 0), (0, 1), (F(1, 2), F(1, 2))]
        count = 0
        for rows in itertools.product(supports, repeat=2):
            for status in itertools.product(range(3), repeat=2):
                for row in range(2):
                    if status[row] != 0:
                        continue
                    request = cases.request(rows, [i for i, s in enumerate(status) if s == 1], [i for i, s in enumerate(status) if s == 2], row=row)
                    equal(analyze_response(request), replay_response(request))
                    count += 1
        self.assertEqual(count, 54)
    def test_seeded_rational_chains(self):
        rng = random.Random(62719)
        for k in range(80):
            n = rng.randrange(2, 7)
            rows = []
            for _ in range(n):
                weights = [rng.randrange(4) for _ in range(n)]
                if not any(weights):
                    weights[rng.randrange(n)] = 1
                rows.append([F(v, sum(weights)) for v in weights])
            varied = rng.randrange(n)
            donor = next(i for i, v in enumerate(rows[varied]) if v)
            receiver = rng.choice([i for i in range(n) if i != donor])
            status = [rng.randrange(3) if i != varied else 0 for i in range(n)]
            request = cases.request(rows, [i for i, s in enumerate(status) if s == 1], [i for i, s in enumerate(status) if s == 2], varied, donor, receiver)
            with self.subTest(case=k):
                equal(analyze_response(request), replay_response(request))
    def test_transfer_reversal(self):
        request = copy.deepcopy(cases.controls()[1][1])
        out = analyze_response(request)
        request["donor"], request["receiver"] = request["receiver"], request["donor"]
        reversed_out = analyze_response(request)
        by_t = {F(x["transfer"]): x for x in reversed_out["samples"]}
        for point in out["samples"]:
            other = by_t[-F(point["transfer"])]
            self.assertEqual(point["roots"], other["roots"])
            if point["derivatives"]:
                for a, b in zip(point["derivatives"], other["derivatives"]):
                    for key in a:
                        self.assertEqual(F(a[key]["first"]), -F(b[key]["first"]))
                        self.assertEqual(a[key]["second"], b[key]["second"])
    def test_horizon_does_not_truncate_eventual_traffic(self):
        request = copy.deepcopy(cases.controls()[0][1])
        a = analyze_response(request)
        request["chain"]["horizon"] = 0
        b = analyze_response(request)
        a["input"] = b["input"]
        self.assertEqual(a, b)
    def test_strict_schema(self):
        request = cases.controls()[0][1]
        for key, value in [("at", 0), ("at", "1e-2"), ("at", "1/0"), ("at", "0.1"), ("at", "2"), ("at", "-2"), ("at", "1/1000001"), ("donor", "missing"), ("row", "s1"), ("receiver", "s0")]:
            bad = copy.deepcopy(request)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate(bad)
        bad = copy.deepcopy(request)
        bad["extra"] = True
        with self.assertRaises(ValueError):
            validate(bad)
    def test_every_noninput_primitive_leaf_mutation_rejected(self):
        out = analyze_response(cases.controls()[0][1])
        paths = []
        def walk(value, path):
            if isinstance(value, dict):
                for k, v in value.items():
                    if not path and k == "input":
                        continue
                    walk(v, path + [k])
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    walk(v, path + [i])
            else:
                paths.append(path)
        walk(out, [])
        for path in paths:
            bad = copy.deepcopy(out)
            target = bad
            for part in path[:-1]:
                target = target[part]
            old = target[path[-1]]
            target[path[-1]] = not old if type(old) is bool else old + 1 if type(old) is int else "forged" if type(old) is str else "not-null"
            with self.assertRaises(ValueError):
                verify_response(bad)
        print("response separately mutated primitive leaves:", len(paths))
    def test_cli_generation_replay_strict_json_and_atomic_refusal(self):
        import json, subprocess, sys, tempfile
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / 'output.json'
            req = Path(directory) / 'request.json'
            req.write_text(json.dumps(cases.controls()[0][1]))
            run = lambda *args: subprocess.run([sys.executable, '-m', 'absorblab.response_cli', *map(str, args)], cwd=root, text=True, capture_output=True)
            self.assertEqual(run(req, '--output', dest).returncode, 0)
            self.assertEqual(run(dest, '--verify').returncode, 0)
            cert = json.loads(dest.read_text())
            frozen = dest.read_bytes()
            for kind in range(20):
                bad = copy.deepcopy(cert)
                if kind % 4 == 0:
                    bad['samples'][kind % len(bad['samples'])]['roots'][0]['success'] = 'forged'
                elif kind % 4 == 1:
                    bad['response']['curves'][0]['success'][0] = 'forged'
                elif kind % 4 == 2:
                    bad['endpoints'][0]['discontinuous'][0] = not bad['endpoints'][0]['discontinuous'][0]
                else:
                    bad['samples'][1]['roots'][0]['conditional']['edges'][0][0] = 'forged'
                req.write_text(json.dumps(bad))
                self.assertEqual(run(req, '--verify', '--output', dest).returncode, 2)
                self.assertEqual(dest.read_bytes(), frozen)
            for raw in ('{"chain":{},"chain":{}}', '{"at":NaN}', '{"at":1.0}', 'x' * 65537):
                req.write_text(raw)
                self.assertEqual(run(req, '--output', dest).returncode, 2)
                self.assertEqual(dest.read_bytes(), frozen)
    def test_checker_import_isolation(self):
        import subprocess, sys
        code = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname in {'absorblab.response','absorblab.linear','absorblab.core'}:raise RuntimeError(fullname)
sys.meta_path.insert(0, Block())
from absorblab.response_verify import replay_response
from tools.response_cases import controls
assert replay_response(controls()[0][1])['endpoints'][0]['discontinuous'][0]
'''
        subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], check=True)


if __name__ == "__main__":
    unittest.main()
