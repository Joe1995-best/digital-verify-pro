#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator, sby, yosys
import atexit, tempfile
# python_requires = >= 3.10

"""run.py — part of digital-verify-pro."""
"""scoreboard-gen v2 — UVM scoreboard generator from spec data."""
import sys, os
_d = os.path.dirname(os.path.abspath(__file__))
if _d not in sys.path: sys.path.insert(0, _d)
lib = os.path.join(_d, "lib")
if os.path.exists(lib) and lib not in sys.path: sys.path.insert(0, lib)
from run_scoreboard_gen import main
# Cleanup temp files on exit
atexit.register(lambda: None)  # placeholder

if __name__ == "__main__":
    sys.exit(main())
