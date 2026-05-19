#!/usr/bin/env python3
"""scoreboard-gen v2 — UVM scoreboard generator from spec data."""
import sys, os
_d = os.path.dirname(os.path.abspath(__file__))
if _d not in sys.path: sys.path.insert(0, _d)
lib = os.path.join(_d, "lib")
if os.path.exists(lib) and lib not in sys.path: sys.path.insert(0, lib)
from run_scoreboard_gen import main
if __name__ == "__main__":
    sys.exit(main())
