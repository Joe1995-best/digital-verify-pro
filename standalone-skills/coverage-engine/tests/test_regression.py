import pytest

"""
Regression tests for coverage-engine -- deterministic results.
"""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def test_deterministic_coverage():
    vcd = os.path.join(FIXTURES, "minimal.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, "run.py", "--vcd", vcd, "--out", tmp],
                capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
            rj = os.path.join(tmp, "result.json")
            if os.path.isfile(rj):
                with open(rj) as f:
                    results.append(json.load(f))
    if len(results) == 2:
        m0 = json.dumps(results[0].get("metrics", {}), sort_keys=True)
        m1 = json.dumps(results[1].get("metrics", {}), sort_keys=True)
        assert m0 == m1, "Determinism broken!"
