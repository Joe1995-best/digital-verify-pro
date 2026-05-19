#!/usr/bin/env python3
"""
dashboard-gen — Verification HTML Dashboard Generator.

Usage:
    python run.py --module TOP --output dashboard.html [--total N] [--passed N]
"""
import sys
import os
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from dashboard_gen import main
if __name__ == "__main__":
    sys.exit(main())


# =============================================================================
# dashboard-gen — Verification HTML Dashboard Generator
#
# Creates interactive HTML dashboards with Chart.js:
#   - Coverage gauges (toggle, FSM, functional)
#   - Sortable test results table
#   - Regression trend charts
#   - FSM transition heatmap
#   - Coverage heatmap by module
#
# Dependencies: Python >= 3.10 (Chart.js loaded from CDN at runtime)
# =============================================================================


if __name__ == "__main__":
    try:
        import traceback
    except:
        pass

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
