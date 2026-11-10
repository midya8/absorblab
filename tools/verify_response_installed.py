"""Outside-checkout wheel reproduction for the row-response extension."""

import copy, importlib, json, subprocess, sys, tempfile
from pathlib import Path

expected = json.load(open(sys.argv[1]))
origins = []
for name in [
    "absorblab",
    "absorblab.input",
    "absorblab.linear",
    "absorblab.core",
    "absorblab.verify",
    "absorblab.__main__",
    "absorblab.lumping_input",
    "absorblab.lumping",
    "absorblab.lumping_verify",
    "absorblab.lumping_cli",
    "absorblab.response_input",
    "absorblab.response",
    "absorblab.response_verify",
    "absorblab.response_cli",
]:
    p = Path(importlib.import_module(name).__file__).resolve()
    assert "site-packages" in p.parts
    origins.append(str(p))
from absorblab.response import analyze_response
from absorblab.response_verify import verify_response

entry = [str(Path(sys.executable).with_name("absorblab-response"))]
with tempfile.TemporaryDirectory() as d:
    for e in expected:
        assert analyze_response(e["input"]) == e["report"]
        assert verify_response(e["report"])
    for command in [entry, [sys.executable, "-m", "absorblab.response_cli"]]:
        for e in expected:
            p = subprocess.run(
                command + ["-"],
                input=json.dumps(e["input"]),
                text=True,
                capture_output=True,
                cwd=d,
            )
            assert p.returncode == 0, p.stderr
            assert json.loads(p.stdout) == e["report"]
            p = subprocess.run(
                command + ["-", "--verify"],
                input=json.dumps(e["report"]),
                text=True,
                capture_output=True,
                cwd=d,
            )
            assert p.returncode == 0, p.stderr
            assert json.loads(p.stdout) == {
                "valid": True,
                "schema": "absorblab-response-v1",
            }
    for i in range(24):
        report = copy.deepcopy(expected[i % len(expected)]["report"])
        report["response"]["curves"][0]["success"][0] = "forged"
        try:
            verify_response(report)
        except ValueError:
            pass
        else:
            raise AssertionError("checker accepted forgery")
        dest = Path(d) / "preserve.json"
        dest.write_bytes(b"existing output\n")
        p = subprocess.run(
            entry + ["-", "--verify", "--output", str(dest)],
            input=json.dumps(report),
            text=True,
            capture_output=True,
            cwd=d,
        )
        assert p.returncode == 2 and p.stdout == "" and "Traceback" not in p.stderr
        assert dest.read_bytes() == b"existing output\n"
        assert sorted(x.name for x in Path(d).iterdir()) == ["preserve.json"]
print(
    json.dumps(
        {
            "response_reports": len(expected),
            "entrypoints": 2,
            "installed_origins": origins,
            "forged_cli_rejections_and_atomic_preservation": 24,
            "direct_checker_forgeries": 24,
        }
    )
)
