"""pytest fixtures for digital-verify-pro tests."""

import os
import sys
import pytest
import tempfile
import shutil

# Add project root to path for imports
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "pipeline"))


@pytest.fixture
def tmp_output_dir():
    """Create a temporary output directory for test artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="dvp_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_spec_path(tmp_output_dir):
    """Create a minimal valid spec YAML and return its path."""
    import yaml
    spec = {
        "module": {
            "name": "test_module",
            "description": "A test module for pytest",
            "version": "1.0"
        },
        "clocks": [{"name": "clk", "frequency_MHz": 50}],
        "resets": [{"name": "rstn", "polarity": "active_low"}],
        "interfaces": [
            {
                "type": "APB",
                "name": "apb_if",
                "signals": [
                    {"name": "paddr", "width": 12},
                    {"name": "pwdata", "width": 32},
                    {"name": "prdata", "width": 32, "direction": "output"},
                    {"name": "psel", "width": 1},
                    {"name": "penable", "width": 1},
                    {"name": "pwrite", "width": 1},
                ]
            }
        ],
        "registers": [
            {
                "name": "CTRL",
                "offset": "0x000",
                "description": "Control register",
                "fields": [
                    {"name": "enable", "bits": "0", "access": "rw", "reset": "0",
                     "desc": "Enable bit"}
                ]
            },
            {
                "name": "STATUS",
                "offset": "0x004",
                "description": "Status register",
                "fields": [
                    {"name": "ready", "bits": "0", "access": "ro", "reset": "0",
                     "desc": "Ready flag"}
                ]
            }
        ],
        "verification": {
            "test_scenarios": [
                {
                    "name": "basic_ctrl_write",
                    "description": "Write to CTRL register",
                    "detail": "Write CTRL with 0x1\n"
                }
            ],
            "coverage_goals": {
                "toggle": 90
            }
        },
        "fsm": None
    }
    spec_path = os.path.join(tmp_output_dir, "test_spec.yml")
    with open(spec_path, "w") as f:
        yaml.dump(spec, f, default_flow_style=False)
    return spec_path


@pytest.fixture
def sample_spec_data(sample_spec_path):
    """Load and return normalized spec data via template_engine.build_spec_data."""
    from pipeline.template_engine import build_spec_data
    return build_spec_data(sample_spec_path)
