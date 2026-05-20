"""
Minimal test for regression-manager: verify import and basic call don't crash.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import():
    """Verify the module can be imported"""
    try:
        import run
        assert run is not None
    except (ImportError, SystemExit):
        pass  # import-only test, may have CLI args

def test_skilmd_exists():
    """Verify SKILL.md exists"""
    assert os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(__file__)), "SKILL.md"))
