#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator, sby, yosys
import atexit, tempfile

"""run.py — part of digital-verify-pro."""
"""
coverage-engine — Standalone VCD toggle coverage analysis.

Usage:
    python run.py --vcd <vcd_file> [--report report.json] [--markdown]
"""
import sys
import os

# Add this directory to path for clean import
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from coverage_engine import main

# Cleanup temp files on exit
atexit.register(lambda: None)  # placeholder

if __name__ == "__main__":
    sys.exit(main())
