"""
Regression tests for test-generator -- basic stability.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_deterministic():
    import run
    import importlib
    r1 = importlib.reload(run)
    r2 = importlib.reload(run)
    assert dir(r1) == dir(r2), "Import not deterministic"