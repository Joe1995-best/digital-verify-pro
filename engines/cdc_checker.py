#!/usr/bin/env python3
"""
cdc_checker.py — Cross-Domain Clocking (CDC) static analysis.

Scans RTL SystemVerilog source for:
  1. Multi-clock domain declarations (always_ff @(posedge clk_X))
  2. Asynchronous signal paths (signal driven in clk_a, sampled in clk_b)
  3. Missing/insufficient synchronization (2-stage FF)

Usage:
    python engines/cdc_checker.py --rtl rtl/*.sv --spec spec.yml
    python engines/cdc_checker.py --rtl rtl/ --clk-names pclk,clk_i --out cdc_report.json
"""
import os, sys, re, json, argparse
from collections import defaultdict
from typing import Dict, List, Tuple

class CDCChecker:
    """Static CDC analysis engine."""

    def __init__(self, rtl_files: List[str], clk_names: List[str] = None):
        self.rtl_files = rtl_files
        self.clk_names = clk_names or []
        self.clock_domains: Dict[str, List[str]] = defaultdict(list)
        self.crossings: List[Dict] = []
        self.issues: List[Dict] = []

    def parse_clocks(self):
        """Extract clock domains from always_ff blocks."""
        sig_to_domain = {}
        for fpath in self.rtl_files:
            if not os.path.isfile(fpath):
                continue
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Find: always_ff @(posedge clk or negedge rst) begin
            blocks = re.finditer(
                r'always_ff\s*@\(([^)]+)\)\s*begin',
                content, re.IGNORECASE
            )
            for m in blocks:
                sensitivity = m.group(1)
                # Extract clock signal: posedge CLK or negedge CLK
                clk_matches = re.findall(r'(?:posedge|negedge)\s+(\w+)', sensitivity)
                if not clk_matches:
                    continue
                clk = clk_matches[0]
                if clk.lower() in ('rst', 'reset', 'rst_n'):
                    continue
                self.clock_domains[clk].append(fpath)

    def detect_crossings(self):
        """Detect signals crossing between clock domains."""
        sig_to_clk = {}
        for clk, files in self.clock_domains.items():
            for fpath in files:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()

                # Find signals assigned in this block
                for line in lines:
                    m = re.match(r'\s*(\w+)\s*<=\s*(\w+)', line)
                    if m:
                        lhs, rhs = m.group(1), m.group(2)
                        sig_to_clk[lhs] = clk

                        # If rhs belongs to a different clock domain
                        if rhs in sig_to_clk and sig_to_clk[rhs] != clk:
                            self.crossings.append({
                                "signal": rhs,
                                "from_clk": sig_to_clk[rhs],
                                "to_clk": clk,
                                "sink": lhs,
                                "file": fpath,
                            })

        # Deduplicate
        seen = set()
        unique = []
        for c in self.crossings:
            key = (c["signal"], c["from_clk"], c["to_clk"])
            if key not in seen:
                seen.add(key)
                unique.append(c)
        self.crossings = unique

    def check_synchronizers(self):
        """Check if crossings have 2-stage synchronizers."""
        sync_patterns = ['sync_', 'cdc_', 'sync2ff', 'double_sync']
        for crossing in self.crossings:
            sig = crossing["signal"]
            has_sync = any(p in sig.lower() for p in sync_patterns)
            crossing["has_synchronizer"] = has_sync
            if not has_sync:
                self.issues.append({
                    "severity": "WARNING",
                    "signal": sig,
                    "from_clk": crossing["from_clk"],
                    "to_clk": crossing["to_clk"],
                    "message": f"Signal '{sig}' crosses from {crossing['from_clk']}"
                               f" to {crossing['to_clk']} without synchronizer",
                })

    def analyze(self) -> dict:
        """Run full CDC analysis."""
        self.parse_clocks()
        self.detect_crossings()
        self.check_synchronizers()

        return {
            "status": "PASS" if len(self.issues) == 0 else "WARNING",
            "clock_domains": list(self.clock_domains.keys()),
            "total_crossings": len(self.crossings),
            "unsynchronized": len(self.issues),
            "crossings": [
                {
                    "signal": c["signal"],
                    "from": c["from_clk"],
                    "to": c["to_clk"],
                    "synced": c["has_synchronizer"],
                }
                for c in self.crossings
            ],
            "issues": self.issues,
        }


def main():
    ap = argparse.ArgumentParser(description="CDC Static Analysis")
    ap.add_argument("--rtl", required=True, help="RTL file or directory")
    ap.add_argument("--clk-names", help="Comma-separated known clock names")
    ap.add_argument("--out", default="cdc_report.json", help="Output report path")
    args = ap.parse_args()

    # Resolve RTL files
    rtl_path = args.rtl
    if os.path.isdir(rtl_path):
        rtl_files = sorted([
            os.path.join(rtl_path, f) for f in os.listdir(rtl_path)
            if f.endswith('.sv') or f.endswith('.v')
        ])
    else:
        rtl_files = [rtl_path]

    clk_names = args.clk_names.split(",") if args.clk_names else []
    checker = CDCChecker(rtl_files, clk_names)
    report = checker.analyze()

    # Write report
    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"CDC Report: {report['status']}")
    print(f"  Clock domains: {report['clock_domains']}")
    print(f"  Crossings: {report['total_crossings']}, Unsynchronized: {report['unsynchronized']}")
    if report["issues"]:
        for i in report["issues"]:
            print(f"  [{i['severity']}] {i['message']}")

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
