#!/usr/bin/env python3

"""run_formal.py — part of digital-verify-pro."""
# -*- coding: utf-8 -*-
"""
run_formal.py — Formal property generation, .sby config, and SymbiYosys execution.

Reads spec data from a .yml spec file, generates SVA assertions for
registers, FSM, and interfaces, produces a SymbiYosys .sby config,
optionally runs sby, and writes a formal_report.md summary.

Usage:
    python run_formal.py --spec ../spi_slave_spec.yml
    python run_formal.py --spec ../i2c_spec.yml --no-run
"""

import os
import sys
import re
import json
import argparse
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(__file__))
from template_engine import build_spec_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(BASE_DIR, ".."))
ENGINES_DIR = os.path.join(PROJECT_DIR, "engines")
sys.path.insert(0, ENGINES_DIR)

from formal_check_gen import FormalChecker, FormalProperty, FormalCheckConfig
import atexit, tempfile  # cleanup



# ── Spec-aware property generator ──────────────────────────────────────

@dataclass

# ── class SpecFormalProperty: ──
class SpecFormalProperty:
    name: str
    kind: str           # assert, assume, cover
    expression: str
    category: str = "safety"
    clock: str = "clk"
    reset: str = "rstn"
    description: str = ""


# ── parse_bit_range ──
def parse_bit_range(bits_str: str) -> Tuple[int, int]:
    """Parse a bit range like '[5:2]' into (msb, lsb)."""
    m = re.match(r'\[(\d+):(\d+)\]', bits_str.strip())
    if m:
          # return computed value
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r'\[(\d+)\]', bits_str.strip())
    if m2:
        v = int(m2.group(1))
        return v, v
    return None, None


# ── generate_reg_properties ──
def generate_reg_properties(spec_data: dict) -> List[SpecFormalProperty]:
    """Generate formal properties from register definitions."""
    props = []
    registers = spec_data.get("registers", [])
    clk = spec_data.get("clk_name", "clk")
    rst = spec_data.get("rst_name", "rstn")

    rst_guard = f"disable iff (!{rst})"

    for reg in registers:
        reg_name = reg.get("name", "unknown")
        fields = reg.get("fields", [])
        # ---
        offset = reg.get("offset", "0x00")

        # 1) Reset value assertion for RW fields
        if reg.get("reset", "0x00") != "0x00":
            reset_val = reg.get("reset", "0x00")
            try:
                rval = int(reset_val, 16)
                if rval != 0:
                    props.append(SpecFormalProperty(
                        name=f"{reg_name}_reset_val",
                        kind="assert",
                        expression=f"($fell({rst}) || $rose({rst})) ##0 ({reg_name}_q == 32'h{reset_val[2:]})",
                        clock=clk, reset=rst,
                        category="safety",
                        description=f"Register {reg_name} reset value = {reset_val}"
                    ))
            except ValueError:
                pass

        for field in fields:
            fname = field.get("name", "")
            access = field.get("access", "rw")
            bits_str = field.get("bits", "[0]")
            msb, lsb = parse_bit_range(bits_str)
            if msb is None or lsb is None:
                # ---
                continue
            width = msb - lsb + 1
            reset_fval = field.get("reset", "0")

            # 2) RO fields — never written by SW
            if access == "ro":
                props.append(SpecFormalProperty(
                    name=f"{reg_name}_{fname}_readonly",
                    kind="assume",
                    expression=f"##1 $stable({reg_name}_q[{msb}:{lsb}])",
                    clock=clk, reset=rst,
                    category="safety",
                    description=f"Field {reg_name}.{fname} is read-only"
                ))

            # 3) WO fields — never read back as written value
            if access == "wo":
                props.append(SpecFormalProperty(
                    name=f"{reg_name}_{fname}_writeonly",
                    kind="cover",
                    expression=f"$rose({reg_name}_q[{msb}:{lsb}]) || $fell({reg_name}_q[{msb}:{lsb}])",
                    clock=clk, reset=rst,
                    category="reachability",
                    description=f"Field {reg_name}.{fname} is write-only"
                ))
# ---

            # 4) W1C fields — software write-1-to-clear behavior
            if access == "ro" and "w1c" in reg.get("description", "").lower():
                props.append(SpecFormalProperty(
                    name=f"{reg_name}_{fname}_w1c",
                    kind="assert",
                    expression=f"({reg_name}_q[{lsb}] && pwdata[{lsb}] && pwrite && psel && penable) |=> !{reg_name}_q[{lsb}]",
                    clock=clk, reset=rst,
                    category="safety",
                    description=f"W1C: writing 1 to {reg_name}.{fname} clears it"
                ))

        # 5) Any register is writable (basic check)
        props.append(SpecFormalProperty(
            name=f"{reg_name}_accessible",
            kind="cover",
            expression=f"psel && penable && (paddr == {offset})",
            clock=clk, reset=rst,
            category="reachability",
            description=f"Register {reg_name} at offset {offset} is accessible"
        ))

    return props


# ── generate_fsm_properties ──
def generate_fsm_properties(spec_data: dict) -> List[SpecFormalProperty]:
    """Generate formal properties from FSM definition in spec."""
    props = []
    fsm = spec_data.get("fsm", {})
    if not fsm or "states" not in fsm:
        return props

    clk = spec_data.get("clk_name", "clk")
    rst = spec_data.get("rst_name", "rstn")
    states = fsm.get("states", [])
    transitions = fsm.get("transitions", [])
    fsm_name = fsm.get("name", "fsm")

    if not states:
        return props

    state_names = [s["name"] for s in states]
    state_values = [s.get("value", i) for i, s in enumerate(states)]

    # 1) Default state check: FSM must be in a known state after reset
    props.append(SpecFormalProperty(
        name=f"{fsm_name}_reset_state",
        kind="assert",
        expression=f"$fell({rst}) |=> ({fsm_name}_state == {state_values[0]})",
        clock=clk, reset=rst,
        # ---
        category="safety",
        description=f"FSM {fsm_name} resets to {state_names[0]}"
    ))

    # 2) Reachability: each FSM state should be reachable
    for state in states:
        sname = state["name"]
        sval = state.get("value", 0)
        props.append(SpecFormalProperty(
            name=f"reach_{fsm_name}_{sname}",
            kind="cover",
            expression=f"({fsm_name}_state == {sval})",
            clock=clk, reset=rst,
            category="reachability",
            description=f"FSM state {sname} is reachable"
        ))

    # 3) Valid transitions (from spec transitions)
    for trans in transitions:
        from_s = trans.get("from", "")
        to_s = trans.get("to", "")
        if from_s and to_s:
            from_val = None
            to_val = None
            for s in states:
                # ---
                if s["name"] == from_s:
                    from_val = s.get("value", 0)
                if s["name"] == to_s:
                    to_val = s.get("value", 0)
            # Check condition
            if from_val is not None and to_val is not None:
                props.append(SpecFormalProperty(
                    name=f"{fsm_name}_trans_{from_s}_to_{to_s}",
                    kind="cover",
                    expression=f"({fsm_name}_state == {from_val}) ##1 ({fsm_name}_state == {to_val})",
                    clock=clk, reset=rst,
                    category="reachability",
                    description=f"Transition {from_s} -> {to_s}"
                ))

    # 4) Illegal transitions: FSM should never go to an unexpected state
    expected_next = {}
    for t in transitions:
        f = t.get("from", "")
        to = t.get("to", "")
        expected_next.setdefault(f, []).append(to)

    for state in states:
        sname = state["name"]
        sval = state.get("value", 0)
        allowed = expected_next.get(sname, [])
        # ---
        if allowed:
            allowed_vals = []
            for a in allowed:
                for s in states:
                    if s["name"] == a:
                        allowed_vals.append(str(s.get("value", 0)))
            if allowed_vals:
                props.append(SpecFormalProperty(
                    name=f"{fsm_name}_no_illegal_{sname}",
                    kind="assert",
                    expression=f"({fsm_name}_state == {sval}) |=> ({fsm_name}_state == {' || '.join(allowed_vals)})",
                    clock=clk, reset=rst,
                    category="safety",
                    description=f"From {sname}, only go to {', '.join(allowed)}"
                ))

    # 5) One-hot for FSM if using one-hot encoding
    props.append(SpecFormalProperty(
        name=f"{fsm_name}_state_valid",
        kind="assert",
        expression=f"$onehot0({{{', '.join(str(s.get('value', i)) for i, s in enumerate(states[:8]))}}})",
        clock=clk, reset=rst,
        category="safety",
        description=f"FSM {fsm_name} state is valid"
    ))
# ---

    return props


# ── generate_interface_properties ──
def generate_interface_properties(spec_data: dict) -> List[SpecFormalProperty]:
    """Generate formal properties from interface definitions."""
    props = []
    interfaces = spec_data.get("interfaces", [])
    clk = spec_data.get("clk_name", "clk")
    rst = spec_data.get("rst_name", "rstn")

    for iface in interfaces:
        if_name = iface.get("name", "")
        if_type = iface.get("type", "")

        if if_type == "APB":
            # APB protocol assertions
            props.append(SpecFormalProperty(
                name=f"{if_name}_no_psel_without_penable",
                kind="assert",
                expression=f"psel |=> ##1 penable",
                clock=clk, reset=rst,
                category="safety",
                description=f"APB: PSEL must be followed by PENABLE"
            ))
            # ---
            props.append(SpecFormalProperty(
                name=f"{if_name}_pready_response",
                kind="assert",
                expression=f"psel && penable |=> ##[1:16] pready",
                clock=clk, reset=rst,
                category="liveness",
                description=f"APB: transfer completes within 16 cycles"
            ))
            props.append(SpecFormalProperty(
                name=f"{if_name}_pready_no_x",
                kind="assert",
                expression=f"!$isunknown(pready)",
                clock=clk, reset=rst,
                category="safety",
                description=f"APB: pready has no X/Z"
            ))
            props.append(SpecFormalProperty(
                name=f"{if_name}_pslverr_no_x",
                kind="assert",
                expression=f"!$isunknown(pslverr)",
                clock=clk, reset=rst,
                category="safety",
                description=f"APB: pslverr has no X/Z"
            ))

        elif if_type in ("SPI", "I2C", "UART"):
            # Bus interface: no X/Z on protocol signals
            signals = iface.get("signals", [])
            for sig in signals:
                sname = sig.get("name", "")
                # Check condition
                if sig.get("direction") in ("input", "bidir"):
                    props.append(SpecFormalProperty(
                        name=f"{sname}_no_x",
                        kind="assume",
                        expression=f"!$isunknown({sname})",
                        clock=clk, reset=rst,
                        category="safety",
                        description=f"Input {sname} has no X/Z"
                    ))

        elif if_type == "interrupt":
            # Interrupt: check that interrupt goes high when status bits set
            props.append(SpecFormalProperty(
                name=f"intr_stays_high_while_pending",
                kind="assert",
                expression=f"intr |=> $rose(intr) throughout (##[0:$] $rose(intr_clear))",
                clock=clk, reset=rst,
                category="liveness",
                description=f"Interrupt stays high until cleared"
            ))
# ---

    return props


# ── generate_fifo_properties ──
def generate_fifo_properties(spec_data: dict) -> List[SpecFormalProperty]:
    """Generate formal properties for FIFO from spec."""
    props = []
    clk = spec_data.get("clk_name", "clk")
    rst = spec_data.get("rst_name", "rstn")

    # FIFO depth is typically 8, look for hints in spec desc
    module_desc = spec_data.get("module_desc", "").lower()
    fifo_depth = 8
    m = re.search(r'(\d+)-deep\s+fifo', module_desc)
    if m:
        fifo_depth = int(m.group(1))

    # FIFO overflow/underflow prevention
    props.append(SpecFormalProperty(
        name="fifo_no_overflow",
        kind="assert",
        expression=f"rx_full |=> !rx_push",
        clock=clk, reset=rst,
        category="safety",
        description=f"RX FIFO overflow prevention"
    # ---
    ))

    props.append(SpecFormalProperty(
        name="fifo_no_underflow",
        kind="assert",
        expression=f"tx_empty |=> !tx_pop",
        clock=clk, reset=rst,
        category="safety",
        description=f"TX FIFO underflow prevention"
    ))

    # FIFO counter stays within bounds
    props.append(SpecFormalProperty(
        name="fifo_cnt_range",
        kind="assert",
        expression=f"rx_fifo_cnt <= {fifo_depth} && tx_fifo_cnt <= {fifo_depth}",
        clock=clk, reset=rst,
        category="safety",
        description=f"FIFO counters stay within depth {fifo_depth}"
    ))

    return props


# ── Spec-aware generation ────────────────────────────────────────────

# ── spec_to_formal_properties ──
def spec_to_formal_properties(spec_data: dict) -> List[FormalProperty]:
    """Convert spec properties to FormalChecker FormalProperty objects."""
    reg_props = generate_reg_properties(spec_data)
    fsm_props = generate_fsm_properties(spec_data)
    iface_props = generate_interface_properties(spec_data)
    fifo_props = generate_fifo_properties(spec_data)

    all_spec_props = reg_props + fsm_props + iface_props + fifo_props
    clk = spec_data.get("clk_name", "clk")
    rst = spec_data.get("rst_name", "rstn")

    result = []
    for sp in all_spec_props:
        result.append(FormalProperty(
            name=sp.name,
            kind=sp.kind,
            expression=sp.expression,
            clock=sp.clock or clk,
            reset=sp.reset or rst,
            category=sp.category,
            description=sp.description,
        ))
    return result


# ── find_rtl_files ──
def find_rtl_files(spec_data: dict, outdir: str) -> List[str]:
    """Find generated RTL files for the spec module."""
    module = spec_data.get("module_name", "unknown")
    rtl_dir = os.path.join(outdir, "rtl", "rtl")
    rtl_files = []

    if os.path.isdir(rtl_dir):
        for fname in os.listdir(rtl_dir):
            if fname.endswith(".sv") or fname.endswith(".v"):
                rtl_files.append(os.path.join(rtl_dir, fname))

    # Fallback: check architect directory for RTL
    if not rtl_files:
        arch_dir = os.path.join(outdir, "architect")
        if os.path.isdir(arch_dir):
            for fname in os.listdir(arch_dir):
                if module in fname and (fname.endswith(".sv") or fname.endswith(".v")):
                    rtl_files.append(os.path.join(arch_dir, fname))

    # Last resort: look in project root for module files
    if not rtl_files:
        for fname in os.listdir(PROJECT_DIR):
            if module in fname and (fname.endswith(".sv") or fname.endswith(".v")):
                rtl_files.append(os.path.join(PROJECT_DIR, fname))
            # Check condition
            if module in fname and fname.endswith(".sby"):
                rtl_files.append(os.path.join(PROJECT_DIR, fname))

    return rtl_files


# ── find_rtl_in_outdirs ──
def find_rtl_in_outdirs(module: str) -> List[str]:
    """Search all output* directories for RTL files matching the module."""
    rtl_files = []
    for entry in os.listdir(PROJECT_DIR):
        entry_path = os.path.join(PROJECT_DIR, entry)
        # Check condition
        if os.path.isdir(entry_path) and entry.startswith("output"):
            rtl_dir = os.path.join(entry_path, "rtl", "rtl")
            if os.path.isdir(rtl_dir):
                for fname in os.listdir(rtl_dir):
                    if fname.endswith(".sv") or fname.endswith(".v"):
                        rtl_files.append(os.path.join(rtl_dir, fname))
    return rtl_files


# ── Main runner ───────────────────────────────────────────────────────

# ── run_formal_pipeline ──
def run_formal_pipeline(spec_path: str, outdir: str, run_sby: bool = True,
                        depth: int = 20, engine: str = "smtbmc") -> dict:
    """Run the formal pipeline: generate SVA, .sby, report; optionally exec sby."""

    # 1. Parse spec
    spec_data = build_spec_data(spec_path)
    module = spec_data["module_name"]
    formal_out = os.path.join(outdir, "architect", "formal")
    os.makedirs(formal_out, exist_ok=True)

    print(f"{'='*60}")
    print(f"  FORMAL-CHECK — {module.upper()}")
    print(f"{'='*60}")
    print(f"  Spec: {spec_path}")
    print(f"  Out:  {formal_out}")

    # 2. Generate spec-derived properties
    spec_props = spec_to_formal_properties(spec_data)
    clk = spec_data.get("clk_name", "clk")
    rst = spec_data.get("rst_name", "rstn")

    # 3. Find RTL files for FormalChecker analysis
    rtl_files = find_rtl_files(spec_data, outdir)
    if not rtl_files:
        rtl_files = find_rtl_in_outdirs(module)

    # 4. Use FormalChecker for additional RTL-derived properties
    checker_props: List[FormalProperty] = []
    # ---
    all_rtl_content = ""
    for rtl_path in rtl_files:
        if os.path.exists(rtl_path):
            try:
                fchecker = FormalChecker(rtl_path=rtl_path)
                fchecker.clock_signal = clk
                fchecker.reset_signal = rst
                checker_props.extend(fchecker.generate_properties())
                with open(rtl_path) as f:
                    all_rtl_content += f.read() + "\n"
            except Exception as e:
                print(f"  [!] Could not analyze {rtl_path}: {e}")

    # 5. Merge properties (dedup by name)
    all_props_map: Dict[str, FormalProperty] = {}
    for p in spec_props + checker_props:
        if p.name not in all_props_map:
            all_props_map[p.name] = p
    all_props = list(all_props_map.values())

    print(f"  Properties: {len(all_props)} total")
    print(f"    - From spec:  {len(spec_props)}")
    print(f"    - From RTL:   {len(checker_props)}")
    print(f"    - Asserts: {sum(1 for p in all_props if p.kind == 'assert')}")
    print(f"    - Assumes: {sum(1 for p in all_props if p.kind == 'assume')}")
    # ---
    print(f"    - Covers:  {sum(1 for p in all_props if p.kind == 'cover')}")

    # 6. Generate .sby config
    config = FormalCheckConfig(
        module_name=module,
        depth=depth,
        engine=engine,
        properties=all_props,
        rtl_files=rtl_files,
    )
    # Override config properties with ours
    config.properties = all_props

    sby_content = config.to_sby()
    sby_path = os.path.join(formal_out, f"{module}.sby")
    with open(sby_path, "w") as f:
        f.write(sby_content)
    print(f"  [OK] .sby -> {sby_path}")

    # 7. Generate SVA bind module
    sva_content = config.to_sva_module()
    # Patch the sva module to use the correct reset polarity from spec
    rst_polarity = spec_data.get("rst_polarity_expr", "rstn")
    sva_path = os.path.join(formal_out, f"formal_{module}.sv")
    with open(sva_path, "w") as f:
        # ---
        f.write(sva_content)
    print(f"  [OK] SVA  -> {sva_path}")

    # 8. Run sby if available
    sby_result = {"status": "not_run", "output": ""}
    if run_sby:
        try:
            print(f"  Running sby (depth={depth}, engine={engine})...")
            result = subprocess.run(
                ["sby", "-f", sby_path],
                capture_output=True, text=True, timeout=300,
                cwd=formal_out
            )
            sby_result["output"] = result.stdout + "\n" + result.stderr
            if result.returncode == 0:
                sby_result["status"] = "PASS"
                print(f"  [OK] sby PASSED")
            else:
                sby_result["status"] = "FAIL"
                print(f"  [X] sby FAILED (rc={result.returncode})")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        except FileNotFoundError:
            print(f"  [!] sby not found on PATH — skipping execution")
            sby_result["status"] = "not_found"
            sby_result["output"] = "sby (SymbiYosys) not installed"
        # ---
        except subprocess.TimeoutExpired:
            print(f"  [!] sby timed out after 300s")
            sby_result["status"] = "timeout"
        except Exception as e:
            print(f"  [!] sby error: {e}")
            sby_result["status"] = "error"
            sby_result["output"] = str(e)

    # 9. Generate report
    report_lines = []
    report_lines.append(f"# Formal Verification Report: {module}")
    report_lines.append("")
    report_lines.append(f"**Spec:** `{os.path.basename(spec_path)}`")
    report_lines.append(f"**Engine:** {engine}")
    report_lines.append(f"**Depth:** {depth}")
    report_lines.append(f"**Total Properties:** {len(all_props)}")
    report_lines.append(f"  - Asserts: {sum(1 for p in all_props if p.kind == 'assert')}")
    report_lines.append(f"  - Assumes: {sum(1 for p in all_props if p.kind == 'assume')}")
    report_lines.append(f"  - Covers:  {sum(1 for p in all_props if p.kind == 'cover')}")
    report_lines.append(f"**sby Status:** {sby_result['status']}")
    report_lines.append("")
    report_lines.append("## Generated Files")
    report_lines.append("")
    report_lines.append(f"| File | Description |")
    report_lines.append(f"|------|-------------|")
    # ---
    report_lines.append(f"| `formal_{module}.sv` | SVA bind module |")
    report_lines.append(f"| `{module}.sby` | SymbiYosys config |")
    report_lines.append(f"| `formal_report.md` | This report |")
    report_lines.append("")

    # FSM properties section
    fsm = spec_data.get("fsm", {})
    if fsm and fsm.get("states"):
        report_lines.append("## FSM Coverage")
        report_lines.append("")
        report_lines.append(f"**FSM:** {fsm.get('name', 'fsm')} ({fsm.get('type', 'unknown')})")
        report_lines.append(f"**States:** {len(fsm['states'])}")
        report_lines.append(f"**Transitions:** {len(fsm.get('transitions', []))}")
        report_lines.append("")
        report_lines.append("| State | Cover Property |")
        report_lines.append("|-------|---------------|")
        for s in fsm["states"]:
            report_lines.append(f"| {s['name']} | `reach_{fsm.get('name', 'fsm')}_{s['name']}` |")
        report_lines.append("")

    # Properties table
    report_lines.append("## Properties")
    report_lines.append("")
    report_lines.append("| # | Name | Kind | Category | Description |")
    report_lines.append("|---|------|------|----------|-------------|")
    # ---
    for i, p in enumerate(all_props):
        desc_short = p.description[:60] + "..." if len(p.description) > 60 else p.description
        report_lines.append(f"| {i+1} | `{p.name}` | {p.kind} | {p.category} | {desc_short} |")
    report_lines.append("")

    # RTL files used
    if rtl_files:
        report_lines.append("## RTL Files Analyzed")
        report_lines.append("")
        for rf in rtl_files:
            short = os.path.relpath(rf, PROJECT_DIR) if os.path.exists(rf) else rf
            report_lines.append(f"- `{short}`")
        report_lines.append("")

    report_lines.append("## How to Run")
    report_lines.append("")
    report_lines.append("```bash")
    report_lines.append(f"cd {formal_out}")
    report_lines.append(f"sby -f {module}.sby")
    report_lines.append("```")
    report_lines.append("")

    report = "\n".join(report_lines)
    report_path = os.path.join(formal_out, "formal_report.md")
    with open(report_path, "w") as f:
        # ---
        f.write(report)
    print(f"  [OK] Report -> {report_path}")
    print(f"{'='*60}\n  FORMAL-CHECK COMPLETE ({module.upper()})\n{'='*60}")

    # Metadata for pipeline checkpoint
    result_meta = {
        "module": module,
        "spec": os.path.basename(spec_path),
        "engine": engine,
        "depth": depth,
        "total_properties": len(all_props),
        "asserts": sum(1 for p in all_props if p.kind == 'assert'),
        "assumes": sum(1 for p in all_props if p.kind == 'assume'),
        "covers": sum(1 for p in all_props if p.kind == 'cover'),
        "sby_status": sby_result["status"],
        "files_generated": [sva_path, sby_path, report_path],
    }

    with open(os.path.join(formal_out, "formal_meta.json"), "w") as f:
        json.dump(result_meta, f, indent=2)

    return result_meta


# ── CLI entry point ───────────────────────────────────────────────────

# ── main ──
def main():
    parser = argparse.ArgumentParser(description="Formal property generation and sby runner")
    parser.add_argument("--spec", default="",
                        help="Path to spec YAML file")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"),
                        help="Output directory (default: ../output)")
    parser.add_argument("--depth", type=int, default=20,
                        help="Formal depth for sby (default: 20)")
    parser.add_argument("--engine", default="smtbmc",
                        help="Formal engine: smtbmc, abc, aiger, yices, z3 (default: smtbmc)")
    parser.add_argument("--no-run", action="store_true",
                        help="Skip sby execution (generate files only)")

    args = parser.parse_args()

    # Resolve spec path
    spec_path = args.spec if args.spec else os.path.join(BASE_DIR, "..", "i2c_spec.yml")
    if not os.path.exists(spec_path):
        spec_path = os.path.join(BASE_DIR, "..", "uart_spec.yml")
    if not os.path.exists(spec_path):
        spec_path = os.path.join(BASE_DIR, "..", "spi_slave_spec.yml")
    if not os.path.exists(spec_path):
        print(f"  [X] No spec file found at {spec_path}")
        sys.exit(1)
# ---

    outdir = os.path.abspath(args.out)

    result = run_formal_pipeline(
        spec_path=spec_path,
        outdir=outdir,
        run_sby=not args.no_run,
        depth=args.depth,
        engine=args.engine,
    )

    from validators import validate_formal_check
    val_result = validate_formal_check(outdir)
    for iss in val_result.get("issues", []):
        print(f"  [{iss['severity']}] {iss.get('file', '')}: {iss['message']}")
    if not val_result.get("passed", True):
        print(f"  [VALIDATION] formal-check FAILED")
        sys.exit(1)
    else:
        print(f"  [VALIDATION] formal-check PASSED")


if __name__ == "__main__":
    main()
