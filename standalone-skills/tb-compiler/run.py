#!/usr/bin/env python3
"""
tb-compiler — Verification environment compilation.

Usage:
    python run.py --spec <spec.yml> [--out output_dir] [--tool questa|vcs|xcelium]
"""
import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_this_dir, "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

import importlib.util

def _monkey_patch(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)

for fname in ["template_engine.py", "questa_vcs_support.py"]:
    fpath = os.path.join(_lib_dir, fname)
    if os.path.exists(fpath):
        _monkey_patch(fname.replace(".py", ""), fpath)

from run_sim import main


# =============================================================================
# tb-compiler — Verification environment compilation
#
# Generates Makefile/CMakeLists.txt/TCL scripts for EDA tool compilation.
# Handles UVM package compilation, DUT RTL, testbench, and elaboration.
#
# Supported tools: VCS, Xcelium, Questa, Verilator, Icarus
# Dependencies: Python >= 3.10, lib/template_engine, lib/questa_vcs_support
# =============================================================================
