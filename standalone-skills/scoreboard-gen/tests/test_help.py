"""Test that scoreboard gen run.py --help works."""
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent


def test_help():
    """Verify run.py --help exits cleanly with return code 0."""
    run_py = SKILL_DIR / "run.py"
    if not run_py.exists():
        raise RuntimeError("run.py not found: {0}".format(run_py))
    result = subprocess.run(
        [sys.executable, str(run_py), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "--help failed: {0}".format(result.stderr)


if __name__ == "__main__":
    test_help()
    print("PASS: test_help")