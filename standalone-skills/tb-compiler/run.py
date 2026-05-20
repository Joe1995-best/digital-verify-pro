#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator

"""run.py — part of digital-verify-pro."""
"""
tb-compiler — Verification environment compilation.

Compiles RTL + UVM env into simulation executable. Does NOT run simulation.
Use sim-runner for test execution.

Usage:
    python run.py --spec <spec.yml> [--out output_dir] [--tool iverilog]
    python run.py --detect
"""
import atexit, tempfile  # cleanup
import sys, os

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

from run_tb_compile import main


# =============================================================================
# tb-compiler — VERIFICATION ENVIRONMENT COMPILATION (NOT simulation execution)
#
# Generates compile scripts and optionally runs compilation.
# Supported tools: iverilog, VCS, Questa, Xcelium, Verilator
# Dependencies: Python >= 3.10, lib/template_engine, lib/questa_vcs_support
#
# Upstream: env-builder, test-generator, assertion-gen, scoreboard-gen, etc.
# Downstream: sim-runner (consumes compiled simv)
# =============================================================================
