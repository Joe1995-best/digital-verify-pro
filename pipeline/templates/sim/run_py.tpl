#!/usr/bin/env python3
"""{{ module_name }} — Simulation runner (auto-generated)"""

import subprocess, sys, os

def main():
    import argparse
    parser = argparse.ArgumentParser(description="{{ module_name }} simulation")
    parser.add_argument("--gui", action="store_true", help="Open GTKWave after simulation")
    parser.add_argument("--waves", default="dump.vcd", help="VCD file path")
    args = parser.parse_args()

    print(f"Running {{ module_name }} simulation...")

    # Compile with iverilog
    rtl_dir = os.path.join(os.path.dirname(__file__), "..", "..", "rtl")
    src_files = [
        "tb_top.sv",
    ]
    for root, _, files in os.walk(os.path.dirname(__file__)):
        for f in files:
            if f.endswith(".sv"):
                src_files.append(os.path.join(root, f))

    cmd = ["iverilog", "-sv", "-g2012", "-o", "sim.vvp"] + src_files
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Compilation failed:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

    print("Compilation OK, running simulation...")
    result = subprocess.run(["vvp", "sim.vvp"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if args.gui and os.path.exists(args.waves):
        subprocess.run(["gtkwave", args.waves])

    sys.exit(0 if "PASSED" in result.stdout else 1)

if __name__ == "__main__":
    main()
