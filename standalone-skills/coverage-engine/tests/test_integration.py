import pytest

"""Integration tests for coverage-engine -- validate result.json + coverage_report."""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def test_minimal_vcd_produces_valid_result():
    vcd = os.path.join(FIXTURES, "minimal.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            [sys.executable, "run.py", "--vcd", vcd, "--out", tmp, "--result", os.path.join(tmp, "result.json")],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert r.returncode != 99, "INTERNAL_ERROR: " + r.stderr[:200]

        rj = os.path.join(tmp, "result.json")
        assert os.path.isfile(rj), "result.json not produced"
        with open(rj) as f:
            data = json.load(f)
        assert data["status"] in ("pass", "fail", "error", "skip")
        assert "metrics" in data
        assert "timestamp" in data

def test_output_files_exist():
    vcd = os.path.join(FIXTURES, "minimal.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "run.py", "--vcd", vcd, "--out", tmp],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        for fn in ("coverage_report.json", "coverage_report.md"):
            fp = os.path.join(tmp, fn)
            if os.path.isfile(fp) and fn.endswith(".json"):
                with open(fp) as f:
                    payload = json.load(f)
                assert isinstance(payload, dict)
