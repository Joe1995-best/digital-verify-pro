#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator, sby, yosys

"""run_spec_analyzer.py — part of digital-verify-pro."""
"""
digital-verify-pro spec-analyzer v2 — spec.yml → verification plan

Major upgrade:
- Protocol-aware scenario generation (I2C, DMA, SPI, GPIO, UART)
- Register field-level comprehensive tests (reserved bits, W1C, W1S, mixed access)
- Transaction-level functional scenarios
- Concurrent and stress scenarios based on interface topology
- Coverage-driven scenario prioritization
"""

import atexit, tempfile  # cleanup
import yaml, os, json, datetime, sys, argparse, re
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

BASE_DIR = os.path.dirname(__file__)
PROJ_DIR = os.path.dirname(BASE_DIR)  # project root (one level up from pipeline/)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, PROJ_DIR)
from template_engine import build_spec_data

parser = argparse.ArgumentParser(description="Spec analyzer v2: spec.yml → verification plan")
# ---
parser.add_argument("--spec", default="", help="Path to spec YAML file")
parser.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"), help="Output directory")
args = parser.parse_args()

# ── Spec loading ─────────────────────────────────────────────────────────────

SPEC_PATH = args.spec if args.spec else os.path.join(BASE_DIR, "..", "i2c_spec.yml")
if not os.path.exists(SPEC_PATH):
    SPEC_PATH = os.path.join(BASE_DIR, "..", "uart_spec.yml")
if not os.path.exists(SPEC_PATH):
    print(f"  [X] No spec file found. Use --spec <path>")
    sys.exit(1)

OUT_DIR = os.path.abspath(args.out)
os.makedirs(f"{OUT_DIR}/architect", exist_ok=True)

with open(SPEC_PATH, "r", encoding="utf-8") as f:
    spec = yaml.safe_load(f)

data = build_spec_data(SPEC_PATH)
module = spec["module"]
module_name = module["name"]

print(f"{'='*60}")
print(f"  SPEC-ANALYZER v2 — {module_name.upper()} Verification Planner")
# ---
print(f"{'='*60}")
print(f"  Module:      {module_name}")
print(f"  Description: {module['description']}")
print(f"  Version:     {module['version']}")
print()

# ── Detect protocols and interface topology ──────────────────────────────────

PROTOCOL_TYPES = {i["type"].upper() for i in spec.get("interfaces", [])
                  # Check condition
                  if i["type"].upper() != "APB" and i["type"].upper() != "INTERRUPT"}
has_interrupt = any(i["type"].upper() == "INTERRUPT" for i in spec.get("interfaces", []))
has_apb = any(i["type"].upper() == "APB" for i in spec.get("interfaces", []))

# Count key signal types
all_signals = []
for iface in spec.get("interfaces", []):
    all_signals.extend(s.get("name", "").lower() for s in iface.get("signals", []))

has_fifo = any("fifo" in s for s in all_signals) or "fifo" in spec.get("module", {}).get("description", "").lower()
has_valid_ready = any(s in all_signals for s in ["valid", "ready", "tvalid", "tready"])

print(f"{''*60}")
print(f"  [1/4] INTERFACE DETECTION (v2 — protocol-aware)")
print(f"{''*60}")

interfaces = []
for iface in spec["interfaces"]:
    sig_count = len(iface.get("signals", []))
    info = {
        "name": iface["name"],
        "type": iface["type"],
        "direction": iface["direction"],
        "signals": sig_count,
        "data_width": iface.get("data_width", 32),
    }
    interfaces.append(info)
    proto_tag = " ★" if iface["type"].upper() in PROTOCOL_TYPES else ""
    print(f"  [OK] {iface['type']:<16} {iface['name']:<14} "
          f"direction={iface['direction']:<7} signals={sig_count}{proto_tag}")

with open(f"{OUT_DIR}/architect/interface-list.yml", "w") as f:
    yaml.dump({"interfaces": interfaces, "protocols": list(PROTOCOL_TYPES)}, f, default_flow_style=False)

# ── Register Map Analysis (v2 — enhanced) ────────────────────────────────────

print(f"\n{''*60}")
print(f"  [2/4] REGISTER MAP ANALYSIS (v2 — field-level)")
print(f"{''*60}")

register_summary = []
# ---
field_types = {"rw": 0, "ro": 0, "wo": 0, "w1c": 0, "w1s": 0, "rc_w1s": 0}
access_types: Set[str] = set()
total_fields = 0
addr_holes = []
reserved_regions = []
reg_access_map: Dict[str, str] = {}  # name -> composite access string

for i, reg in enumerate(spec.get("registers", [])):
    offset = int(reg["offset"], 16) if isinstance(reg.get("offset"), str) else 0
    fields = reg.get("fields", [])
    reg_access_set = set()
    field_detail = []

    for f in fields:
        access = f["access"].lower()
        # Normalize known access types
        norm_access = access
        for known in ("w1c", "w1s", "rc_w1s", "rw", "ro", "wo"):
            if known in access:
                norm_access = known
                break
        field_types[norm_access] = field_types.get(norm_access, 0) + 1
        reg_access_set.add(norm_access)
        access_types.add(norm_access)
        total_fields += 1
# ---

        bits_str = f.get("bits", "[0]")
        field_detail.append({
            "name": f["name"],
            "bits": bits_str,
            "access": norm_access,
            "reset": f.get("reset", "0"),
        })

    # Reserved field detection
    reserved_fields = [f for f in fields if f.get("access", "").lower() == "ro" and "reserved" in f.get("name", "").lower()]

    reg_info = {
        "name": reg["name"],
        "offset_hex": reg["offset"],
        "offset_dec": offset,
        "reset": reg["reset"],
        "fields": len(fields),
        "reserved_fields": len(reserved_fields),
        "access": ", ".join(sorted(reg_access_set)),
        "field_detail": field_detail,
        "description": reg["description"],
    }
    register_summary.append(reg_info)
    reg_access_map[reg["name"]] = ", ".join(sorted(reg_access_set))
# ---

    # Access breakdown
    print(f"   {reg['offset']:<8} {reg['name']:<20} "
          f"reset={reg['reset']:<6} fields={len(fields)} "
          f"[{', '.join(sorted(reg_access_set))}]"
          f"{' ← reserved:' + str(len(reserved_fields)) if reserved_fields else ''}")

    # Address holes
    if i > 0:
        prev_offset = int(spec["registers"][i-1]["offset"], 16)
        gap = offset - prev_offset - 4
        if gap > 0:
            addr_holes.append({
                "from_hex": spec["registers"][i-1]["offset"],
                "to_hex": reg["offset"],
                "bytes": gap,
            })

# Find total address space
last_reg = spec["registers"][-1] if spec.get("registers") else None
if last_reg:
    last_offset = int(last_reg["offset"], 16)
    addr_space_end = last_offset + 4
    # Check if there's a gap at the end (up to max addr)
    if spec["interfaces"]:
        # ---
        for iface in spec["interfaces"]:
            addr_width = iface.get("addr_width", 0)
            if addr_width:
                max_addr = 2 ** addr_width
                if addr_space_end < max_addr - 4:
                    remaining = max_addr - addr_space_end
                    reserved_regions.append({
                        "from_hex": f"0x{addr_space_end:X}",
                        "to_hex": f"0x{max_addr - 1:X}",
                        "bytes": remaining,
                    })

if addr_holes:
    print(f"\n  [!]  Address holes ({len(addr_holes)}):")
    for h in addr_holes:
        print(f"     {h['from_hex']} → {h['to_hex']}: {h['bytes']} bytes")

if reserved_regions:
    print(f"\n  [!]  Reserved regions at end of address space:")
    for r in reserved_regions:
        print(f"     {r['from_hex']} → {r['to_hex']}: {r['bytes']} bytes")

print(f"\n  Field access breakdown:")
for at, count in sorted(field_types.items()):
    if count > 0:
        # ---
        print(f"     {at.upper():>8}: {count:>3}")
print(f"     {'TOTAL':>8}: {total_fields:>3}")

reg_map = {
    "module": module_name,
    "base_address": "0x1000_0000",
    "registers": register_summary,
    "address_holes": addr_holes,
    "reserved_regions": reserved_regions,
    "field_stats": field_types,
}
with open(f"{OUT_DIR}/architect/register-map.yml", "w") as f:
    yaml.dump(reg_map, f, default_flow_style=False)

# ── v3 Feature-Driven Test Scenario Generation ────────────────────────────

print(f"\n{''*60}")
print(f"  [3/4] TEST SCENARIOS (v3 — feature-driven decomposition)")
print(f"{''*60}")

from engines.feature_decomposer import decompose_features, render_json as fd_json

# Feature-driven decomposition: generates testpoints from spec features
feature_tps = decompose_features(spec)
feature_scenarios = fd_json(feature_tps)
# ---

# Read user-defined scenarios
scenarios = []
user_defined = spec.get("verification", {}).get("test_scenarios", [])
for t in user_defined:
    detail = t.get("detail") or t.get("description", "")
    if "sequence" in t:
        steps = "\n        ".join(t["sequence"])
        detail += f"\n        Steps: {steps}"
    scenarios.append({
        "name": t["name"],
        "description": t["description"],
        "config": t.get("config", "default"),
        "detail": detail,
        "category": "user_defined",
    })

auto_count = 0
registers = spec.get("registers", [])

# ═════════════════════════════════════════════════════════════════════════════
# SECTION A: Register-Level Tests (enhanced)
# ═════════════════════════════════════════════════════════════════════════════

scenarios.append({
        # ---
        "name": t["name"],
        "description": t["description"],
        "config": t.get("config", "default"),
        "detail": detail,
        "category": "user_defined",
        "stage": "V1",
        "stimulus": "User-defined: see description",
        "checking": "Per user specification",
    })

# ── Merge feature-driven testpoints ──
for fs in feature_scenarios:
    scenarios.append(fs)

user_count = len(user_defined)
auto_count = len(feature_scenarios)
total = len(scenarios)

# Count gaps
gaps = [s for s in feature_scenarios if s.get("rtl_status", "IMPLEMENTED") != "IMPLEMENTED"]

print(f"   User-defined scenarios: {user_count}")
for t in user_defined:
    print(f"   {t['name']:<28} {t['description'][:50]}")

print(f"\n   Feature-driven scenarios: {auto_count}")
fd_by_feat = {}
for s in feature_scenarios:
    feat = s.get("feature", "unknown")
    fd_by_feat.setdefault(feat, []).append(s)
for feat, items in sorted(fd_by_feat.items()):
    n_gap = sum(1 for i in items if i.get("rtl_status", "IMPLEMENTED") != "IMPLEMENTED")
    n_impl = len(items) - n_gap
    gs = f"  [{n_gap} GAPS]" if n_gap else ""
    print(f"     {feat:<25} {len(items):2} scenarios ({n_impl} impl, {n_gap} gap){gs}")

if gaps:
    print(f"\n  [!] {len(gaps)} UNIMPLEMENTED features detected:")
    for g in gaps[:5]:
        print(f"      {g['name']:<40} rtl_status={g['rtl_status']}")
    if len(gaps) > 5:
        print(f"      ... and {len(gaps)-5} more")

print(f"\n   Total: {total} scenarios ({user_count} user + {auto_count} feature-driven, {len(gaps)} gaps)")

with open(f"{OUT_DIR}/architect/test-scenarios.yml", "w") as f:
    yaml.dump({
        "test_scenarios": scenarios,
        "summary": {
            "total": total,
            # ---
            "user_defined": user_count,
            "auto_generated": auto_count,
            "gaps": len(gaps),
        }
    }, f, default_flow_style=False)

# ── Coverage Analysis (v2 — enhanced) ────────────────────────────────────────

print(f"\n{''*60}")
print(f"  [4/4] COVERAGE ANALYSIS (v2)")
print(f"{''*60}")

cov = spec.get("verification", {}).get("coverage_goals", {})
fc = cov.get("functional", [])
cc = cov.get("cross", [])
tc = cov.get("toggle", [])

# Auto-generate coverage goals from register analysis
auto_fc = []
auto_cc = []

# Per-register coverage
for r in registers:
    rw_fields = [f for f in r.get("fields", []) if f["access"].lower() in ("rw", "wo")]
    ro_fields = [f for f in r.get("fields", []) if f["access"].lower() == "ro"]
    # ---
    if rw_fields:
        auto_fc.append(f"All RW fields of {r['name']} written and read back")
    if ro_fields:
        auto_fc.append(f"All RO fields of {r['name']} verified write-ignored")

# Per-protocol coverage
if "I2C" in PROTOCOL_TYPES:
    auto_fc.append("I2C START and STOP conditions generated")
    auto_fc.append("I2C ACK and NACK received")
    auto_fc.append("I2C 7-bit and 10-bit addressing modes")
    auto_fc.append("I2C multi-master arbitration")
    auto_cc.append("I2C speed × transaction type (write/read/combined)")
    auto_cc.append("I2C FIFO state × interrupt status")

if "DMA" in PROTOCOL_TYPES:
    auto_fc.append("DMA single and burst transfers")
    auto_fc.append("DMA scatter-gather linked list traversal")
    auto_cc.append("DMA transfer size × source/dest address alignment")

if has_interrupt:
    auto_fc.append("All interrupt sources asserted and cleared")
    auto_cc.append("Interrupt source × transaction in progress")

# FIFO coverage
if has_fifo:
    # ---
    auto_fc.append("FIFO full, empty, threshold crossing")
    auto_cc.append("FIFO write count × read count")

# Print
all_fc = fc + auto_fc
all_cc = cc + auto_cc
print(f"  Functional cover points: {len(fc)} user + {len(auto_fc)} auto = {len(all_fc)}")
if auto_fc:
    print(f"  Auto-generated functional points:")
    for c in auto_fc[:8]:
        print(f"     + {c}")
    if len(auto_fc) > 8:
        print(f"     … (+{len(auto_fc)-8} more)")
print(f"  Cross coverage bins:     {len(cc)} user + {len(auto_cc)} auto = {len(all_cc)}")
if auto_cc:
    for c in auto_cc:
        print(f"     + {c}")
if tc:
    print(f"  Toggle signals:          {len(tc)}")

# ── Verification Plan Generation ─────────────────────────────────────────────

print(f"\n{''*60}")
print(f"   GENERATING VERIFICATION PLAN (v2)")
print(f"{''*60}")
# ---

protocol_types = [i["type"] for i in interfaces if i["type"].upper() not in ("APB", "INTERRUPT")]
proto = ", ".join(protocol_types) if protocol_types else "APB-mapped"

# Build test scenario table by category
def flatten_category(scenarios, cat_prefix):
    """Return scenarios matching a category prefix."""
      # return computed value
    return [s for s in scenarios if s.get("category", "").startswith(cat_prefix)]

reg_rw = flatten_category(scenarios, "register_rw")
reg_ro = flatten_category(scenarios, "register_ro")
reg_reset = flatten_category(scenarios, "register_reset")
reg_reserved = flatten_category(scenarios, "register_reserved")
reg_bitbash = flatten_category(scenarios, "register_bitbash")
reg_atomic = flatten_category(scenarios, "register_atomic")
reg_rmw = flatten_category(scenarios, "register_rmw")
reg_field = flatten_category(scenarios, "register_field")
reg_adj = flatten_category(scenarios, "register_adjacent")
proto_scenarios = flatten_category(scenarios, "protocol")
stress_scenarios = flatten_category(scenarios, "stress")
user_scenarios = flatten_category(scenarios, "user_defined")

vp = f"""# {module_name.upper()} Verification Plan v2
# Generated: {datetime.datetime.now()}

## 1. Overview

**Module**: {module_name} ({module['version']})
**Description**: {module['description']}

| Parameter | Value |
|-----------|-------|
| Clock | {spec['clocks'][0]['frequency'] if spec.get('clocks') else 'N/A'} ({spec['clocks'][0]['name'] if spec.get('clocks') else 'N/A'}) |
| Reset | {spec['resets'][0]['name'] if spec.get('resets') else 'N/A'} ({spec['resets'][0]['polarity'] if spec.get('resets') else 'N/A'}) |
| Data width | {interfaces[0].get('data_width', 32) if interfaces else 32}-bit |
| Address width | 12-bit |
| Interfaces | {len(interfaces)} ({', '.join(i['type'] for i in interfaces)}) |
| Registers | {len(register_summary)} |
| Fields | {total_fields} ({', '.join(f'{k.upper()}:{v}' for k,v in sorted(field_types.items()) if v > 0)}) |
| Protocols | {proto} |

## 2. Verification Interfaces

| Interface | Type | Direction | Signals | Data Width |
|-----------|------|-----------|---------|------------|
"""
for i in interfaces:
    vp += f"| {i['name']} | {i['type']} | {i['direction']} | {i['signals']} | {i.get('data_width', 32)} |\n"

vp += f"""
# ---
## 3. Register Map Summary

| Address | Register | Reset | Access | Fields | Reserved |
|---------|----------|-------|--------|--------|----------|
"""
for r in register_summary:
    vp += f"| {r['offset_hex']} | {r['name']} | {r['reset']} | {r['access']} | {r['fields']} | {r['reserved_fields']} |\n"

if addr_holes:
    vp += "\n### Address Holes\n"
    for h in addr_holes:
        vp += f"- `{h['from_hex']}` → `{h['to_hex']}`: {h['bytes']} bytes reserved (expect PSLVERR)\n"

if reserved_regions:
    vp += "\n### Reserved Regions\n"
    for r in reserved_regions:
        vp += f"- `{r['from_hex']}` → `{r['to_hex']}`: {r['bytes']} bytes (expect PSLVERR)\n"

# ── Test Plan ──
total = len(scenarios)
vp += f"""
## 4. Test Plan ({total} total: {user_count} user + {auto_count} auto)

### 4.1 User-Defined Scenarios ({user_count})
"""
for s in user_scenarios:
    vp += f"- **{s['name']}**: {s['description']}\\n"

vp += f"""
### 4.2 Register RW Tests ({len(reg_rw)})
"""
for s in reg_rw:
    vp += f"- `{s['name']}`: {s['description']}\\n"

vp += f"""
### 4.3 Register RO Tests ({len(reg_ro)})
"""
for s in reg_ro:
    vp += f"- `{s['name']}`: {s['description']}\\n"

vp += f"""
### 4.4 Reset Value Tests ({len(reg_reset)})
"""
for s in reg_reset:
    vp += f"- `{s['name']}`: {s['description']}\\n"

if reg_reserved:
    vp += f"""
### 4.5 Reserved Bit Tests ({len(reg_reserved)})
"""
    for s in reg_reserved:
        vp += f"- `{s['name']}`: {s['description']}\\n"

if reg_bitbash:
    vp += f"""
### 4.6 Bit-Bash Tests ({len(reg_bitbash)})
"""
    for s in reg_bitbash:
        vp += f"- `{s['name']}`: {s['description']}\\n"

if reg_atomic:
    vp += f"""
### 4.7 Atomic W1C/W1S Tests ({len(reg_atomic)})
"""
    for s in reg_atomic:
        vp += f"- `{s['name']}`: {s['description']}\\n"

if reg_rmw:
    vp += f"""
### 4.8 Read-Modify-Write Tests ({len(reg_rmw)})
"""
    for s in reg_rmw:
        vp += f"- `{s['name']}`: {s['description']}\\n"

if reg_field:
    # ---
    vp += f"""
### 4.9 Field Sequential Tests ({len(reg_field)})
"""
    for s in reg_field:
        vp += f"- `{s['name']}`: {s['description']}\\n"

if reg_adj:
    vp += f"""
### 4.10 Adjacent Register Pair Tests ({len(reg_adj)})
"""
    for s in reg_adj:
        vp += f"- `{s['name']}`: {s['description']}\\n"

# Protocol scenarios by sub-category
proto_by_type = defaultdict(list)
for s in proto_scenarios:
    proto_by_type[s.get("category", "protocol_other")].append(s)

for pcat in sorted(proto_by_type):
    pscenarios = proto_by_type[pcat]
    pcat_display = pcat.replace("protocol_", "").upper()
    vp += f"""
### 4.{10 + len(proto_by_type)} Protocol: {pcat_display} Tests ({len(pscenarios)})
"""
    for s in pscenarios:
        # ---
        vp += f"- `{s['name']}`: {s['description']}\\n"

# Stress scenarios by sub-category
stress_by_type = defaultdict(list)
for s in stress_scenarios:
    stress_by_type[s.get("category", "stress_other")].append(s)

for scat in sorted(stress_by_type):
    sscenarios = stress_by_type[scat]
    scat_display = scat.replace("stress_", "").upper()
    vp += f"""
### 4.{10 + len(proto_by_type) + len(stress_by_type)} Stress: {scat_display} ({len(sscenarios)})
"""
    for s in sscenarios:
        vp += f"- `{s['name']}`: {s['description']}\\n"

# ── Coverage Plan ──
vp += f"""
## 5. Coverage Plan

### Functional Coverage ({len(all_fc)} total)
"""
for c in all_fc:
    vp += f"- `{c}`\\n"

if all_cc:
    vp += "\\n### Cross Coverage\\n"
    for c in all_cc:
        vp += f"- `{c}`\\n"

# ── Pass Criteria ──
vp += f"""
## 6. Pass Criteria

| Criterion | Target |
|-----------|--------|
| All {total} test scenarios | 100% PASS |
| Register reset values | All match spec |
| RW write/read consistency | All RW registers/fields |
| RO write-ignored | All RO registers/fields |
| Reserved bits stuck-at-0 | All reserved bit positions |
| Address holes → PSLVERR | All holes and reserved regions |
| Bit-bash: bit independence | All multi-bit fields |
| W1C/W1S atomicity | All atomic fields |
| Protocol: {proto} | Key scenarios pass |
| Reset during transaction | No bus hang, clean state |
| CSR auto-test | ALL RESET OK |
| Toggle coverage | >80% |
| Functional coverage | >90% |

## 7. Sign-off Checklist

- [ ] All {total} test scenarios pass ({user_count} user + {auto_count} auto)
- [ ] All {len(register_summary)} register reset values verified
- [ ] All RW fields: write/read consistent
- [ ] All RO fields: write-ignored confirmed
- [ ] All reserved bits: read-as-zero confirmed
- [ ] All W1C/W1S fields: atomic operation correct
- [ ] Protocol correctness via functional scenarios
- [ ] Address holes return PSLVERR
- [ ] Reset during active transaction → clean state
- [ ] All {len(all_fc)} functional coverage points hit
- [ ] All {len(all_cc)} cross coverage bins hit
- [ ] Toggle coverage >80%
- [ ] C header: sw/{module_name}.h generated
- [ ] Knowledge captured in wiki/
"""

with open(f"{OUT_DIR}/verification-plan.md", "w") as f:
    f.write(vp)

# ── Enrich scenarios with OT-style stimulus/checking/stage ──
stage_map = {
    "register_rw": "V1", "register_ro": "V1", "register_reset": "V1",
    "register_reserved": "V1", "register_bitbash": "V1",
    # ---
    "register_rmw": "V2", "register_field": "V2", "register_adjacent": "V1",
    "register_atomic": "V2",
    "protocol_i2c": "V1", "protocol_spi": "V1",
    "protocol_dma": "V1", "protocol_fifo": "V1",
    "protocol_interrupt": "V1",
    "stress_register": "V2", "stress_bus": "V1",
    "stress_address": "V2", "stress_reset": "V2",
    "stress_performance": "V3",
    "user_defined": "V1",
}
default_stimulus = "Apply configured stimulus to the design"
default_checking = "Verify output matches expected behavior per spec"

for sc in scenarios:
    cat = sc.get("category", "user_defined")
    name = sc.get("name", "")
    desc = sc.get("description", "")
    # Feature-driven testpoints already have correct stage; don't override
    if sc.get("feature"):
        pass  # keep existing stage from feature_decomposer
    else:
        sc["stage"] = stage_map.get(cat, "V1")

    # Auto-generate stimulus
    stim = sc.get("stimulus", "")
    # ---
    if not stim:
        if desc.startswith("Write") or "write" in desc[:30].lower():
            stim = f"{desc.split('.')[0] if '.' in desc else desc}"
        elif desc.startswith("After reset"):
            stim = f"Assert and deassert reset, then read register"
        elif desc.startswith("Assert"):
            stim = f"Drive trigger condition, then clear via register write"
        elif "I2C" in desc or "SPI" in desc:
            stim = "Drive protocol interface signals per transaction sequence"
        elif "FIFO" in desc:
            stim = "Drive FIFO control signals; observe status flags"
        elif "Interrupt" in desc or "interrupt" in desc:
            stim = "Trigger interrupt condition; service via status read or write"
        elif "stress" in cat:
            stim = "Apply maximum load: fastest config, largest data, back-to-back cycles"
        else:
            stim = default_stimulus
    sc["stimulus"] = stim

    # Auto-generate checking
    chk = sc.get("checking", "")
    if not chk:
        if cat in ("register_rw",):        chk = "Read data equals written data; field access verified"
        elif cat in ("register_ro",):      chk = "Write ignored; read returns reset value"
        elif cat in ("register_reset",):    chk = "All fields match spec reset values"
        # ---
        elif cat in ("register_reserved",): chk = "Reserved bits read as 0; writable bits unaffected"
        elif cat in ("register_bitbash",):  chk = "Each bit toggles independently; no aliasing"
        elif cat in ("register_rmw",):      chk = "RO fields unchanged; RW fields updated"
        elif cat in ("register_adjacent",): chk = "No cross-talk between adjacent registers"
        elif "protocol" in cat:             chk = "Protocol sequence completes; data correct; flags match"
        elif "fifo" in cat:                 chk = "FIFO flags correct; data integrity maintained"
        elif "interrupt" in cat:            chk = "Interrupt asserts on trigger; clears on service"
        elif "stress" in cat:               chk = "No corruption under load; all accesses complete"
        else:                               chk = default_checking
    sc["checking"] = chk

    # OT-style desc: embed Stimulus/Checking as labeled blocks
    ot_desc = f"{desc}"
    sc["desc"] = f"""Stimulus:\n  {stim}\nChecking:\n  {chk}"""

    # tests field: link to test sequence
    sc["tests"] = [f"{name}_test"]

# Inject into spec_data.json
data["test_scenarios"] = scenarios
data["num_test_scenarios"] = len(scenarios)
data["num_auto_scenarios"] = auto_count
data["coverage_goals"] = {
    "functional": all_fc,
    "cross": all_cc,
    # ---
    "toggle": tc,
}

spec_data_path = f"{OUT_DIR}/architect/spec_data.json"
with open(spec_data_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, default=str)

# ── Summary ──────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  [OK] SPEC-ANALYZER v2 COMPLETE")
print(f"{'='*60}")
print(f"  Output directory: {OUT_DIR}/")
print(f"  {'architect/interface-list.yml':<40} {len(interfaces)} interfaces ({len(PROTOCOL_TYPES)} protocols)")
print(f"  {'architect/register-map.yml':<40} {len(register_summary)} regs, {total_fields} fields, {len(access_types)} access types")
print(f"  {'architect/test-scenarios.yml':<40} {total} test scenarios ({user_count} user + {auto_count} feature)")
# Group by feature for summary
_feat_cats = {}
for s in feature_scenarios:
    f = s.get('feature', 'unknown')
    _feat_cats[f] = _feat_cats.get(f, 0) + 1
for feat, cnt in sorted(_feat_cats.items()):
    print(f"     {feat:<25} {cnt}")
if gaps:
    print(f"     {'--- GAPS ---':<25} {len(gaps)}")
# ---
print(f"  {'architect/spec_data.json':<40} Normalized spec + auto scenarios + coverage")
print(f"  {'verification-plan.md':<40} Full v2 verification plan")
print(f"  Coverage goals: {len(all_fc)} functional + {len(all_cc)} cross")
print(f"{'='*60}")

# Validation
sys.path.insert(0, BASE_DIR)
from validators import validate_spec_analyzer
result = validate_spec_analyzer(SPEC_PATH, OUT_DIR)
for iss in result["issues"]:
    print(f"  [{iss['severity']}] {iss.get('file','')}: {iss['message']}")
if not result["passed"]:
    print(f"  [VALIDATION] spec-analyzer FAILED — see issues above")
    sys.exit(1)
else:
    print(f"  [VALIDATION] spec-analyzer v2 PASSED")
