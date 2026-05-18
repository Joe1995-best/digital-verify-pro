#!/usr/bin/env python3
"""
cli.py — Command-line entry point for Digital Verify Pro.

Usage:
    python cli.py <rtl_file> [--spec "description"] [--dashboard] [--formal] ...
    python cli.py --pipeline <spec.yml> [--phases spec-analyzer,...]
    python cli.py --regression [spec1.yml spec2.yml ...]
    python cli.py --list-pipeline-phases
"""

import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

from track1 import ProVerify
from track2 import PipelineRunner, PIPELINE_PHASES
from regression import run_regression, print_pipeline_help


def main():
    parser = argparse.ArgumentParser(
        description="Digital Verify Pro -- Enhanced RTL Verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  Track 1 (Quick RTL Verification):
    python pro_verify.py alu.v
    python pro_verify.py alu.v --spec "4-bit ALU with add/sub/and/or"
    python pro_verify.py alu.v --dashboard --vcd --iterations 5
    python pro_verify.py alu.v --formal --depth 30

  Track 2 (Spec-driven UVM Pipeline):
    python pro_verify.py --pipeline i2c_spec.yml
    python pro_verify.py --pipeline uart_spec.yml --phases spec-analyzer,env-builder
    python pro_verify.py --pipeline i2c_spec.yml --outdir ./my_output
    python pro_verify.py --pipeline i2c_spec.yml --resume
    python pro_verify.py --list-pipeline-phases
        """,
    )

    # Pipeline mode arguments (mutually exclusive with RTL mode)
    parser.add_argument("--pipeline", "-p", nargs="?", const="", default=None,
                        help="Run UVM pipeline mode with spec file")
    parser.add_argument("--phases", "-P",
                        help="Comma-separated phases to run (default: all): spec-analyzer,env-builder,...")
    parser.add_argument("--list-pipeline-phases", action="store_true",
                        help="List all pipeline phases and exit")
    parser.add_argument("--skip-checks", action="store_true",
                        help="Skip dependency checks in pipeline mode")
    parser.add_argument("--resume", "-r", action="store_true",
                        help="Resume pipeline from last checkpoint")
    parser.add_argument("--regression", nargs="*", default=None,
                        help="Run regression on all specs or specified subset. Usage: --regression [spec1.yml spec2.yml ...]")

    # Track 1 (RTL verification) arguments
    parser.add_argument("rtl", nargs="?", help="Verilog/SystemVerilog RTL file")
    parser.add_argument("--spec", "-s", help="Natural language specification", default="")
    parser.add_argument("--outdir", "-o", help="Output directory", default="")
    parser.add_argument("--vcd", action="store_true", default=True, help="Enable VCD waveform dump")
    parser.add_argument("--no-vcd", action="store_false", dest="vcd", help="Disable VCD")
    parser.add_argument("--iterations", "-i", type=int, default=5, help="Max auto-fix iterations")
    parser.add_argument("--dashboard", action="store_true", default=True, help="Generate HTML dashboard")
    parser.add_argument("--no-dashboard", action="store_false", dest="dashboard", help="Skip dashboard")
    parser.add_argument("--formal", action="store_true", help="Generate formal properties (SVA + SymbiYosys)")
    parser.add_argument("--depth", type=int, default=20, help="Formal check depth")

    args = parser.parse_args()

    # ── Mode selection ────────────────────────────────────────
    if args.regression is not None:
        summary = run_regression(
            spec_filter=args.regression,
            outdir_override=args.outdir,
            phases=None if not args.phases else [p.strip() for p in args.phases.split(",")],
            skip_checks=args.skip_checks,
        )
        sys.exit(0 if summary["failed_specs"] == 0 else 1)

    if args.list_pipeline_phases:
        print_pipeline_help()
        sys.exit(0)

    if args.pipeline is not None:
        # ── Track 2: UVM Pipeline Mode ──
        spec_path = args.pipeline if args.pipeline else (args.rtl or "")
        if not spec_path:
            # Try i2c_spec.yml or uart_spec.yml in project root
            for candidate in ["i2c_spec.yml", "uart_spec.yml"]:
                full = os.path.join(SCRIPT_DIR, candidate)
                if os.path.exists(full):
                    spec_path = full
                    break

        if not spec_path or not os.path.exists(spec_path):
            print(f"[X] No spec file specified or found")
            print(f"    Provide path: python pro_verify.py --pipeline <spec.yml>")
            print(f"    Or use default: python pro_verify.py --pipeline i2c_spec.yml")
            sys.exit(1)

        # Parse phases
        phases = None
        if args.phases:
            phases = [p.strip() for p in args.phases.split(",")]
            # Validate phases
            for p in phases:
                if p not in PIPELINE_PHASES:
                    print(f"[X] Unknown phase: {p}")
                    print(f"    Valid phases: {', '.join(PIPELINE_PHASES.keys())}")
                    sys.exit(1)

        runner = PipelineRunner(
            spec_path=spec_path,
            outdir=args.outdir,
            phases=phases,
            skip_checks=args.skip_checks,
            resume=args.resume,
        )

        result = runner.run()
        sys.exit(0 if result["success"] else 1)

    else:
        # ── Track 1: Quick RTL Verification Mode ──
        if not args.rtl:
            parser.print_help()
            print(f"")
            print(f"Specify an RTL file for Track 1, or use --pipeline for Track 2.")
            print(f"See --list-pipeline-phases for pipeline details.")
            sys.exit(1)

        if not os.path.exists(args.rtl):
            print(f"[X] RTL file not found: {args.rtl}")
            sys.exit(1)

        verifier = ProVerify(
            rtl_path=args.rtl,
            spec=args.spec,
            outdir=args.outdir,
            enable_vcd=args.vcd,
            max_iterations=args.iterations,
            enable_dashboard=args.dashboard,
            enable_formal=args.formal,
        )

        result = verifier.run()

        if result.get("tests", {}).get("failed", 0) > 0:
            sys.exit(1)  # Failure exit code
        sys.exit(0)


if __name__ == "__main__":
    main()
