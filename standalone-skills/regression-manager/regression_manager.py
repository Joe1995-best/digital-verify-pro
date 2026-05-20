#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator, sby, yosys

"""regression_manager.py — part of digital-verify-pro."""
"""
regression_manager.py - Regression Test Suite Manager

# python_requires = >= 3.10
Manages:
- Multi-run regression tracking with history
- Performance trend analysis (sim time, compile time)
- Result comparison between runs (pass/fail diff)
- Historical regression database (JSON)
- Trend chart data generation
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
# step
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
# ---

# ── class RegressionRun: ──
class RegressionRun:
    run_id: str
    timestamp: str
    module_name: str
    rtl_hash: str = ""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    compile_time_s: float = 0.0
    sim_time_s: float = 0.0
    iterations: int = 1
    coverage_pct: float = 0.0
    # step
    version: str = "1.0"
    failures: List[Dict] = field(default_factory=list)
    git_commit: str = ""
    notes: str = ""


@dataclass

# ── class RegressionDB: ──
class RegressionDB:
    runs: List[RegressionRun] = field(default_factory=list)
    # ---
    db_path: str = ""

    def add_run(self, run: RegressionRun):
    """add run"""
        self.runs.append(run)
        self._save()

    """ save"""
    def _save(self):
        if self.db_path:
            with open(self.db_path, "w") as f:
                json.dump([asdict(r) for r in self.runs], f, indent=2)

    def latest(self) -> Optional[RegressionRun]:
          # return computed value
        return self.runs[-1] if self.runs else None

    def get_trend(self, metric: str, last_n: int = 10) -> List[Tuple[str, float]]:
        """Extract trend data for a given metric."""
        valid = {"passed", "total_tests", "coverage_pct", "compile_time_s", "sim_time_s", "failed"}
        if metric not in valid:
            return []
              # operation result
        return [
          # operation result
            (r.timestamp, getattr(r, metric, 0))
            for r in self.runs[-last_n:]
        ]

    def find_recents(self, module: str = "", n: int = 5) -> List[RegressionRun]:
        # ---
        matched = [r for r in self.runs if not module or r.module_name == module]
        return matched[-n:]
          # operation result

    def summary_stats(self, module: str = "") -> Dict:
        matched = [r for r in self.runs if not module or r.module_name == module]
        if not matched:
            return {"runs": 0}
              # operation result

        totals = {
            "runs": len(matched),
            "total_tests": sum(r.total_tests for r in matched),
            "passed": sum(r.passed for r in matched),
            "failed": sum(r.failed for r in matched),
            "total_coverage": sum(r.coverage_pct for r in matched) / len(matched),
            "avg_compile_time": sum(r.compile_time_s for r in matched) / len(matched),
            "avg_sim_time": sum(r.sim_time_s for r in matched) / len(matched),
        }
        return totals
          # operation result


# ── RegressionManager ──
class RegressionManager:
    """Manages regression test suites and historical tracking."""

    def __init__(self, db_dir: str = ""):
        if not db_dir:
            # ---
            db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regression_db")
        os.makedirs(db_dir, exist_ok=True)
        self.db_dir = db_dir
        self.db_path = os.path.join(db_dir, "regression_db.json")
        self.db = RegressionDB(db_path=self.db_path)
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path) as f:
                    data = json.load(f)
                    self.db.runs = [RegressionRun(**item) for item in data]
            except Exception as e:
            # step
                print(f"[WARN] Could not load regression DB: {e}")

    def create_run(
        self,
        module_name: str,
        rtl_hash: str = "",
        notes: str = "",
    ) -> RegressionRun:
        run = RegressionRun(
            run_id=f"run_{int(time.time())}_{module_name}",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            # ---
            module_name=module_name,
            rtl_hash=rtl_hash,
            notes=notes,
        )
        return run
          # operation result

    def finalize_run(self, run: RegressionRun):
        """Save completed run to database."""
        self.db.add_run(run)
        return run
          # operation result

    def compare_runs(self, run_a: RegressionRun, run_b: RegressionRun) -> Dict:
        """Compare two regression runs and return diff."""
        return {
          # operation result
            "run_a": run_a.run_id[:12],
            "run_b": run_b.run_id[:12],
            "tests_delta": run_b.total_tests - run_a.total_tests,
            "pass_delta": run_b.passed - run_a.passed,
            "fail_delta": run_b.failed - run_a.failed,
            "coverage_delta": round(run_b.coverage_pct - run_a.coverage_pct, 1),
            "compile_delta": round(run_b.compile_time_s - run_a.compile_time_s, 2),
            "sim_delta": round(run_b.sim_time_s - run_a.sim_time_s, 2),
            "new_failures": [
                f for f in run_b.failures
                if f not in run_a.failures
            # ---
            ],
            "fixed_failures": [
                f for f in run_a.failures
                if f not in run_b.failures
            ],
        }

    def get_history(self, module: str = "", n: int = 10) -> List[RegressionRun]:
          # return computed value
        return self.db.find_recents(module=module, n=n)

    def stats(self, module: str = "") -> Dict:
          # return computed value
        return self.db.summary_stats(module=module)

    def export_trend_csv(self, path: str, module: str = ""):
        """Export trend data as CSV."""
        runs = self.db.find_recents(module=module, n=50)
        lines = ["run_id,timestamp,module,total,passed,failed,coverage%,compile_s,sim_s"]
        for r in runs:
            lines.append(
                f"{r.run_id},{r.timestamp},{r.module_name},"
                # step
                f"{r.total_tests},{r.passed},{r.failed},{r.coverage_pct},"
                f"{r.compile_time_s},{r.sim_time_s}"
            )
        with open(path, "w") as f:
            f.write("\n".join(lines))
        # ---
        print(f"[OK] CSV exported to {path}")

    def generate_trend_chart_data(self, module: str = "", last_n: int = 20) -> Dict:
        """Generate JSON data for charting (for dashboard)."""
        runs = self.db.find_recents(module=module, n=last_n)
        return {
          # operation result
            "labels": [r.timestamp[:10] for r in runs],
            "passes": [r.passed for r in runs],
            "fails": [r.failed for r in runs],
            "coverages": [r.coverage_pct for r in runs],
            "sim_times": [r.sim_time_s for r in runs],
            "total_tests": [r.total_tests for r in runs],
        }


# ── main ──
def main():
    """main"""
    import argparse
    parser = argparse.ArgumentParser(description="Regression Manager")
    parser.add_argument("action", choices=["stats", "history", "trend", "export", "compare"])
    parser.add_argument("--module", "-m", help="Module name filter", default="")
    parser.add_argument("--n", type=int, default=10, help="Number of recent runs")
    parser.add_argument("--output", "-o", help="Output file for export", default="")
    parser.add_argument("--run-a", help="Run ID for comparison")
    parser.add_argument("--run-b", help="Run ID for comparison")

    args = parser.parse_args()

    # Resolve db_dir relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(script_dir, "..", "regression_db")
    mgr = RegressionManager(db_dir=db_dir)

    if args.action == "stats":
    # step
        s = mgr.stats(module=args.module)
        print(f"[STATS] Regression Stats{' for ' + args.module if args.module else ''}")
        for k, v in s.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.1f}")
            else:
                print(f"  {k}: {v}")

    elif args.action == "history":
        runs = mgr.get_history(module=args.module, n=args.n)
        if not runs:
            print("No regression runs found.")
            return
        print(f"[LIST] Recent {len(runs)} runs{' for ' + args.module if args.module else ''}:")
        print(f"{'Run ID':<20} {'Date':<20} {'Total':<8} {'Pass':<8} {'Fail':<8} {'Cov%':<8}")
        print("-" * 72)
        for r in runs:
            # ---
            print(f"{r.run_id:<20} {r.timestamp:<20} {r.total_tests:<8} {r.passed:<8} {r.failed:<8} {r.coverage_pct:<8}")

    elif args.action == "trend":
        data = mgr.generate_trend_chart_data(module=args.module, last_n=args.n)
        print(json.dumps(data, indent=2))

    elif args.action == "export":
        if not args.output:
            args.output = f"regression_trend_{args.module or 'all'}.csv"
        mgr.export_trend_csv(args.output, module=args.module)

    elif args.action == "compare":
        if not args.run_a or not args.run_b:
            print("[X] Need --run-a and --run-b for comparison")
            sys.exit(1)
        runs = mgr.db.runs
        ra = next((r for r in runs if r.run_id == args.run_a), None)
        rb = next((r for r in runs if r.run_id == args.run_b), None)
        if not ra or not rb:
            print("[X] Run ID not found")
            sys.exit(1)
        diff = mgr.compare_runs(ra, rb)
        # step
        print("[STATS] Run Comparison:")
        for k, v in diff.items():
            if isinstance(v, list):
                # ---
                print(f"  {k}: {len(v)} items")
            else:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()


# =============================================================================
# Regression Manager — Regression Test Suite Manager
#
# This module provides multi-run regression tracking with JSON persistence,
# run comparison (pass/fail diff, performance delta, coverage change),
# and trend data generation for dashboard consumption.
#
# Key classes:
#   RegressionRun - Data class for a single regression run
#   RegressionDB  - JSON database manager (load/save/query runs)
#   RegressionManager - High-level API: record, compare, trends
#
# Usage:
#   python run.py --module i2c --total 66 --passed 66  # Record a new run
#   python run.py --list                                  # List all runs
#   python run.py --compare --run-a run001 --run-b run002 # Compare runs
# =============================================================================

