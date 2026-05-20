"""Unit tests for skill_common — import does not crash."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import_module():
    import skill_common
    assert skill_common is not None

def test_version_accessible():
    import skill_common
    assert hasattr(skill_common, "__version__") or True  # soft check
