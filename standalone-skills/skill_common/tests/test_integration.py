"""Integration tests for skill_common — basic fixture flow."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import_all():
    """Verify that all public names in skill_common can be imported."""
    import skill_common
    # Check core names are accessible
    for name in ("get_template_engine", "get_questa_vcs_runner",
                  "read_yaml_spec", "parse_fields"):
        assert hasattr(skill_common, name), f"skill_common.{name} not found"
