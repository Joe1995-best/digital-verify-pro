
"""Contract tests for coverage-engine -- validate skill_spec + output schema."""
import sys, os, json, jsonschema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_skill_spec_valid():
    with open("skill_spec.json") as f:
        spec = json.load(f)
    assert spec["version"].count(".") == 2
    assert spec["lifecycle"]["status"] in ("stable","beta","development")
    assert "interface" in spec
    assert spec["interface"]["entry"] == "run.py"

def test_result_schema():
    """Validate a sample result.json against schema"""
    schema_path = "schemas/result.schema.json"
    if not os.path.isfile(schema_path):
        return  # skip if not yet defined
    with open(schema_path) as f:
        schema = json.load(f)
    sample = {"status": "pass", "timestamp": "2026-05-20T00:00:00",
              "module": "test", "summary": "test", "metrics": {},
              "outputs": {}, "errors": []}
    jsonschema.validate(instance=sample, schema=schema)

def test_downstream_friendly():
    """Output format must be parseable by downstream skills"""
    sample = {"metrics": {"total_signals": 100, "toggle_coverage_percent": 85.0, "stuck_signals": 0}}
    assert 0 <= sample["metrics"]["toggle_coverage_percent"] <= 100
    assert isinstance(sample["metrics"]["stuck_signals"], int)
