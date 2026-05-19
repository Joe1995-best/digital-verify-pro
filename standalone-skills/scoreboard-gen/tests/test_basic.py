"""Basic smoke test for the skill."""
import subprocess, sys, os
this_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(this_dir)

def test_help_runs():
    """Verify --help exits successfully."""
    run_py = os.path.join(skill_dir, "run.py")
    if os.path.exists(run_py):
        result = subprocess.run(
            [sys.executable, run_py, "--help"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0

def test_skilmd_exists():
    """Verify SKILL.md exists."""
    assert os.path.exists(os.path.join(skill_dir, "SKILL.md"))
