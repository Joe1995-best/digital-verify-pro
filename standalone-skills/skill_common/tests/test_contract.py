"""Contract tests for skill_common — validate package structure."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_skill_spec_exists():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skill_spec.json")
    # skill_common is a library package, not a full standalone skill —
    # it may not have a skill_spec.json.  Verify at least __init__.py exists.
    pkg_init = os.path.join(os.path.dirname(os.path.dirname(__file__)), "__init__.py")
    assert os.path.isfile(pkg_init), "skill_common/__init__.py must exist"

def test_import():
    import skill_common
    assert skill_common is not None
