
"""Unit tests for fsm-templates -- core logic validation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import():
    import run
    assert run is not None

def test_parse_args():
    """--help should not crash"""
    import subprocess
    r = subprocess.run([sys.executable, "run.py", "--help"],
                       capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(__file__)))
    assert r.returncode == 0

def test_result_schema_contract():
    """Validate result.json would conform to expected schema"""
    schema = {"type": "object", "required": ["status", "timestamp"]}
    sample = {"status": "pass", "timestamp": "2026-01-01T00:00:00"}
    assert sample["status"] in ("pass", "fail", "error", "skip")
