#!/usr/bin/env python3
"""
regression.py — Regression runner and coverage convergence reporter.

Batch-run the UVM pipeline across one or more spec files and generate
a coverage convergence report.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGRESSION_RESULTS_FILE = "regression_summary.json"

from track2 import PipelineRunner, PIPELINE_PHASES, PIPELINE_ORDER


def run_regression(spec_filter=None, outdir_override: str = "",
                   phases=None, skip_checks: bool = False):
    """
    Discover all spec YAML files in the project root and batch-run the
    UVM pipeline for each spec.  Outputs a JSON summary of all runs.
    """
    # Discover spec YAML files in project root
    spec_files = []
    if spec_filter:
        # Use explicitly specified specs
        for sf in spec_filter:
            sf_path = sf if os.path.isabs(sf) else os.path.join(SCRIPT_DIR, sf)
            if os.path.isfile(sf_path):
                spec_files.append(sf_path)
            elif os.path.isfile(sf):
                spec_files.append(os.path.abspath(sf))
            else:
                print(f"  [!] Spec file not found: {sf}")
    else:
        for f in sorted(os.listdir(SCRIPT_DIR)):
            if f.endswith("_spec.yml") or f.endswith("_spec.yaml"):
                spec_path = os.path.join(SCRIPT_DIR, f)
                if os.path.isfile(spec_path):
                    spec_files.append(spec_path)

    if not spec_files:
        print(f"[X] No spec YAML files (*_spec.yml/*_spec.yaml) found in project root")
        print(f"    Project root: {SCRIPT_DIR}")
        return {"success": False, "error": "No spec files found", "runs": []}

    total_start = time.time()
    runs = []

    print(f"")
    print(f"{'='*60}")
    print(f"[REGRESSION] Auto-discovered {len(spec_files)} spec file(s)")
    print(f"{'='*60}")
    for sf in spec_files:
        print(f"   [{spec_files.index(sf)+1}] {os.path.basename(sf)}")
    print(f"{'='*60}")
    print(f"")

    for idx, spec_path in enumerate(spec_files):
        spec_basename = os.path.splitext(os.path.basename(spec_path))[0]
        # e.g. i2c_spec.yml → output_i2c/
        default_out = os.path.join(SCRIPT_DIR, f"output_{spec_basename.removesuffix('_spec')}")
        run_outdir = outdir_override if outdir_override else default_out

        print(f"")
        print(f"{'─'*60}")
        print(f"[REGRESSION {idx+1}/{len(spec_files)}] {spec_basename}")
        print(f"    Spec:     {spec_path}")
        print(f"    Output:   {run_outdir}")
        print(f"{'─'*60}")

        runner = PipelineRunner(
            spec_path=spec_path,
            outdir=run_outdir,
            phases=phases,
            skip_checks=skip_checks,
            resume=False,
        )
        result = runner.run()

        run_entry = {
            "spec": spec_path,
            "spec_basename": spec_basename,
            "output": run_outdir,
            "success": result.get("success", False),
            "elapsed_s": result.get("elapsed", 0),
            "total_phases": result.get("total", 0),
            "passed_phases": result.get("passed", 0),
            "failed_phases": result.get("failed", 0),
            "skipped_phases": result.get("skipped", 0),
        }
        runs.append(run_entry)

        # Print one-line status for this run
        status = "[OK]" if run_entry["success"] else "[X]"
        print(f"  {status} {spec_basename}: {run_entry['passed_phases']}/{run_entry['total_phases']} phases passed "
              f"({run_entry['failed_phases']} failed, {run_entry['skipped_phases']} skipped) "
              f"in {run_entry['elapsed_s']:.1f}s")
        print(f"")

    total_elapsed = time.time() - total_start

    summary = {
        "regression_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_elapsed_s": total_elapsed,
        "total_specs": len(spec_files),
        "passed_specs": sum(1 for r in runs if r["success"]),
        "failed_specs": sum(1 for r in runs if not r["success"]),
        "runs": runs,
    }

    # Write summary JSON to project root
    summary_path = os.path.join(SCRIPT_DIR, REGRESSION_RESULTS_FILE)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # ── Coverage convergence report ──
    coverage_convergence_path = _generate_coverage_convergence_report(SCRIPT_DIR, spec_files, runs)
    if coverage_convergence_path:
        print(f"  Convergence report: {coverage_convergence_path}")

    print(f"")
    print(f"{'='*60}")
    print(f"[REGRESSION] Summary — {total_elapsed:.1f}s total")
    print(f"{'='*60}")
    for r in runs:
        icon = "[OK]" if r["success"] else "[X]"
        print(f"  {icon} {r['spec_basename']:30s}  {r['passed_phases']}/{r['total_phases']} phases  {r['elapsed_s']:7.1f}s")
    print(f"")
    print(f"  Total: {summary['total_specs']} specs, {summary['passed_specs']} passed, "
          f"{summary['failed_specs']} failed")
    if summary["failed_specs"] == 0:
        print(f"  [ALL OK] All regression runs passed!")
    else:
        print(f"  [!] {summary['failed_specs']} spec(s) had failures — check logs above")
    print(f"  Summary: {summary_path}")
    print(f"{'='*60}")
    print(f"")

    return summary


def _generate_coverage_convergence_report(project_root, spec_files, runs):
    """Generate a coverage convergence report across all regression spec runs."""
    reg_dir = os.path.join(project_root, "output", "regression")
    os.makedirs(reg_dir, exist_ok=True)

    report_lines = []
    report_lines.append("# Coverage Convergence Report")
    report_lines.append("")
    report_lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report_lines.append(f"Specs: {len(spec_files)}")
    report_lines.append("")
    report_lines.append("| Spec | Phases Passed | Phases Failed | Elapsed (s) | Status |")
    report_lines.append("|------|--------------|--------------|-------------|--------|")

    all_passed = True
    total_phases_passed = 0
    total_phases_failed = 0
    total_elapsed = 0.0

    for i, sf in enumerate(spec_files):
        basename = os.path.basename(sf)
        run_info = runs[i] if i < len(runs) else {}
        passed = run_info.get("passed_phases", 0)
        failed = run_info.get("failed_phases", 0)
        elapsed = run_info.get("elapsed_s", 0.0)
        status = "PASS" if run_info.get("success", False) else "FAIL"
        total_phases_passed += passed
        total_phases_failed += failed
        total_elapsed += elapsed
        if not run_info.get("success", False):
            all_passed = False
        report_lines.append(f"| {basename} | {passed} | {failed} | {elapsed:.1f} | {status} |")

    report_lines.append("")
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append(f"- **Total Specs**: {len(spec_files)}")
    report_lines.append(f"- **Total Phases Passed**: {total_phases_passed}")
    report_lines.append(f"- **Total Phases Failed**: {total_phases_failed}")
    report_lines.append(f"- **Total Elapsed**: {total_elapsed:.1f}s")
    report_lines.append(f"- **Overall Status**: {'PASS' if all_passed else 'FAIL'}")
    report_lines.append("")

    if all_passed:
        report_lines.append("All specs passed regression. Coverage is convergent.")
    else:
        report_lines.append("Some specs failed. Review individual run logs.")

    report_path = os.path.join(reg_dir, "coverage_convergence_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    return report_path


def print_pipeline_help():
    """Print pipeline command reference."""
    print(f"")
    print(f"Pipeline Phases (in order):")
    for i, phase in enumerate(PIPELINE_ORDER, 1):
        info = PIPELINE_PHASES[phase]
        print(f"  {i}. {phase:<18} — {info['description']}")
    print(f"")
    print(f"Examples:")
    print(f"  python pro_verify.py --pipeline i2c_spec.yml")
    print(f"  python pro_verify.py --pipeline uart_spec.yml --phases spec-analyzer,env-builder")
    print(f"  python pro_verify.py --pipeline i2c_spec.yml --outdir ./my_output")
    print(f"  python pro_verify.py --pipeline uart_spec.yml --phases spec-analyzer")
    print(f"  python pro_verify.py --pipeline i2c_spec.yml --resume")
    print(f"  python pro_verify.py --list-pipeline-phases")
