"""Contract tests for review."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_skill_spec_exists():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skill_spec.json")
    assert os.path.isfile(path)
    with open(path) as f:
        spec = json.load(f)
    assert "name" in spec
    assert "version" in spec

def test_skilmd_exists():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SKILL.md")
    assert os.path.isfile(path)

def test_config_yaml_exists():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    assert os.path.isfile(path)

def test_run_py_has_main():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "run.py")
    with open(path) as f:
        content = f.read()
    assert "def main(" in content
    assert "if __name__" in content

def test_has_tests():
    td = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
    assert os.path.isdir(td)
    assert os.path.isfile(os.path.join(td, "test_unit.py"))
    assert os.path.isfile(os.path.join(td, "test_integration.py"))
    assert os.path.isfile(os.path.join(td, "test_contract.py"))
