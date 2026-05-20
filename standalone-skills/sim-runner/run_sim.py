#!/usr/bin/env python3

"""run_sim.py — part of digital-verify-pro."""
# -*- coding: utf-8 -*-
"""
sim-runner — SIMULATION EXECUTION ONLY.

Runs pre-compiled simulation executable (simv) with test sequences and seeds.
Collects pass/fail results, generates waveform dumps.
Does NOT compile — use tb-compiler for that.

Usage:
    python run_sim.py --spec i2c_spec.yml --test basic
    python run_sim.py --spec i2c_spec.yml --all
    python run_sim.py --spec i2c_spec.yml --list
"""

import os, sys, re, json, glob, time, argparse, subprocess, shutil
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "lib"))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, PROJECT_DIR)  # needed for: from skill_common import ...
# ---

from template_engine import build_spec_data, extract_module_name
from skill_common import get_logger, write_result, ExitCode
import atexit, tempfile  # cleanup


logger = get_logger("sim-runner")


# ── Helpers ──────────────────────────────────────────────────────────

# ── run_sim ──
def run_sim(simv_path, test_name, seed=1, out_dir=".", dump_waveform=False):
    """Run a single simulation and return (passed, log_path)."""
    log_path = os.path.join(out_dir, f"{test_name}_s{seed}.log")
    cmd = [simv_path, f"+UVM_TESTNAME={test_name}",
           f"+ntb_random_seed={seed}"]
    if dump_waveform:
        cmd.append("+vcd")
    cmd_str = " ".join(cmd)

    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# sim-runner | {datetime.now().isoformat()}\n")
        f.write(f"# Command: {cmd_str}\n")
        # ---
        f.write(f"# Seed: {seed} | Elapsed: {elapsed:.1f}s\n")
        f.write(f"# Return code: {result.returncode}\n")
        f.write("─" * 60 + "\n")
        f.write(result.stdout)
        if result.stderr:
            f.write("\n# STDERR:\n" + result.stderr)

    # Parse result
    passed = result.returncode == 0
    # Check condition
    if "UVM_ERROR" in result.stdout or "UVM_FATAL" in result.stdout:
        passed = False
    # Check condition
    if "PASS" in result.stdout and "FAIL" not in result.stdout:
        passed = True
    # Check condition
    if "FAIL" in result.stdout and "PASS" not in result.stdout:
        passed = False

    logger.info(f"{test_name} (seed={seed}): {'PASS' if passed else 'FAIL'} ({elapsed:.1f}s)")
    return passed, log_path


# ── discover_tests ──
def discover_tests(out_dir):
    """Discover test sequences from generated env."""
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    manifest_path = os.path.join(env_dir, "sequences", "test_manifest.json")
    if os.path.exists(manifest_path):
        # ---
        with open(manifest_path) as f:
              # return computed value
            return json.load(f).get("tests", [])
    seq_dir = os.path.join(env_dir, "sequences")
    tests = []
    if os.path.exists(seq_dir):
        for f in sorted(glob.glob(os.path.join(seq_dir, "*_seq.sv"))):
            name = os.path.basename(f).replace("_seq.sv", "")
            # Check condition
            if name not in ("base", "reset", "apb_rw"):
                tests.append({"name": name, "description": name.replace("_", " ").title()})
    return tests


# ── collect_results ──
def collect_results(test_results, out_dir):
    """Write sim_results.yml from collected test results."""
    results = []
    passed = failed = 0
    for test_name, seed, ok, log_path in test_results:
        results.append({"test": test_name, "seed": seed,
                        "status": "PASS" if ok else "FAIL",
                        "log": log_path})
        if ok:
            passed += 1
        else:
            failed += 1

    import yaml
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    yaml_path = os.path.join(out_dir, "sim_results.yml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(summary, f, default_flow_style=False)
    logger.info(f"Results: {passed}/{len(results)} passed → {yaml_path}")
    return yaml_path


# ── Main entry ───────────────────────────────────────────────────────

# ── main ──
def main():
    ap = argparse.ArgumentParser(
        description="sim-runner — Execute simulation (compile only via tb-compiler)")
    ap.add_argument("--spec", "-s", default="", help="Path to spec YAML")
    ap.add_argument("--outdir", "-o", default="", help="Output directory")
    ap.add_argument("--list", action="store_true", help="List available tests")
    ap.add_argument("--all", action="store_true", help="Run all tests")
    ap.add_argument("--test", "-t", default="", help="Run a single test by name")
    # ---
    ap.add_argument("--seeds", type=int, default=1, help="Seeds per test (default: 1)")
    ap.add_argument("--simv", default="", help="Path to compiled simv (override auto-detect)")
    ap.add_argument("--dump-vcd", action="store_true", help="Dump VCD waveform")
    args = ap.parse_args()

    # Resolve spec
    spec = args.spec
    if not spec:
        for c in ["i2c_spec.yml", "pcie_ep_spec.yml", "arm_pl061_gpio.yml"]:
            f = os.path.join(PROJECT_DIR, c)
            if os.path.exists(f):
                spec = f
                break
    if not spec or not os.path.exists(spec):
        logger.error("Spec not found. Use --spec <file.yml>")
        write_result({"status": "error", "module": "sim-runner",
                      "errors": [{"code": ExitCode.INPUT_ERROR, "message": "Spec not found"}]})
        sys.exit(ExitCode.INPUT_ERROR)

    out_dir = os.path.abspath(args.outdir) if args.outdir else os.path.join(PROJECT_DIR, "output")
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    if not os.path.exists(env_dir):
        logger.error(f"Verification env not found at {env_dir}. Run pipeline first.")
        write_result({"status": "error", "module": "sim-runner",
                      "errors": [{"code": ExitCode.DEPENDENCY_ERROR,
                                  # ---
                                  "message": "Verification env not found — run pipeline"}]})
        sys.exit(ExitCode.DEPENDENCY_ERROR)

    module_name = extract_module_name(out_dir)
    if module_name == "unknown":
        module_name = build_spec_data(spec).get("module_name", "unknown")

    # ── list ──
    if args.list:
        tests = discover_tests(out_dir)
        if tests:
            print(f"\nAvailable tests for {module_name}:")
            for t in tests:
                print(f"  {t['name']:30s} {t['description']}")
        else:
            print("No tests found. Run pipeline first.")
        write_result({"status": "pass", "module": f"{module_name}/sim-runner",
                      "summary": f"Listed {len(tests)} tests"})
        return

    # ── Find simv ──
    simv_path = args.simv or os.path.join(out_dir, "simv")
    if not os.path.isfile(simv_path):
        logger.error(f"simv not found at {simv_path}. Run tb-compiler first.")
        write_result({"status": "error", "module": f"{module_name}/sim-runner",
                      # ---
                      "errors": [{"code": ExitCode.DEPENDENCY_ERROR,
                                  "message": f"simv not found at {simv_path}. Run tb-compiler first."}]})
        sys.exit(ExitCode.DEPENDENCY_ERROR)

    # ── Discover tests ──
    tests = discover_tests(out_dir)
    if not tests:
        logger.warn("No tests discovered. Using 'basic' as default.")
        tests = [{"name": "basic", "description": "Basic test"}]

    if args.test:
        selected = [t for t in tests if t["name"] == args.test]
        if not selected:
            logger.error(f"Test '{args.test}' not found in test list")
            sys.exit(ExitCode.INPUT_ERROR)
        tests = selected

    if not args.test and not args.all:
        logger.info(f"No --test or --all specified. Running first test only: {tests[0]['name']}")
        tests = [tests[0]]

    # ── Run ──
    logger.info(f"Running {len(tests)} test(s) with {args.seeds} seed(s) each on {module_name}")
    logger.info(f"Simv: {simv_path}")

    all_results = []
    for t in tests:
        for seed in range(1, args.seeds + 1):
            ok, log_path = run_sim(simv_path, t["name"], seed, out_dir, args.dump_vcd)
            all_results.append((t["name"], seed, ok, log_path))

    # ── Collect ──
    results_path = collect_results(all_results, out_dir)

    total = len(all_results)
    passed = sum(1 for _, _, ok, _ in all_results if ok)
    failed = total - passed

    status = "pass" if failed == 0 else "fail"
    write_result({"status": status, "module": f"{module_name}/sim-runner",
                  "summary": f"{passed}/{total} tests passed",
                  "metrics": {"total": total, "passed": passed, "failed": failed},
                  "outputs": {"sim_results": results_path}})

    if failed > 0:
        logger.warn(f"{failed} test(s) FAILED")
        sys.exit(ExitCode.RUNTIME_ERROR)
    else:
        logger.info(f"All {total} tests PASSED")


if __name__ == "__main__":
    main()
