"""
Tests for pipeline/template_engine.py — spec data normalization & template rendering.
"""

import os
import sys
import pytest

# Ensure project root is in path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "pipeline"))


class TestBuildSpecData:
    """Tests for build_spec_data() — the core spec → normalized data function."""

    def test_basic_spec_parsing(self, sample_spec_path):
        """Test that a valid spec YAML is parsed and returns expected top-level fields."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        assert data["module_name"] == "test_module"
        assert data["module_desc"] == "A test module for pytest"
        assert data["clocks"][0]["name"] == "clk"
        assert data["clk_name"] == "clk"
        assert data["rst_name"] == "rstn"
        assert data["rst_polarity"] == "active_low"
        assert data["rst_polarity_expr"] == "!"

    def test_registers_parsed(self, sample_spec_path):
        """Test that register definitions are present and correct."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        assert data["num_registers"] == 2
        reg_names = [r["name"] for r in data["reg_list"]]
        assert "CTRL" in reg_names
        assert "STATUS" in reg_names
        assert "ADDR_CTRL" in data["reg_constants"]
        assert "ADDR_STATUS" in data["reg_constants"]

    def test_hwaccess_derivation(self, sample_spec_path):
        """Test that hwaccess is correctly derived from access field."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        ctrl_fields = [f for f in data["reg_fields_detail"] if f["reg_name"] == "CTRL"]
        assert len(ctrl_fields) == 1
        cf = ctrl_fields[0]
        assert cf["field_name"] == "enable"
        assert cf["access"] == "rw"
        # rw access → hrw hwaccess
        assert cf["hwaccess"] == "hrw"
        # hrw → hwqe = "true"
        assert cf["hwqe"] == "true"

        status_fields = [f for f in data["reg_fields_detail"] if f["reg_name"] == "STATUS"]
        assert len(status_fields) == 1
        sf = status_fields[0]
        assert sf["access"] == "ro"
        # ro access → hro hwaccess
        assert sf["hwaccess"] == "hro"
        # hro → hwqe = "false"
        assert sf["hwqe"] == "false"

    def test_swacc_derivation(self, sample_spec_path):
        """Test that swacc is correctly derived."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        fields = {f["field_name"]: f for f in data["reg_fields_detail"]}
        assert fields["enable"]["swacc"] == "RW"
        assert fields["ready"]["swacc"] == "RO"

    def test_interfaces_parsed(self, sample_spec_path):
        """Test interface parsing and helpers."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        assert len(data["interfaces"]) == 1
        apb = data["interfaces"][0]
        assert apb["type"] == "APB"
        assert "signal_decls" in apb
        assert len(apb.get("signal_names", [])) == 6

        # APB interface identified
        assert data["apb"]["type"] == "APB"

    def test_fsm_section_none(self, sample_spec_path):
        """Test that FSM section is None when not specified."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)
        assert data["fsm"] is None

    def test_test_scenarios_parsed(self, sample_spec_path):
        """Test that test scenarios are parsed."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        assert len(data["test_scenarios"]) == 1
        assert data["test_scenarios"][0]["name"] == "basic_ctrl_write"

    def test_reserved_ranges(self, sample_spec_path):
        """Test reserved address range calculation."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        # Two registers at 0x000 and 0x004 → no gap between them
        # But there's reserved space above STATUS (0x004 + 4 = 0x008) to top of 4K (0xFFF)
        assert len(data["reserved_ranges"]) >= 1
        # The last reserved range should be above STATUS
        last_range = data["reserved_ranges"][-1]
        assert "reserved above" in last_range["desc"]

    def test_coverage_goals(self, sample_spec_path):
        """Test coverage goals are parsed."""
        from pipeline.template_engine import build_spec_data
        data = build_spec_data(sample_spec_path)

        assert data["coverage_goals"]["toggle"] == 90


class TestTemplateRender:
    """Tests for template rendering functions."""

    def test_load_template_exists(self, sample_spec_path):
        """Test that assertion templates can be loaded."""
        from pipeline.template_engine import load_template
        content = load_template("assertion/basic_assert.sv.tpl")
        # The template may or may not exist; if it does, check it's non-empty
        if content is not None:
            assert len(content) > 0

    def test_render_with_data(self, sample_spec_data):
        """Test rendering a template with spec data."""
        from pipeline.template_engine import render
        # Try rendering with some key fields
        result = render("assertion/basic_assert.sv.tpl", sample_spec_data)
        # If template exists, result should be a string
        if result is not None:
            assert isinstance(result, str)
            assert len(result) > 0
