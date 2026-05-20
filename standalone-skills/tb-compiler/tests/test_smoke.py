"""
Smoke test for tb-compiler: basic functional check.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_help():
    """Running --help should not crash"""
    import subprocess
    result = subprocess.run([sys.executable, "-m", "run", "--help"],
                           capture_output=True, text=True,
                           cwd=os.path.dirname(os.path.dirname(__file__)))
    assert result.returncode == 0
