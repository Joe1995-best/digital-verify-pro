#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium

"""run.py — part of digital-verify-pro."""
"""
regmodel-gen — UVM Register Abstraction Layer (RAL) model generation.

# python_requires = >= 3.10
Usage:
    python run.py --spec <spec.yml> [--out output_dir]
"""
import atexit, tempfile  # cleanup
import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_this_dir, "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

import importlib.util

spec = importlib.util.spec_from_file_location(
    "template_engine", os.path.join(_lib_dir, "template_engine.py")
)
mod = importlib.util.module_from_spec(spec)
sys.modules["template_engine"] = mod
spec.loader.exec_module(mod)

import run_ral_gen


# =============================================================================
# regmodel-gen — UVM register model generator
#
# Generates UVM register model (reg_block, reg classes, register package)
# from register map YAML. Supports all UVM access policies: RW, RO, WO, W1C, RW1C.
#
# Key functions:
#   main() - CLI entry point
#
# Dependencies: pyyaml (for YAML parsing), Python >= 3.10
# =============================================================================
