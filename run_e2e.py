#!/usr/bin/env python3
"""DEPRECATED - use pro_verify.py --pipeline <spec>.yml"""
import warnings
warnings.warn("run_e2e.py is deprecated, use pro_verify.py --pipeline <spec>.yml")

"""Updated convergence pipeline: tests both modes, fixes feature matching."""
import os, sys, json, subprocess, glob, shutil
sys.path.insert(0, os.path.dirname(__file__))

BASE = os.path.join(os.path.dirname(__file__), "verify_ot_dma")
GEN_DIR = os.path.join(os.path.dirname(__file__), "output_ot_dma")
VCD = os.path.join(BASE, "dma_full_test.vcd")
GEN_VCD = os.path.join(os.path.dirname(__file__), "dma_gen_test.vcd")
SPEC = os.path.join(os.path.dirname(__file__), "ot_dma_spec.yml")
RTL = os.path.join(BASE, "dma.sv")


def compile_and_run(srcs, top, vcd_name, timeout=120):
    out = os.path.join(BASE, f"sim_{top}")
    r = subprocess.run(["iverilog", "-g2012", "-s", top, "-o", out] + srcs,
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  [X] Compile: {r.stderr[:200]}")
        return None

    vvp = subprocess.run(["vvp", out], capture_output=True, timeout=timeout)
    text = vvp.stdout.decode("utf-8", errors="replace")

    results = {"pass": 0, "fail": 0, "timeout": False, "tests": []}
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("PASS:"):
            results["pass"] += 1
            results["tests"].append({"name": s[6:], "status": "PASS"})
        elif s.startswith("FAIL:"):
            results["fail"] += 1
            results["tests"].append({"name": s[6:], "status": "FAIL"})
        if "TIMEOUT" in s:
            results["timeout"] = True

    print(f"  PASS={results['pass']} FAIL={results['fail']}", end="")
    if results["timeout"]:
        print(" TIMEOUT!", end="")
    print()
    return results


def analyze_vcd(vcd_path):
    from engines.coverage_engine import CoverageEngine
    e = CoverageEngine()
    r = e.analyze_vcd(vcd_path)
    stats = r.to_dict() if hasattr(r, "to_dict") else {}
    return r, stats


def count_regs_in_tests(spec, test_text):
    """Use address matching for register coverage, not name matching."""
    regs = spec.get("registers", [])
    covered = 0
    details = []
    for r in regs:
        off = int(r.get("offset", "0x000"), 16)
        name = r["name"]
        # Check APB reads and writes to this address
        addr_upper = (off >> 8) & 0xFF
        addr_lower = off & 0xFF
        # Match patterns like 16'hXXXX, 12'hXXX, {off}
        patterns = [
            f"16'h{off:04X}",
            f"12'h{off:03X}",
            f"16'h{off:04X},",
            f"12'h{off:03X},",
        ]
        found = any(p in test_text for p in patterns)
        if found:
            covered += 1
            details.append(f"  [OK] {name:30s} @ 0x{off:04X}")
        else:
            details.append(f"  [MISS] {name:30s} @ 0x{off:04X} — never accessed in tests")
    return covered, len(regs), details


def run_gen_rtl():
    """Generate RTL from spec and run tests."""
    print("\n[GEN] Spec -> RTL...")
    r = subprocess.run(
        [sys.executable, "pipeline/run_rtl_gen.py", "--spec", SPEC, "--out", GEN_DIR],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  [X] Generation: {r.stderr[:200]}")
        return None

    rtl_dir = os.path.join(GEN_DIR, "rtl", "rtl")
    gen_srcs = sorted(glob.glob(os.path.join(rtl_dir, "*.sv")))
    tb = os.path.join(GEN_DIR, "vrf", "tests", "dma_gen_test.sv")
    gen_srcs.append(tb)

    print(f"  Compiling + running ({len(gen_srcs)} files)...")
    return compile_and_run(gen_srcs, "dma_gen_test", None)


if __name__ == "__main__":
    print("=" * 60)
    print("  E2E: Both Modes Coverage Convergence")
    print("=" * 60)

    # ── Mode 1: Existing RTL ──
    print("\n[MODE 1] Hand-written RTL (dma.sv v4)")
    srcs = [
        os.path.join(BASE, "dma.sv"),
        os.path.join(BASE, "vrf", "env", "vrf_env_top.sv"),
        os.path.join(BASE, "vrf", "sva", "vrf_assert_apb.sv"),
        os.path.join(BASE, "vrf", "sva", "vrf_assert_fsm.sv"),
        os.path.join(BASE, "vrf", "sva", "vrf_assert_dma.sv"),
        os.path.join(BASE, "vrf", "tests", "dma_full_test.sv"),
    ]
    res1 = compile_and_run(srcs, "dma_full_test", VCD)
    if res1:
        r1, s1 = analyze_vcd(VCD)
        print(f"  Coverage: {r1.toggle_coverage_pct:.1f}% (full={r1.full_toggle_signals}/{r1.total_signals}, stuck={r1.stuck_signals})")

    # ── Mode 2: Spec-generated RTL ──
    print("\n[MODE 2] Spec-generated RTL")
    res2 = run_gen_rtl()
    if res2:
        if os.path.exists(GEN_VCD):
            r2, s2 = analyze_vcd(GEN_VCD)
            print(f"  Coverage: {r2.toggle_coverage_pct:.1f}% (full={r2.full_toggle_signals}/{r2.total_signals}, stuck={r2.stuck_signals})")
            os.remove(GEN_VCD)
        else:
            print("  [X] VCD not found")

    # ── Feature coverage (address-based) ──
    print("\n[TPR] Register address coverage in tests")
    import yaml
    with open(SPEC, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    all_test_text = ""
    for tf in glob.glob(os.path.join(BASE, "vrf", "tests", "*.sv")):
        with open(tf, "r", encoding="utf-8") as f:
            all_test_text += f.read()
    for tf in glob.glob(os.path.join(GEN_DIR, "vrf", "tests", "*.sv")):
        with open(tf, "r", encoding="utf-8") as f:
            all_test_text += f.read()

    covered, total, details = count_regs_in_tests(spec, all_test_text)
    for d in details:
        if "[MISS]" in d:
            print(f"  {d}")
    print(f"\n  Result: {covered}/{total} registers accessed in tests ({covered/total*100:.0f}%)")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    if res1:
        print(f"  Mode 1 (hand-written): {res1['pass']}/{res1['pass']+res1['fail']} PASS, {r1.toggle_coverage_pct:.1f}% toggle")
    if res2:
        print(f"  Mode 2 (spec-gen):     {res2['pass']}/{res2['pass']+res2['fail']} PASS, {r2.toggle_coverage_pct:.1f}% toggle")
    print(f"  TPR: {covered}/{total} registers covered ({covered/total*100:.0f}%)")
    print(f"\n  Files:")
    print(f"    checklists/verification_checklist.md — 6-phase sign-off")
    print(f"    checklists/rtl_review_checklist.md   — RTL code review")
    print(f"    tools/checklist_audit.py              — Auto-audit tool")
