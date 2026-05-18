"""
Tests for pipeline/validators.py — validation gates and inter-phase contracts.
"""

import os
import sys
import pytest

# Ensure project root is in path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "pipeline"))


class TestValidators:
    """Tests for the validator functions."""

    def test_validate_spec_analyzer_missing_files(self, tmp_output_dir):
        """Test that missing required output files produce errors."""
        from pipeline.validators import validate_spec_analyzer

        # Empty output dir should generate errors for missing files
        result = validate_spec_analyzer(None, tmp_output_dir)
        assert "errors" in result or "issues" in result
        issues = result.get("issues", [])
        error_issues = [i for i in issues if i.get("severity") == "ERROR"]
        assert len(error_issues) >= 3  # At least 3 required files missing

    def test_validate_spec_analyzer_with_sample(self, tmp_output_dir, sample_spec_path):
        """Test validation with a spec file but empty output dir."""
        from pipeline.validators import validate_spec_analyzer

        result = validate_spec_analyzer(sample_spec_path, tmp_output_dir)
        # Should still have missing file errors since output dir is empty
        issues = result.get("issues", [])
        has_missing_file_errors = any(
            "missing" in i.get("message", "").lower()
            for i in issues if i.get("severity") == "ERROR"
        )
        assert has_missing_file_errors

    def test_read_yaml(self, sample_spec_path):
        """Test utility function read_yaml."""
        from pipeline.validators import read_yaml

        data = read_yaml(sample_spec_path)
        assert data is not None
        assert data.get("module", {}).get("name") == "test_module"

    def test_read_write_json(self, tmp_output_dir):
        """Test utility functions read_json and write_json."""
        from pipeline.validators import write_json, read_json

        test_data = {"key": "value", "number": 42}
        json_path = os.path.join(tmp_output_dir, "test.json")
        write_json(json_path, test_data)
        assert os.path.exists(json_path)

        loaded = read_json(json_path)
        assert loaded == test_data

    def test_find_sv_files_empty(self, tmp_output_dir):
        """Test find_sv_files returns empty list when no env dir exists."""
        from pipeline.validators import find_sv_files

        files = find_sv_files(tmp_output_dir)
        assert isinstance(files, list)
        assert len(files) == 0

    @pytest.mark.skipif(not os.path.exists(os.path.join(PROJECT_DIR, "pipeline", "validators.py")),
                        reason="validators.py not found")
    def test_validator_module_imports(self):
        """Test that validators module can be imported cleanly."""
        import pipeline.validators
        assert hasattr(pipeline.validators, "validate_spec_analyzer")
        assert hasattr(pipeline.validators, "read_yaml")
        assert hasattr(pipeline.validators, "read_file")
        assert hasattr(pipeline.validators, "write_file")
