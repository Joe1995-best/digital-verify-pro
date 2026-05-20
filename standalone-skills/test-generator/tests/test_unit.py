"""Unit tests for test-generator -- core logic, zero external dependencies."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import():
    import run
    assert run is not None

def test_help():
    import subprocess
    result = subprocess.run(
        [sys.executable, "run.py", "--help"],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )
    assert result.returncode == 0
