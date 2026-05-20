#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium

"""run.py — part of digital-verify-pro."""
"""
sim-runner — Simulation execution and result collection.

Runs pre-compiled simv with test sequences, collects pass/fail results.
Does NOT compile — use tb-compiler for compilation.

Usage:
    python run.py --spec <spec.yml> [--out output_dir] [--test <name>]
    python run.py --spec <spec.yml> --all
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

from run_sim import main


# =============================================================================
# sim-runner — SIMULATION EXECUTION ONLY
#
# Runs compiled simv with test sequences, collects results, produces VCD.
# Supported tools: iverilog, VCS, Questa, Xcelium
# Dependencies: Python >= 3.10, lib/template_engine, lib/questa_vcs_support
#
# Depends on: tb-compiler (provides compiled simv)
# Downstream: waveform-analyzer, coverage-engine, doc-gen
# =============================================================================
