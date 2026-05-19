#!/usr/bin/env python3
"""
review_to_checklist.py — Bridge review findings into verification checklist.

Usage:
    python tools/review_to_checklist.py \\
        --review output/review_report.json \\
        --output bug-list.md

Converts review CRITICAL/HIGH findings into checklist-ready bug entries.
"""
import json, sys, os
from pathlib import Path
from datetime import datetime

# Rule → Phase mapping
RULE_PHASE = {
    "FIFO_RD_STUCK": "Phase 4 (SIM)",
    "FIFO_PORT_UNCONNECTED": "Phase 3 (RTL-GEN)",
    "HW_PORT_ZOMBIE": "Phase 3 (RTL-GEN)",
    "DUAL_ASSIGN_OVERRIDE": "Phase 1+3 (DSR+RTL-GEN)",
    "W1C_ON_WIRE": "Phase 5 (CCR)",
    "NO_TOGGLE_GAP": "Phase 5 (CCR)",
}

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Review → Checklist bridge")
    ap.add_argument("--review", "-r", required=True, help="Review JSON report")
    ap.add_argument("--output", "-o", default="bug-list.md", help="Output bug list")
    args = ap.parse_args()

    with open(args.review, encoding="utf-8") as f:
        report = json.load(f)

    findings = []
    for fp, fs in report.get("findings", {}).items():
        for f in fs:
            if f["severity"] in ("critical", "high"):
                findings.append({
                    "file": fp,
                    "line": f["line"],
                    "rule": f["rule"],
                    "msg": f["message"],
                    "phase": RULE_PHASE.get(f["rule"], "Phase 5 (CCR)"),
                    "severity": f["severity"],
                })

    findings.sort(key=lambda x: x["severity"] == "critical", reverse=True)

    lines = [
        "# Bug List (auto-generated from review)",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Source: {args.review}",
        f"Total findings: {len(findings)}",
        "",
        "| ID | Type | Rule | Description | File | Line | Phase | Fix Status |",
        "|----|:----:|:----:|-------------|:----:|:----:|:----:|:----------:|",
    ]

    for i, f in enumerate(findings, 1):
        sev = "RTL" if f["severity"] == "critical" else "ARCH"
        lines.append(
            f"| BUG-{i:03d} | {sev} | {f['rule']} | {f['msg'][:60]} "
            f"| {Path(f['file']).name} | {f['line']} "
            f"| {f['phase']} | :x: 待修复 |"
        )

    output = args.output
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  [OK] Bug list: {output} ({len(findings)} findings)")


if __name__ == "__main__":
    main()
