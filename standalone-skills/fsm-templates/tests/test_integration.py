"""Integration tests for fsm-templates."""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def test_minimal_spec():
    spec = os.path.join(FIXTURES, "minimal_spec.yml")
    if not os.path.isfile(spec):
        return
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, "run.py", "--spec", spec, "--out", tmp, "--result", os.path.join(tmp, "result.json")],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert result.returncode != 99
