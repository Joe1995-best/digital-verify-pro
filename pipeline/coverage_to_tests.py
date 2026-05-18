#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coverage_to_tests.py — Coverage Gap → Test Generation Bridge

Orchestrates the full coverage closure loop:
  1. Find/run simulation → VCD file
  2. Run coverage analysis on VCD → export gaps.json
  3. Read gaps.json → drive test generation (run_test_generator.py --gaps)
  4. Output new coverage-driven test sequences
  5. (Optional) Re-run simulation with new tests

Usage:
  python pipeline/coverage_to_tests.py --vcd <sim.vcd> --spec <spec.yml>
  python pipeline/coverage_to_tests.py --vcd examples/alu4/alu4.vcd --spec simple --mod alu4

Args:
  --vcd      Path to VCD waveform file
  --spec     Spec file (yml, or "simple"/"i2c"/"ot_dma" for built-in)
  --mod      Module name (default: auto-detect from VCD path)
  --out      Output directory (default: output/)
  --clk      Clock signal name (default: clk)
  --rerun    If set, re-run sim after test generation
  --sim-cmd  Command to run sim (default: iverilog-based)
"""

import os, sys, json, argparse, subprocess, glob, re, datetime

# ── Path setup ───────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "engines"))
sys.path.insert(0, os.path.join(BASE_DIR, "pipeline"))

from coverage_engine import CoverageEngine


def find_latest_vcd(search_dir: str = ".") -> str:
    """Find the most recently modified VCD file in a directory tree."""
    candidates = glob.glob(os.path.join(search_dir, "**", "*.vcd"), recursive=True)
    if not candidates:
        return ""
    return max(candidates, key=os.path.getmtime)


def run_coverage_analysis(vcd_path: str, module: str, clk: str,
                           out_dir: str) -> str:
    """
    Run full coverage analysis on VCD file.
    Returns path to exported gaps.json.
    """
    gaps_dir = os.path.join(out_dir, "coverage")
    os.makedirs(gaps_dir, exist_ok=True)
    gaps_path = os.path.join(gaps_dir, "gaps.json")

    engine = CoverageEngine(module_name=module)
    print(f"  [COV] Analyzing VCD: {vcd_path}")
    report = engine.analyze_vcd(vcd_path=vcd_path, clk_signal=clk)

    # Export gaps
    engine.export_gaps_json(gaps_path)

    # Print gap summary
    gaps = report.coverage_gaps
    suggestions = engine.generate_targeted_tests()
    print(f"  [COV] Coverage: toggle={report.toggle_coverage_pct}%, "
          f"fsm={report.fsm_coverage_pct}%, "
          f"overall={report.overall_pct}%")
    print(f"  [COV] Gaps found: {len(gaps)} "
          f"(critical={sum(1 for g in gaps if g.severity >= 4)})")
    print(f"  [COV] Suggested tests: {len(suggestions)}")

    return gaps_path


def run_test_generation(gaps_path: str, spec: str, out_dir: str) -> list:
    """
    Run test generator with gaps.json to produce targeted SV sequences.
    Returns list of generated file paths.
    """
    # Locate the test generator
    tg_script = os.path.join(BASE_DIR, "pipeline", "run_test_generator.py")
    if not os.path.exists(tg_script):
        print(f"  [X] Test generator not found: {tg_script}")
        return []

    cmd = [sys.executable, tg_script,
           f"--gaps={gaps_path}",
           f"--out={os.path.abspath(out_dir)}"]

    if spec and os.path.exists(spec):
        cmd.append(f"--spec={spec}")
    elif spec:
        cmd.append(f"--spec={spec}")

    print(f"  [GEN] Running: {' '.join(os.path.basename(c) if i == 0 and 'python' in c else c for i, c in enumerate(cmd))}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
    print(result.stdout)
    if result.stderr:
        print(f"  [STDERR] {result.stderr[:500]}")

    return result.stdout


def find_generated_seqs(out_dir: str, prefix: str = "gap_") -> list:
    """Find generated gap-driven test sequences."""
    seq_dir = os.path.join(out_dir, "rtl", "verification", "env", "sequences")
    if not os.path.exists(seq_dir):
        return []
    return glob.glob(os.path.join(seq_dir, f"{prefix}*.sv"))


def main():
    parser = argparse.ArgumentParser(
        description="Coverage-to-Tests Bridge — closes the coverage loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python pipeline/coverage_to_tests.py --vcd sim.vcd --spec i2c_spec.yml
  python pipeline/coverage_to_tests.py --vcd examples/alu4/alu4.vcd --spec simple
  python pipeline/coverage_to_tests.py --vcd dma_full_test.vcd --spec ot_dma_spec.yml
  python pipeline/coverage_to_tests.py --latest --spec simple
""")
    parser.add_argument("--vcd", default="", help="VCD file to analyze")
    parser.add_argument("--latest", action="store_true", help="Auto-find latest VCD")
    parser.add_argument("--spec", default="", help="Spec file or name")
    parser.add_argument("--mod", default="", help="Module name")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "output"),
                        help="Output directory")
    parser.add_argument("--clk", default="clk", help="Clock signal name")
    parser.add_argument("--rerun", action="store_true",
                        help="Re-run simulation after test generation")
    parser.add_argument("--sim-cmd", default="", help="Simulation command")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  COVERAGE-TO-TESTS BRIDGE")
    print(f"  Started: {datetime.datetime.now().isoformat()}")
    print(f"{'='*60}")

    # Step 0: Resolve VCD path
    vcd_path = args.vcd
    if args.latest or not vcd_path:
        found = find_latest_vcd(BASE_DIR)
        if found:
            print(f"  [VCD] Auto-found latest: {found}")
            vcd_path = found
        elif vcd_path:
            pass  # user specified but not found
        else:
            print("  [X] No VCD file found. Use --vcd or --latest")
            return

    if not os.path.exists(vcd_path):
        print(f"  [X] VCD not found: {vcd_path}")
        return

    # Step 1: Determine module name
    module = args.mod
    if not module:
        # Try to extract module name from VCD filename
        basename = os.path.splitext(os.path.basename(vcd_path))[0]
        # Remove common suffixes
        for suffix in ["_test", "_sim", "_tb", "_full", ".vcd"]:
            if basename.endswith(suffix):
                basename = basename[:-len(suffix)]
        module = basename if basename else "unknown"
    print(f"  [MOD] Module: {module}")

    # Step 2: Resolve spec
    spec_path = args.spec
    if spec_path and not os.path.exists(spec_path):
        # Try common locations
        for candidate in [
            os.path.join(BASE_DIR, spec_path),
            os.path.join(BASE_DIR, f"{spec_path}_spec.yml"),
            os.path.join(BASE_DIR, "examples", spec_path, f"{spec_path}_spec.yml"),
        ]:
            if os.path.exists(candidate):
                spec_path = candidate
                break

    # Step 3: Run coverage analysis → export gaps.json
    print(f"\n{'─'*50}")
    print(f"  Phase 1: Coverage Analysis")
    print(f"{'─'*50}")
    gaps_path = run_coverage_analysis(vcd_path, module, args.clk, args.out)

    # Step 4: Load gaps to understand what we found
    with open(gaps_path) as f:
        gap_data = json.load(f)

    gaps = gap_data.get("gaps", [])
    suggested = gap_data.get("suggested_tests", [])

    if not gaps:
        print(f"\n  [INFO] No coverage gaps found — coverage is complete!")
        return

    if not suggested:
        print(f"\n  [WARN] No suggested tests generated from gaps. "
              f"Gaps may be low-severity only.")
        # Still proceed — may generate coverage_gap category tests

    # Step 5: Run test generator with gaps
    print(f"\n{'─'*50}")
    print(f"  Phase 2: Test Generation (Gap-Driven)")
    print(f"{'─'*50}")
    run_test_generation(gaps_path, spec_path, args.out)

    # Step 6: Check generated files
    print(f"\n{'─'*50}")
    print(f"  Phase 3: Verification")
    print(f"{'─'*50}")
    seq_dir = os.path.join(args.out, "rtl", "verification", "env", "sequences")
    generated = find_generated_seqs(args.out)

    # Also find any new .sv files
    if os.path.exists(seq_dir):
        all_new = sorted(glob.glob(os.path.join(seq_dir, "*.sv")))
        # Filter to ones modified recently (within last 60 seconds)
        now = datetime.datetime.now().timestamp()
        recent = [f for f in all_new if os.path.getmtime(f) > now - 60]

        if recent:
            print(f"  [OK] Generated {len(recent)} new sequence files:")
            for f in recent:
                fname = os.path.basename(f)
                # Check if it's gap-driven
                tag = " [GAP-DRIVEN]" if "gap_" in fname else ""
                print(f"    └─ {fname}{tag}")
        else:
            print(f"  [INFO] No recent files — checking sequences dir...")
            for f in sorted(all_new):
                fname = os.path.basename(f)
                tag = " [GAP-DRIVEN]" if "gap_" in fname else ""
                print(f"    └─ {fname}{tag}")

    # Step 7: Optional re-run simulation
    if args.rerun:
        print(f"\n{'─'*50}")
        print(f"  Phase 4: Re-run Simulation")
        print(f"{'─'*50}")
        if args.sim_cmd:
            print(f"  [SIM] Running: {args.sim_cmd}")
            subprocess.run(args.sim_cmd, shell=True, cwd=BASE_DIR)
        else:
            print(f"  [SIM] No sim command provided. "
                  f"Run manually after verifying new sequences.")

    # Summary
    print(f"\n{'='*60}")
    print(f"  COVERAGE-TO-TESTS BRIDGE COMPLETE")
    print(f"{'='*60}")
    print(f"  VCD:        {vcd_path}")
    print(f"  Module:     {module}")
    critical_gaps = sum(1 for g in gaps if g.get("severity", 0) >= 4) if gaps else 0
    print(f"  Gaps found: {len(gaps)} ({critical_gaps} critical)")
    print(f"  Tests gen:  {len(suggested)} targeted")
    print(f"  Gaps JSON:  {gaps_path}")
    print(f"  Next step:  Review generated sequences in {seq_dir}")
    if args.rerun:
        print(f"  Re-run:     Completed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
