
"""Contract tests for regression-manager -- validate skill_spec.json, SKILL.md, config.yaml."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_skill_spec_full():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skill_spec.json")
    assert os.path.isfile(path)
    with open(path) as f:
        spec = json.load(f)
    assert "name" in spec
    assert "version" in spec
    assert "interface" in spec
    assert "lifecycle" in spec
    assert "error_codes" in spec

def test_skilmd_has_config():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SKILL.md")
    with open(path) as f:
        content = f.read()
    assert "## Config" in content
    assert "## Known Limitations" in content

def test_config_yaml_valid():
    import yaml
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    assert "timeout_seconds" in cfg
    assert "log_level" in cfg
    assert "out_dir" in cfg

def test_test_dirs_complete():
    base = os.path.dirname(os.path.dirname(__file__))
    for f in ("config.yaml", "schemas/input.schema.json", "schemas/result.schema.json",
              "tests/test_unit.py", "tests/test_integration.py", "tests/test_contract.py",
              "tests/fixtures/minimal_spec.yml"):
        assert os.path.isfile(os.path.join(base, f)), f"Missing: {f}"
