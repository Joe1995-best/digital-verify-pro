#!/usr/bin/env python3
"""regression-manager — Regression test suite tracker and analyzer."""
import sys, os
_d = os.path.dirname(os.path.abspath(__file__))
if _d not in sys.path: sys.path.insert(0, _d)
from regression_manager import main
if __name__ == "__main__": sys.exit(main())


# =============================================================================
# regression-manager — Regression test suite tracker
#
# Manages multi-run regression tracking with history, performance trends,
# pass/fail comparison between runs, and historical database (JSON).
#
# Key functions:
#   main() - CLI entry point (record, list, compare, trends)
#
# Dependencies: Python >= 3.10
# =============================================================================
