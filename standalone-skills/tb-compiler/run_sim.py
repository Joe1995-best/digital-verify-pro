#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_sim.py — Simulation execution engine for digital-verify-pro.

Layered approach:
1. RTL syntax check (always, no UVM needed)
2. Simple non-UVM testbench simulation (--gen-tb for quick functional test)
3. Full UVM simulation (when UVM library available)

Usage:
    python run_sim.py --spec i2c_spec.yml -o ./output --list
    python run_sim.py --spec i2c_spec.yml -o ./output --check-only   ← compile RTL
    python run_sim.py --spec i2c_spec.yml -o ./output --gen-tb       ← gen + run simple TB
    python run_sim.py --spec i2c_spec.yml -o ./output --test basic    ← UVM sim (needs UVM)
    python run_sim.py --detect
"""

import os, sys, re, json, glob, time, argparse, subprocess, shutil
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)
from template_engine import build_spec_data, extract_module_name


def detect_simulators():
    sims = []
    for name, exe_key in [("iverilog", "iverilog"), ("verilator", "verilator"),
                          ("vcs", "vcs"), ("questa", "vsim")]:
        exe = shutil.which(exe_key)
        if exe:
            sims.append((name, exe))
    return sims


def find_default_simulator():
    sims = detect_simulators()
    return sims[0] if sims else None


def discover_sources(out_dir):
    rtl_dir = os.path.join(out_dir, "rtl", "rtl")
    rtl_sv = sorted(glob.glob(os.path.join(rtl_dir, "*.sv"))) if os.path.exists(rtl_dir) else []
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    if_dir = sorted(glob.glob(os.path.join(env_dir, "interfaces", "*.sv"))) if os.path.exists(env_dir) else []
    return rtl_sv, if_dir, env_dir


def discover_tests(out_dir):
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    manifest_path = os.path.join(env_dir, "sequences", "test_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            return json.load(f).get("tests", [])
    seq_dir = os.path.join(env_dir, "sequences")
    tests = []
    if os.path.exists(seq_dir):
        for f in sorted(glob.glob(os.path.join(seq_dir, "*_seq.sv"))):
            name = os.path.basename(f).replace("_seq.sv", "")
            if name not in ("base", "reset", "apb_rw"):
                tests.append({"name": name, "description": name.replace("_", " ").title()})
    return tests


# ── Compile RTL ─────────────────────────────────────────────

def find_uvm():
    """Locate UVM or project stubs. Returns (pkg_path, dir) or None."""
    # Generated stubs in project
    for p in [
        os.path.join(PROJECT_DIR, "uvm", "uvm_pkg.sv"),
    ]:
        if os.path.exists(p):
            return (p, os.path.dirname(p))
    # iverilog embedded UVM
    iverilog = shutil.which("iverilog")
    if iverilog:
        ivl = os.path.dirname(os.path.dirname(iverilog))
        for p in [
            os.path.join(ivl, "lib", "ivl", "uvm_pkg.sv"),
            os.path.join(ivl, "lib", "ivl", "uvm-1.2", "src", "uvm_pkg.sv"),
        ]:
            if os.path.exists(p):
                return (p, os.path.dirname(p))
    return None


def compile_rtl(rtl_sources, out_dir, module_name):
    work_dir = os.path.join(out_dir, "sim_work")
    os.makedirs(work_dir, exist_ok=True)
    log = os.path.join(work_dir, "compile_rtl.log")
    iverilog = shutil.which("iverilog")
    if not iverilog:
        print("  [X] No simulator found"); return False
    cmd = [iverilog, "-g2012", "-o", os.path.join(work_dir, f"{module_name}_rtl.vvp")] + rtl_sources
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    dt = time.time() - t0
    with open(log, "w") as f:
        f.write(f"{' '.join(cmd)}\n=== STDOUT ===\n{r.stdout}\n=== STDERR ===\n{r.stderr}\n")
    if r.returncode == 0:
        print(f"  [OK] RTL compile ({len(rtl_sources)} files, {dt:.1f}s)")
        return True
    print(f"  [X] RTL compile FAILED ({dt:.1f}s)")
    for line in r.stderr.split("\n"):
        if line.strip() and ("error" in line.lower() or "syntax" in line.lower()):
            print(f"      {line.strip()}")
    return False


# ── Generate simple testbench ──────────────────────────────

def gen_simple_tb(out_dir, module_name, spec_path):
    """Generate a standalone non-UVM testbench for quick simulation.
    Tests all registers by writing and reading back.
    No tasks or macros (iverilog 11.0 compatibility)."""
    data = build_spec_data(spec_path)
    regs = data.get("registers", [])
    clk = data["clk_name"]
    rst = data["rst_name"]
    date = datetime.now().strftime("%Y-%m-%d")

    # Build inline test body
    test_body = ""
    for r in regs:
        name = r["name"]
        off = r.get("offset", "0x000")
        rv = None
        for f in r.get("fields", []):
            fname = f.get("name", "").lower()
            if fname != "reserved":
                rv = f.get("reset", "0")
                break
        test_val = "32'hA5A5A5A5"
        if rv:
            try:
                rvi = int(rv, 16) if "x" in rv.lower() else int(rv)
                test_val = f"32'h{(rvi ^ 0xFF) & 0xFF:08X}"
            except ValueError:
                pass
        # Write transaction
        test_body += f"""    // WRITE {name} ({off})
    psel = 1; penable = 0; pwrite = 1; paddr = 12'h{off[2:]}; pwdata = {test_val};
    @(posedge {clk});
    penable = 1;
    @(posedge {clk});
    while (!pready) @(posedge {clk});
    if (pslverr) $display("  WARN: PSLVERR on write %0h", 12'h{off[2:]});
    psel = 0; penable = 0;
    @(posedge {clk});
"""
        # Read transaction
        test_body += f"""    // READ {name} ({off})
    psel = 1; penable = 0; pwrite = 0; paddr = 12'h{off[2:]};
    @(posedge {clk});
    penable = 1;
    @(posedge {clk});
    while (!pready) @(posedge {clk});
    read_data = prdata;
    if (pslverr) begin
      $display("  WARN: PSLVERR on read %0h", 12'h{off[2:]});
    end else if (read_data !== {test_val}) begin
      $display("  FAIL: %0h = %0h (expected %0h)", 12'h{off[2:]}, read_data, {test_val});
      errors = errors + 1;
    end else begin
      $display("  PASS: %0h = %0h", 12'h{off[2:]}, read_data);
    end
    psel = 0; penable = 0;
    @(posedge {clk});
"""
    # Build full TB
    tb_code = f"""// {date}
// Simple testbench for {module_name} -- auto-generated by digital-verify-pro
// No UVM, no tasks, no macros -- iverilog compatible

`timescale 1ns/1ps

module tb_{module_name};
  reg {clk};
  reg {rst};
  reg psel, penable, pwrite;
  reg [11:0] paddr;
  reg [31:0] pwdata;
  wire [31:0] prdata;
  wire pready, pslverr;
  reg [31:0] read_data;
  int errors;

  {module_name} dut (
    .{clk}({clk}), .{rst}({rst}),
    .psel(psel), .penable(penable), .pwrite(pwrite),
    .paddr(paddr), .pwdata(pwdata),
    .prdata(prdata), .pready(pready), .pslverr(pslverr)
  );

  initial begin
    {clk} = 0;
    forever #10 {clk} = ~{clk};
  end

  initial begin
    {rst} = 0;
    #100;
    {rst} = 1;
  end

  initial begin
    errors = 0;
    $display("=== {module_name} Test ({len(regs)} registers) ===");
    #150;

{test_body}
    #100;
    if (errors == 0)
      $display("*** TEST PASSED ***");
    else
      $display("*** TEST FAILED with %0d errors ***", errors);
    $finish;
  end

  initial begin
    $dumpfile("{module_name}.vcd");
    $dumpvars(0, tb_{module_name});
  end
endmodule
"""
    # Strip non-ASCII (iverilog hates UTF-8 in comments)
    tb_code_ascii = tb_code.encode("ascii", "replace").decode("ascii")
    tb_path = os.path.join(out_dir, "sim_work", "tb_simple.sv")
    os.makedirs(os.path.dirname(tb_path), exist_ok=True)
    with open(tb_path, "w", encoding="ascii") as f:
        f.write(tb_code_ascii)
    print(f"  [GEN] Simple testbench ({len(regs)} register tests)")
    return tb_path

def compile_and_run_simple(rtl_sources, tb_path, out_dir, module_name):
    """Compile RTL + simple TB, then simulate."""
    work_dir = os.path.join(out_dir, "sim_work")
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        print("  [X] iverilog not found"); return False

    # Compile
    vvp_out = os.path.join(work_dir, f"{module_name}_sim.vvp")
    log = os.path.join(work_dir, "simulate.log")
    cmd = [iverilog, "-g2012", "-s", f"tb_{module_name}", "-o", vvp_out] + rtl_sources + [tb_path]
    print(f"  [SIM] Compiling RTL + testbench...")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    dt = time.time() - t0
    with open(log, "w") as f:
        f.write(f"Compile: {' '.join(cmd)}\n=== STDOUT ===\n{r.stdout}\n=== STDERR ===\n{r.stderr}\n")
    if r.returncode != 0:
        print(f"  [X] Compile FAILED ({dt:.1f}s)")
        for line in r.stderr.split("\n"):
            if line.strip() and ("error" in line.lower()):
                print(f"      {line.strip()}")
        return False
    print(f"  [OK] Compile ({dt:.1f}s)")

    # Simulate
    print(f"  [SIM] Running simulation...")
    t0 = time.time()
    r = subprocess.run([vvp, vvp_out], capture_output=True, text=True, timeout=120)
    dt = time.time() - t0
    with open(log, "a") as f:
        f.write(f"\n=== SIMULATION ===\n{r.stdout}\n{r.stderr}\n")

    # Parse results
    out = r.stdout + r.stderr
    passed = "TEST PASSED" in out
    fail_count = 0
    m = re.search(r"FAILED with (\d+) errors", out)
    if m:
        fail_count = int(m.group(1))

    print(f"  {'[OK]' if passed else '[X]'} Simulation {'PASSED' if passed else 'FAILED'} ({dt:.1f}s)")
    if fail_count:
        print(f"         {fail_count} register test(s) failed")

    # Print key simulation output
    for line in out.split("\n"):
        line = line.strip()
        if line and ("PASS:" in line or "FAIL:" in line or "TEST" in line or "WARN:" in line):
            print(f"    {line}")

    return passed


# ── Main ─────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="digital-verify-pro simulation runner")
    ap.add_argument("--spec", "-s", default="")
    ap.add_argument("--outdir", "-o", default="")
    ap.add_argument("--list", action="store_true", help="List tests")
    ap.add_argument("--check-only", action="store_true", help="Syntax check RTL")
    ap.add_argument("--gen-tb", action="store_true", help="Generate & run simple testbench")
    ap.add_argument("--all", action="store_true", help="Run all UVM tests (needs UVM)")
    ap.add_argument("--test", "-t", default="", help="Run UVM test by name")
    ap.add_argument("--detect", action="store_true", help="Detect simulators")
    ap.add_argument("--gen-eda", action="store_true", help="Generate Questa/VCS compile scripts")
    args = ap.parse_args()

    if args.detect:
        sims = detect_simulators()
        if sims:
            print("Available simulators:")
            for n, e in sims:
                print(f"  {n:12s} → {e}")
        else:
            print("No simulators. Install: choco install iverilog")
        return

    spec = args.spec
    if not spec:
        for c in ["i2c_spec.yml", "pcie_ep_spec.yml", "arm_pl061_gpio.yml"]:
            f = os.path.join(PROJECT_DIR, c)
            if os.path.exists(f):
                spec = f; break
    if not spec or not os.path.exists(spec):
        print("[X] Spec not found"); sys.exit(1)

    out_dir = os.path.abspath(args.outdir) if args.outdir else os.path.join(PROJECT_DIR, "output")
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    if not os.path.exists(env_dir):
        print(f"[X] Run pipeline first: python pro_verify.py --pipeline {spec}"); sys.exit(1)

    module_name = extract_module_name(out_dir)
    if module_name == "unknown":
        module_name = build_spec_data(spec).get("module_name", "unknown")

    rtl_sv, if_sv, env_dir_path = discover_sources(out_dir)
    tests = discover_tests(out_dir)

    if args.list:
        print(f"\n{'='*60}")
        print(f"  {module_name.upper()} — {len(tests)} tests")
        print(f"  RTL: {len(rtl_sv)} files")
        print(f"{'='*60}")
        for t in tests:
            print(f"  {t['name']:35s} {t.get('description','')}")
        return

    # ── RTL check ──
    print(f"\n{'='*60}")
    if not compile_rtl(rtl_sv, out_dir, module_name):
        sys.exit(1)

    if args.check_only:
        return

    # ── Simple TB simulation ──
    if args.gen_tb:
        tb = gen_simple_tb(out_dir, module_name, spec)
        ok = compile_and_run_simple(rtl_sv, tb, out_dir, module_name)
        sys.exit(0 if ok else 1)

    # ── Generate EDA scripts (Questa/VCS) ──
    if args.gen_eda:
        print("  [GEN] Generating Questa/VCS compile scripts...")
        sys.path.insert(0, BASE_DIR)
        from questa_vcs_support import gen_questa_do, gen_vcs_script
        import questa_vcs_support
        uvm_dir = os.path.join(PROJECT_DIR, "uvm")
        if not os.path.exists(os.path.join(uvm_dir, "uvm_pkg.sv")):
            uvm_dir = None
        questa_vcs_support.gen_questa_do(out_dir, module_name, uvm_dir)
        questa_vcs_support.gen_vcs_script(out_dir, module_name, uvm_dir)
        sys.exit(0)

    # ── UVM simulation ──
    print(f"  --UVM mode--")
    # Find UVM library (system or local stubs)
    uvm_info = find_uvm() if 'find_uvm' in dir() else None
    uvm_pkg_path = None
    uvm_dir = None
    
    # Quick UVM stub generator (always available)
    uvm_stub_dir = os.path.join(PROJECT_DIR, "uvm")
    if not os.path.exists(os.path.join(uvm_stub_dir, "uvm_pkg.sv")):
        print(f"  [GEN] Generating UVM stubs...")
        subprocess2 = __import__('subprocess')
        subprocess2.run([sys.executable, os.path.join(PROJECT_DIR, "gen_uvm_stub.py")],
                      capture_output=True, timeout=30)
    uvm_pkg_path = os.path.join(uvm_stub_dir, "uvm_pkg.sv")
    uvm_dir = uvm_stub_dir
    
    if not os.path.exists(uvm_pkg_path):
        print(f"  [X] UVM not available. Run gen_uvm_stub.py first.")
        sys.exit(1)
    
    # Compile RTL + UVM env together
    print(f"  [SIM] Full compile with UVM...")
    all_src = list(dict.fromkeys(rtl_sv + if_sv + [os.path.join(env_dir_path, f) for f in os.listdir(env_dir_path) if f.endswith('.sv')] if os.path.exists(env_dir_path) else []))
    
    # Collect env SV files recursively
    env_sv_files = []
    if os.path.exists(env_dir_path):
        for root, _, files in os.walk(env_dir_path):
            for f in files:
                if f.endswith('.sv'):
                    env_sv_files.append(os.path.join(root, f))
    all_src = list(dict.fromkeys(rtl_sv + if_sv + env_sv_files))
    
    work_dir = os.path.join(out_dir, "sim_work")
    os.makedirs(work_dir, exist_ok=True)
    vvp_out = os.path.join(work_dir, f"{module_name}_uvm.vvp")
    
    iverilog = shutil.which("iverilog")
    if not iverilog:
        print(f"  [X] iverilog not found")
        sys.exit(1)
    
    # Add include paths for env files (they use `include relative paths)
    include_dirs = [uvm_dir, env_dir_path]
    for sub in ["agents", "sequences", "assertions", "scoreboard", "coverage", "bfm", "ral", "tests"]:
        subd = os.path.join(env_dir_path, sub)
        if os.path.exists(subd):
            include_dirs.append(subd)
    
    # Order sources for compilation: dependencies before dependents
    ordered_src = []
    env_root = env_dir_path
    # 1. Package first
    for f in sorted(glob.glob(os.path.join(env_root, "env_pkg.sv"))):
        ordered_src.append(f)
    # 2. Interfaces (no deps)
    for f in sorted(glob.glob(os.path.join(env_root, "interfaces", "*.sv"))):
        ordered_src.append(f)
    # 3. Agents (depends on package)
    for f in sorted(glob.glob(os.path.join(env_root, "agents", "*.sv"))):
        ordered_src.append(f)
    # 4. BFM (depends on interface)
    for f in sorted(glob.glob(os.path.join(env_root, "bfm", "*.sv"))):
        ordered_src.append(f)
    # 5. RAL (depends on package)
    for f in sorted(glob.glob(os.path.join(env_root, "ral", "*.sv"))):
        ordered_src.append(f)
    # 6. Scoreboard (depends on agents)
    for f in sorted(glob.glob(os.path.join(env_root, "scoreboard", "*.sv"))):
        ordered_src.append(f)
    # 7. Coverage (depends on package)
    for f in sorted(glob.glob(os.path.join(env_root, "coverage", "*.sv"))):
        ordered_src.append(f)
    # 8. Assertions (depends on interfaces)
    for f in sorted(glob.glob(os.path.join(env_root, "assertions", "*.sv"))):
        ordered_src.append(f)
    # 9. Sequences (depends on agents)
    for f in sorted(glob.glob(os.path.join(env_root, "sequences", "*.sv"))):
        ordered_src.append(f)
    # 10. Base test (depends on env)
    for f in sorted(glob.glob(os.path.join(env_root, "base_test.sv"))):
        ordered_src.append(f)
    # 11. Env (depends on agents, scoreboard)
    for f in sorted(glob.glob(os.path.join(env_root, "*_env.sv"))):
        ordered_src.append(f)
    # 12. Tests (depends on sequences, env)
    for f in sorted(glob.glob(os.path.join(env_root, "tests", "*.sv"))):
        ordered_src.append(f)
    # 13. TB top (depends on everything)
    for f in sorted(glob.glob(os.path.join(env_root, "tb_top.sv"))):
        ordered_src.append(f)
    # Add RTL sources at front
    all_ordered = rtl_sv + ordered_src
    all_ordered = list(dict.fromkeys(all_ordered))  # deduplicate
    
    cmd = [iverilog, "-g2012", "-s", "tb_top" if any('tb_top.sv' in f for f in all_ordered) else "tb_" + module_name,
           "-o", vvp_out]
    for d in include_dirs:
        cmd.extend(["-I", d])
    # UVM first, then all sources
    cmd.append(os.path.join(uvm_dir, "uvm_global_macros.svh"))
    cmd.append(os.path.join(uvm_dir, "uvm_pkg.sv"))
    cmd.extend(all_ordered)
    
    log = os.path.join(work_dir, "compile_uvm.log")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    dt = time.time() - t0
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"{' '.join(cmd)}\n=== STDOUT ===\n{r.stdout}\n=== STDERR ===\n{r.stderr}\n")
    
    if r.returncode != 0:
        print(f"  [X] UVM compile FAILED ({dt:.1f}s)")
        for line in r.stderr.split("\n"):
            if "error" in line.lower() and "uvm_" not in line.lower() and "macro" not in line.lower():
                print(f"      {line.strip()}")
        sys.exit(1)
    print(f"  [OK] UVM compile ({len(all_src)} files + UVM, {dt:.1f}s)")
    
    # Run simulation
    print(f"  [SIM] Running UVM simulation...")
    t0 = time.time()
    r2 = subprocess.run([shutil.which("vvp"), vvp_out], capture_output=True, text=True, timeout=120)
    dt2 = time.time() - t0
    sim_log = os.path.join(work_dir, "simulate_uvm.log")
    with open(sim_log, "w", encoding="utf-8") as f:
        f.write(f"=== SIMULATION ===\n{r2.stdout}\n{r2.stderr}\n")
    
    out = r2.stdout + r2.stderr
    passed = "TEST PASSED" in out
    errors = len(re.findall(r"UVM_ERROR|UVM_FATAL", out))
    print(f"  {'[OK]' if passed else '[X]'} UVM Simulation {'PASSED' if passed else 'FAILED'} ({dt2:.1f}s)")
    if errors:
        print(f"      {errors} error(s)")
    
    # Print UVM report
    for line in out.split("\n"):
        line = line.strip()
        if any(kw in line for kw in ["TEST PASSED", "TEST FAILED", "UVM_INFO", "UVM_ERROR", "UVM_FATAL"]):
            if "uvm_test_top.env" in line or "TEST" in line.upper():
                print(f"    {line}")
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
