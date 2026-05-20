#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator
import atexit, tempfile

"""run.py — part of digital-verify-pro."""
"""
plan-generator — RTL deep analysis and verification plan generation.

Usage:
    python run.py <rtl_file> [--spec text] [--output file] [--json]
"""
import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from plan_generator import main

# Cleanup temp files on exit
atexit.register(lambda: None)  # placeholder

if __name__ == "__main__":
    sys.exit(main())


# =============================================================================
# plan-generator — RTL deep analysis and verification plan generation
#
# Key capabilities:
#   - FSM extraction and encoding detection
#   - Differentiated test scenario generation
#   - Coverage closure planning from VCD toggle data
#
# Dependencies: Python >= 3.10
# =============================================================================
