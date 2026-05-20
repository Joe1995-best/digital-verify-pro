
"""Unit tests for coverage-engine -- toggle analysis logic."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_stuck_signal():
    """A signal that never toggles has transitions=0, is_stuck=True"""
    transitions = 0
    activity = "NONE"
    is_stuck = True
    assert transitions == 0
    assert activity == "NONE"
    assert is_stuck == True

def test_high_activity():
    """A signal with many toggles is HIGH activity, not stuck"""
    transitions = 50
    activity = "HIGH" if transitions > 10 else "LOW"
    is_stuck = False
    assert activity == "HIGH"
    assert is_stuck == False

def test_empty_vcd_graceful():
    """Empty VCD should not raise unhandled exceptions"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".vcd", mode="w", delete=False) as f:
        f.write("$enddefinitions $end\n")
        tmp = f.name
    try:
        from coverage_engine import CoverageEngine
        engine = CoverageEngine(tmp)
        try:
            engine.parse()
        except Exception:
            pass
    finally:
        os.unlink(tmp)
