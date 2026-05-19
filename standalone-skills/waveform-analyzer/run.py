#!/usr/bin/env python3
"""
waveform-analyzer — Simulation Results Analysis Engine.

Analyzes simulation logs, waveform dumps, and coverage databases to
extract pass/fail metrics, coverage percentages, and failure classifications.
Post-simulation analysis for verification closure assessment.

Usage:
    python run.py --log sim_results/sim.log
    python run.py --log sim.log --vcd output.vcd --report coverage_report.json
    python run.py --help
"""
import sys
import os
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = Path(".")  # Default output directory for generated reports


# ── Log Parser ─────────────────────────────────────────────────────────────────

class SimulationLogParser:
    """
    Parse simulation log files to extract pass/fail counts, UVM messages,
    coverage percentages, and runtime statistics.
    """

    def __init__(self, log_path: str):
        """
        Initialize parser with path to simulation log file.

        Args:
            log_path: Path to the simulation log file.
        """
        self.path = Path(log_path)
        self.lines: List[str] = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.uvm_errors: List[Dict] = []      # UVM_ERROR messages with timestamps
        self.uvm_fatals: List[Dict] = []      # UVM_FATAL messages with timestamps
        self.coverage_percent: Optional[float] = None  # Overall functional coverage
        self.coverage_by_group: Dict[str, float] = {}  # Per-covergroup coverage
        self.warnings: List[str] = []          # Simulation runtime warnings
        self._parsed = False                   # Whether parsing has completed

    def parse(self) -> bool:
        """
        Parse the simulation log file for all metrics.

        Returns:
            True if parsing succeeded, False otherwise.
        """
        # Read: check file exists and read all lines
        if not self.path.exists():
            print(f"  [X] Log file not found: {self.path}")
            return False
        try:
            # Use latin-1 encoding for broad compatibility with EDA tools
            text = self.path.read_text(encoding="latin-1", errors="replace")
            self.lines = text.splitlines()
        except Exception as e:
            # Catch read failures (permission, binary, etc.)
            print(f"  [X] Failed to read log: {e}")
            return False

        # Parse: scan each line for known patterns
        for line in self.lines:
            # Count UVM_ERROR (but not UVM_ERROR macro definition)
            if "UVM_ERROR" in line and "uvm_error" in line.lower():
                self.uvm_errors.append({
                    "line": line.strip(),
                    "timestamp": self._extract_timestamp(line),
                })
            # Count UVM_FATAL
            if "UVM_FATAL" in line:
                self.uvm_fatals.append({
                    "line": line.strip(),
                    "timestamp": self._extract_timestamp(line),
                })
            # Detect test pass/fail counts from UVM summary
            if "# Tests :" in line or "Tests :" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        self.total_tests = int(parts[-1].strip())
                    except ValueError:
                        pass  # Non-numeric count, skip
            if "# PASSED :" in line or "PASSED :" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        self.passed_tests = int(parts[-1].strip())
                    except ValueError:
                        pass
            if "# FAILED :" in line or "FAILED :" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        self.failed_tests = int(parts[-1].strip())
                    except ValueError:
                        pass
            # Extract coverage percentage from typical UVM patterns
            cov_match = re.search(r"coverage\s*[:=]\s*(\d+\.?\d*)\s*%", line, re.IGNORECASE)
            if cov_match:
                try:
                    self.coverage_percent = float(cov_match.group(1))
                except ValueError:
                    pass
            # Per-covergroup coverage
            cg_match = re.search(r"covergroup\s+(\w+).*?(\d+\.?\d*)\s*%", line, re.IGNORECASE)
            if cg_match:
                try:
                    self.coverage_by_group[cg_match.group(1)] = float(cg_match.group(2))
                except ValueError:
                    pass
            # Track warnings
            if "Warning" in line or "warning" in line:
                self.warnings.append(line.strip())

        # Infer counts from UVM_ERROR/FATAL if explicit counts missing
        if self.total_tests == 0 and (self.uvm_errors or self.uvm_fatals):
            self.total_tests = max(len(self.uvm_errors), 1)

        self._parsed = True
        return True

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """
        Extract timestamp from a log line if present.

        Args:
            line: A single log line string.

        Returns:
            Timestamp string (e.g., "@12345") or None.
        """
        # Timestamp patterns: @12345, [12345], or time: 12345 ns
        ts = re.search(r"@(\d+)", line)
        if ts:
            return ts.group(0)
        ts = re.search(r"\[(\d+)\]", line)
        if ts:
            return ts.group(0)
        ts = re.search(r"time:\s*(\d+)\s*ns", line)
        if ts:
            return ts.group(0)
        return None

    def get_summary(self) -> Dict:
        """
        Build a summary dictionary from parsed results.

        Returns:
            Dictionary with test counts, errors, fatals, and coverage data.
        """
        if not self._parsed:
            return {"error": "Not parsed yet"}
        return {
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "uvm_errors": len(self.uvm_errors),
            "uvm_fatals": len(self.uvm_fatals),
            "coverage_percent": self.coverage_percent,
            "coverage_by_group": self.coverage_by_group,
            "warnings": len(self.warnings),
            "file": str(self.path),
        }


# ── Report Generator ──────────────────────────────────────────────────────────

def generate_report(log_summary: Dict, output_path: Path) -> bool:
    """
    Generate a structured JSON report from parsed log data.

    Args:
        log_summary: Dictionary from SimulationLogParser.get_summary().
        output_path: Path to write the JSON report file.

    Returns:
        True if report was written successfully, False on error.
    """
    try:
        # Build a structured report with metadata
        report = {
            "tool": "waveform-analyzer",
            "version": "1.0.0",
            "source": log_summary.get("file", "unknown"),
            "analysis": {
                "total_tests": log_summary.get("total_tests", 0),
                "passed": log_summary.get("passed_tests", 0),
                "failed": log_summary.get("failed_tests", 0),
                "pass_rate": 0.0,  # Will compute below
                "uvm_errors": log_summary.get("uvm_errors", 0),
                "uvm_fatals": log_summary.get("uvm_fatals", 0),
                "coverage_percent": log_summary.get("coverage_percent"),
                "coverage_by_group": log_summary.get("coverage_by_group", {}),
                "warnings": log_summary.get("warnings", 0),
            },
            "verdict": "unknown",
        }
        # Compute pass rate from available data
        total = report["analysis"]["total_tests"]
        passed = report["analysis"]["passed"]
        if total > 0:
            report["analysis"]["pass_rate"] = round(passed / total * 100, 1)
        # Determine verdict based on failures
        if report["analysis"]["failed"] > 0 or report["analysis"]["uvm_fatals"] > 0:
            report["verdict"] = "FAIL"
        elif report["analysis"]["uvm_errors"] > 0:
            report["verdict"] = "WARN"
        else:
            report["verdict"] = "PASS"

        # Write JSON with pretty formatting
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  [+] Report saved: {output_path}")
        return True
    except Exception as e:
        # Catch all I/O and encoding errors
        print(f"  [X] Failed to write report: {e}")
        return False


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main() -> int:
    """
    Entry point for waveform-analyzer CLI.

    Parses command-line arguments, runs log analysis, and generates reports.

    Returns:
        0 on success, 1 on error.
    """
    # Build argument parser with descriptions for each option
    parser = argparse.ArgumentParser(
        description="waveform-analyzer — Simulation Results Analysis Engine",
        epilog="Example: python run.py --log sim.log --report analysis.json",
    )
    # Input: path to simulation log file (required)
    parser.add_argument(
        "--log", "-l",
        type=str,
        required=True,
        help="Path to simulation log file for analysis",
    )
    # Input: optional VCD waveform path (for future enhancement)
    parser.add_argument(
        "--vcd", "-v",
        type=str,
        default=None,
        help="Optional path to VCD waveform file for signal analysis",
    )
    # Output: report file path
    parser.add_argument(
        "--report", "-r",
        type=str,
        default="coverage_report.json",
        help="Output report path (default: coverage_report.json)",
    )

    # Parse arguments — will exit with --help if no args given
    args = parser.parse_args()

    # Validate: log file must exist
    if not os.path.exists(args.log):
        print(f"  [X] Log file not found: {args.log}")
        return 1

    # Validate: report path should not be a directory
    report_path = Path(args.report)
    if report_path.is_dir():
        print(f"  [X] Report path is a directory: {args.report}")
        return 1

    print(f"  [*] Analyzing: {args.log}")

    # Step 1: Parse the simulation log
    log_parser = SimulationLogParser(args.log)
    if not log_parser.parse():
        # parse() already printed error details
        return 1

    # Step 2: Generate summary report
    summary = log_parser.get_summary()
    print(f"  [+] Tests: {summary['passed_tests']} passed / {summary['failed_tests']} failed"
          f" / {summary['total_tests']} total")
    print(f"  [+] UVM Errors: {summary['uvm_errors']}, Fatals: {summary['uvm_fatals']}")
    if summary.get("coverage_percent") is not None:
        print(f"  [+] Coverage: {summary['coverage_percent']:.1f}%")
    print(f"  [+] Warnings: {summary['warnings']}")

    # Step 3: Generate report file
    if not generate_report(summary, report_path):
        return 1

    print(f"  [✓] Analysis complete")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone entry point — called when run as `python run.py`
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    sys.exit(main())
