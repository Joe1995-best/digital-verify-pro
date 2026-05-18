#!/usr/bin/env python3
"""
coverage_gap_plugin.py v2 — Coverage gap → test regeneration bridge.

Generates gap-filling test scenarios + SV sequences.
Detects UVM vs plain-Verilog TB and generates compatible code.

Usage:
  # UVM mode (with spec_data)
  python coverage_gap_plugin.py --gaps gaps.json --spec spec.yml --out ./output

  # Plain Verilog mode (standalone gap_filler module)
  python coverage_gap_plugin.py --gaps gaps.json --module alu4 --out ./output --plain
"""

import os, sys, json, yaml, argparse
from typing import Dict, List
from collections import defaultdict

parser = argparse.ArgumentParser(description="Coverage gap → test regenerator v2")
parser.add_argument("--gaps", required=True, help="Coverage gaps JSON")
parser.add_argument("--spec", default="", help="Spec YAML (UVM mode)")
parser.add_argument("--module", default="", help="Module name (plain mode)")
parser.add_argument("--out", default=".", help="Output directory")
parser.add_argument("--plain", action="store_true", help="Plain Verilog mode (no UVM)")
args = parser.parse_args()

GAPS_PATH = os.path.abspath(args.gaps)
OUT_DIR = os.path.abspath(args.out)

if not os.path.exists(GAPS_PATH):
    print(f"[X] Gaps file not found: {GAPS_PATH}")
    sys.exit(1)

with open(GAPS_PATH, "r", encoding="utf-8") as f:
    gaps_data = json.load(f)

gaps = gaps_data.get("gaps", [])
suggested = gaps_data.get("suggested_tests", [])
overall = gaps_data.get("overall", 100.0)
module_name = args.module or gaps_data.get("module", "unknown")

print(f"{'='*60}")
print(f"  COVERAGE GAP PLUGIN v2")
print(f"  Module: {module_name}  Overall: {overall}%")
print(f"  Mode: {'Plain Verilog' if args.plain else 'UVM'}")
print(f"  Gaps: {len(gaps)}  Suggested: {len(suggested)}")
print(f"{'='*60}")

if not gaps and not suggested:
    print("  [OK] No coverage gaps detected — coverage is sufficient!")
    sys.exit(0)

# ── Generate gap-driven test scenarios ───────────────────────────────────────

new_scenarios = []

# Critical toggle gaps
for g in gaps:
    sev = g.get("severity", 0)
    sig = g["signal"]
    gt = g["gap_type"]

    if gt == "no_toggle" and sev >= 4:
        new_scenarios.append({
            "name": f"cov_toggle_{sig}",
            "description": f"Toggle {sig}: drive to 0 and 1",
            "category": "cov_gap_toggle", "priority": 1,
        })
    elif gt == "no_toggle" and sev == 3:
        new_scenarios.append({
            "name": f"cov_warn_toggle_{sig}",
            "description": f"Toggle {sig}: improve coverage",
            "category": "cov_gap_toggle", "priority": 2,
        })
    elif gt == "fsm_unvisited" and sev >= 4:
        new_scenarios.append({
            "name": f"cov_fsm_{sig}",
            "description": f"Reach FSM state {sig}",
            "category": "cov_gap_fsm", "priority": 1,
        })
    elif gt == "half_toggle":
        new_scenarios.append({
            "name": f"cov_complete_{sig}",
            "description": f"Complete toggle for {sig}",
            "category": "cov_gap_half", "priority": 2,
        })
    elif gt == "low_activity" and sev <= 2:
        new_scenarios.append({
            "name": f"cov_stress_{sig}",
            "description": f"Increase toggle rate for {sig}",
            "category": "cov_gap_stress", "priority": 3,
        })
    elif gt == "condition" and sev >= 3:
        new_scenarios.append({
            "name": f"cov_cond_{sig}",
            "description": f"Exercise missing condition for {sig}",
            "category": "cov_gap_cond", "priority": 2,
        })

for s in suggested:
    new_scenarios.append({
        "name": s.get("name", f"cov_suggested_{len(new_scenarios)}"),
        "description": s.get("description", ""),
        "category": "cov_gap_suggested",
        "priority": s.get("priority", 2),
    })

print(f"\n  Generated {len(new_scenarios)} new test scenarios")

# ── Save scenarios to YML ────────────────────────────────────────────────────

os.makedirs(os.path.join(OUT_DIR, "coverage"), exist_ok=True)
yaml_path = os.path.join(OUT_DIR, "coverage", "gap_scenarios.yml")
with open(yaml_path, "w", encoding="utf-8") as f:
    yaml.dump({"gap_scenarios": new_scenarios}, f, default_flow_style=False)
print(f"  [GEN] gap_scenarios.yml ({len(new_scenarios)} scenarios)")

# ── Merge into spec_data.json (UVM mode) ─────────────────────────────────────

spec_data_path = os.path.join(OUT_DIR, "architect", "spec_data.json")
if os.path.exists(spec_data_path):
    with open(spec_data_path, "r", encoding="utf-8") as f:
        spec_data = json.load(f)
    existing = spec_data.get("test_scenarios", [])
    existing_names = {s.get("name") for s in existing}
    added = 0
    for sc in new_scenarios:
        if sc["name"] not in existing_names:
            existing.append(sc)
            added += 1
    spec_data["test_scenarios"] = existing
    spec_data["num_test_scenarios"] = len(existing)
    with open(spec_data_path, "w", encoding="utf-8") as f:
        json.dump(spec_data, f, indent=2, default=str)
    print(f"  [MERGE] {added} scenarios merged into spec_data.json")
else:
    print(f"  [WARN] No spec_data.json — gap scenarios saved to YML only")

# ══════════════════════════════════════════════════════════════════════════════
# GENERATE SV FILES
# ══════════════════════════════════════════════════════════════════════════════

gap_generated = []

for sc in new_scenarios:
    name = sc["name"]
    desc = sc["description"]
    gtype = sc.get("category", "cov_gap")

    if args.plain:
        # ── Plain Verilog: standalone module ──
        # Drives TB signals via hierarchical path: `tb_module.signal`
        # Simpler: generates a `gap_filler_<name>` module that drives DUT inputs

        verilog_code = f"""// Coverage gap closing sequence: {name}
// {desc}
// Auto-generated by coverage_gap_plugin.py (plain Verilog mode)

module gap_filler_{name} ();
    initial begin
        #100;  // Wait for original TB to finish

        // Gap: {gtype} - {desc}
        $display("[GAP] {name}: {desc}");

        // Drive tb_top signals through hierarchical paths
        // Most designs use module name 'tb_' + <module_name>
        // Customize these paths for your design

        #100;
        $display("[GAP] {name} complete");
        #10;
    end
endmodule
"""
        path = os.path.join(OUT_DIR, "coverage", f"gap_filler_{name}.sv")

    else:
        # ── UVM mode: sequence class ──
        if "toggle" in gtype:
            seq_body = f"""  // Toggle gap: {desc}
  `uvm_info("gap", "{name}: {desc}", UVM_LOW)
  apb_rw_seq rw = apb_rw_seq::type_id::create("rw");
  rw.randomize() with {{ write==1; addr==12'h000; data==32'h0000_0001; }};
  rw.start(m_sequencer);
  rw.randomize() with {{ write==1; addr==12'h000; data==32'h0000_0000; }};
  rw.start(m_sequencer);"""
        elif "fsm" in gtype:
            seq_body = f"""  // FSM gap: {desc}
  `uvm_info("gap", "fsm: {name}", UVM_LOW)
  apb_rw_seq rw = apb_rw_seq::type_id::create("rw");
  repeat (5) begin
    rw.randomize() with {{ write==1; addr==12'h008; data==$urandom; }};
    rw.start(m_sequencer);
    #200;
  end"""
        else:
            seq_body = f"""  // Gap: {desc}
  `uvm_info("gap", "{name}: {desc}", UVM_LOW)
  #100;"""

        seq_code = f"""// {desc}
class {name}_seq extends base_seq;
  `uvm_object_utils({name}_seq)
  function new(string n = "{name}_seq"); super.new(n); endfunction
  virtual task body();
{seq_body}
  endtask
endclass : {name}_seq
"""
        path = os.path.join(OUT_DIR, "coverage", f"{name}_seq.sv")
        verilog_code = seq_code

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated by digital-verify-pro\n{verilog_code}")
    gap_generated.append(path)
    print(f"  [GEN] {os.path.basename(path)}")

# ── Summary ──────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  COVERAGE GAP PLUGIN COMPLETE ({module_name})")
print(f"{'='*60}")
print(f"  Coverage before:  {overall}%")
print(f"  New scenarios:    {len(new_scenarios)}")
print(f"  SV files:         {len(gap_generated)}")
print(f"  Next step:        Re-compile with gap_filler files")
print(f"{'='*60}")
