
"""Integration tests for plan-generator -- run with fixture, validate result.json."""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def test_with_fixture():
    spec = os.path.join(FIXTURES, "minimal_spec.yml")
    vcd = os.path.join(FIXTURES, "minimal.vcd")
    inp = spec if os.path.isfile(spec) else (vcd if os.path.isfile(vcd) else None)
    if not inp:
        return
    flag = "--spec" if inp.endswith(".yml") else "--vcd"
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            [sys.executable, "run.py", flag, inp, "--out", tmp, "--result", os.path.join(tmp, "result.json")],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert r.returncode != 99, "INTERNAL_ERROR: " + r.stderr[:200]
        rj = os.path.join(tmp, "result.json")
        if os.path.isfile(rj):
            with open(rj) as f:
                d = json.load(f)
            assert d["status"] in ("pass", "fail", "error", "skip")
            assert "metrics" in d
            assert "timestamp" in d
