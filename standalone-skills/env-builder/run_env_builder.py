#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env-builder — protocol-agnostic UVM environment generator.

Takes spec data (interfaces, registers, signals) and renders
generic templates — no protocol-specific code paths.
Protocols (I2C, GPIO, SPI, UART, AXI, PCIe) are all handled
identically through template iteration over spec data.
"""

import os, sys, json, argparse

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)
from template_engine import build_spec_data, render_to_file

# ── Render error tracking ──
_render_errors = 0
def _render(tpl, data, path):
    global _render_errors
    ok = render_to_file(tpl, data, path)
    if not ok:
        _render_errors += 1
        print(f"  [X] RENDER FAILED: {tpl}")
    return ok

parser = argparse.ArgumentParser()
parser.add_argument("--spec", default="")
parser.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"))
args = parser.parse_args()

# ── Spec discovery ──
SPEC_PATH = args.spec if args.spec else os.path.join(BASE_DIR, "..", "i2c_spec.yml")
if not os.path.exists(SPEC_PATH):
    SPEC_PATH = os.path.join(BASE_DIR, "..", "uart_spec.yml")
if not os.path.exists(SPEC_PATH):
    print(f"  [X] No spec file found")
    sys.exit(1)

data = build_spec_data(SPEC_PATH)
module = data["module_name"]
OUT_DIR = os.path.abspath(args.out)
ENV_DIR = os.path.join(OUT_DIR, "rtl", "verification", "env")

# ── Create directory structure ──
for sub in ["agents", "interfaces", "sequences", "sim", "assertions",
            "scoreboard", "coverage", "tests", "bfm"]:
    os.makedirs(os.path.join(ENV_DIR, sub), exist_ok=True)

# Print interface summary
iface_types = [i["type"] for i in data["interfaces"]]
print(f"{'='*60}")
print(f"  ENV-BUILDER — {module.upper()} UVM Environment")
print(f"  Interfaces: {', '.join(iface_types)}")
print(f"{'='*60}")

# ═════════════════════════════════════════════════════════════
# 1. INTERFACE TEMPLATES — Render one per interface type
# ═════════════════════════════════════════════════════════════

for iface in data["interfaces"]:
    iftype = iface["type"].lower()
    if iftype == "apb":
        _render("interface_apb.sv.tpl", data,
                os.path.join(ENV_DIR, "interfaces", "apb_if.sv"))
    elif iftype == "interrupt":
        _render("interface_interrupt.sv.tpl", data,
                os.path.join(ENV_DIR, "interfaces", "intr_if.sv"))
    else:
        iface_data = dict(data, interface=iface)
        ifname = f"{iface['name']}_if.sv"
        _render("interface.sv.tpl", iface_data,
                os.path.join(ENV_DIR, "interfaces", ifname))

# ═════════════════════════════════════════════════════════════
# 2. AGENT TEMPLATES
# ═════════════════════════════════════════════════════════════

_render("transaction_apb.sv.tpl", data,
        os.path.join(ENV_DIR, "agents", "apb_txn.sv"))
_render("sequencer.sv.tpl", data,
        os.path.join(ENV_DIR, "agents", "apb_sequencer.sv"))
_render("driver.sv.tpl", data,
        os.path.join(ENV_DIR, "agents", "apb_driver.sv"))
_render("monitor.sv.tpl", data,
        os.path.join(ENV_DIR, "agents", "apb_monitor.sv"))
_render("agent.sv.tpl", data,
        os.path.join(ENV_DIR, "agents", "apb_agent.sv"))
print(f"  [GEN] agents/ (apb_txn, sequencer, driver, monitor, agent)")

# ═════════════════════════════════════════════════════════════
# 3. ENVIRONMENT + TEST + PACKAGE
# ═════════════════════════════════════════════════════════════

_render("env.sv.tpl", data,
        os.path.join(ENV_DIR, f"{module}_env.sv"))
_render("base_test.sv.tpl", data,
        os.path.join(ENV_DIR, "base_test.sv"))
_render("env_pkg.sv.tpl", data,
        os.path.join(ENV_DIR, "env_pkg.sv"))

# ═════════════════════════════════════════════════════════════
# 4. SEQUENCES
# ═════════════════════════════════════════════════════════════

_render("base_seq.sv.tpl", data,
        os.path.join(ENV_DIR, "sequences", "base_seq.sv"))
_render("reset_seq.sv.tpl", data,
        os.path.join(ENV_DIR, "sequences", "reset_seq.sv"))
_render("apb_rw_seq.sv.tpl", data,
        os.path.join(ENV_DIR, "sequences", "apb_rw_seq.sv"))
print(f"  [GEN] sequences/ (base_seq, reset_seq, apb_rw_seq)")

# ═════════════════════════════════════════════════════════════
# 5. SCOREBOARD
# ═════════════════════════════════════════════════════════════

_render("scoreboard.sv.tpl", data,
        os.path.join(ENV_DIR, "scoreboard", f"{module}_sb.sv"))

# ═════════════════════════════════════════════════════════════
# 6. BFM
# ═════════════════════════════════════════════════════════════

if data["protocol"]:
    bfm_data = dict(data, protocol=data["protocol"])
    _render("bfm.sv.tpl", bfm_data,
            os.path.join(ENV_DIR, "bfm", f"{module}_bfm.sv"))

# ═════════════════════════════════════════════════════════════
# 7. ASSERTIONS
# ═════════════════════════════════════════════════════════════

_render("assertions/apb_assert.sv.tpl", data,
        os.path.join(ENV_DIR, "assertions", "apb_assert.sv"))
_render("assertions/reset_assert.sv.tpl", data,
        os.path.join(ENV_DIR, "assertions", "reset_assert.sv"))
_render("assertions/reg_assert.sv.tpl", data,
        os.path.join(ENV_DIR, "assertions", "reg_assert.sv"))
print(f"  [GEN] assertions/ (apb_assert, reset_assert, reg_assert)")

# ═════════════════════════════════════════════════════════════
# 8. COVERAGE
# ═════════════════════════════════════════════════════════════

_render("coverage/cov.sv.tpl", data,
        os.path.join(ENV_DIR, "coverage", f"{module}_cov.sv"))

# ═════════════════════════════════════════════════════════════
# 9. SIMULATION INFRASTRUCTURE
# ═════════════════════════════════════════════════════════════

_render("sim/Makefile.tpl", data,
        os.path.join(ENV_DIR, "sim", "Makefile"))
_render("sim/run_py.tpl", data,
        os.path.join(ENV_DIR, "sim", "run.py"))

# ═════════════════════════════════════════════════════════════
# 10. FUSESOC CORE
# ═════════════════════════════════════════════════════════════

_render("fusesoc/core.tpl", data,
        os.path.join(OUT_DIR, f"{module}.core"))
print(f"  [GEN] {module}.core (FuseSoC)")

# ═════════════════════════════════════════════════════════════
# 11. CSR EXCLUSIONS
# ═════════════════════════════════════════════════════════════

csr_excl = {
    "module": module,
    "description": data.get("module_desc", ""),
    "excluded": [],
}
for r in data["registers"]:
    rname = r["name"]
    ro_only = all(f.get("access", "rw") == "ro" for f in r.get("fields", []))
    wo_only = all(f.get("access", "rw") == "wo" for f in r.get("fields", []))
    if ro_only:
        csr_excl["excluded"].append({
            "register": rname, "reason": "Read-only",
            "skip_read_check": False, "skip_write_check": True,
        })
    elif wo_only:
        csr_excl["excluded"].append({
            "register": rname, "reason": "Write-only (read undefined)",
            "skip_read_check": True, "skip_write_check": False,
        })
with open(os.path.join(ENV_DIR, "csr_excl.json"), "w", encoding="utf-8") as f:
    json.dump(csr_excl, f, indent=2)
print(f"  [GEN] csr_excl.json ({len(csr_excl['excluded'])} exclusions)")

# ═════════════════════════════════════════════════════════════
# 12. REGRESSION TEST
# ═════════════════════════════════════════════════════════════

_render("regression_test.sv.tpl", data,
        os.path.join(ENV_DIR, "tests", f"{module}_regression_test.sv"))

# ═════════════════════════════════════════════════════════════
# 13. TB TOP
# ═════════════════════════════════════════════════════════════

_render("tb_top.sv.tpl", data,
        os.path.join(ENV_DIR, "tb_top.sv"))
print(f"  [GEN] tb_top.sv")

# ═════════════════════════════════════════════════════════════
# 14. VALIDATION
# ═════════════════════════════════════════════════════════════

sys.path.insert(0, BASE_DIR)
from validators import validate_env_builder

# Fail fast on template render errors
if _render_errors > 0:
    print(f"  [X] Pipeline abort: {_render_errors} template(s) failed to render")
    print(f"  [FIX] Check templates above for syntax errors")
    sys.exit(1)

result = validate_env_builder(OUT_DIR)
for iss in result.get("issues", []):
    print(f"  [{iss['severity']}] {iss.get('file','')}: {iss['message']}")
if not result.get("passed", True):
    print(f"  [VALIDATION] env-builder FAILED")
    sys.exit(1)
else:
    print(f"  [VALIDATION] env-builder PASSED")

print(f"{'='*60}")
print(f"  ENV-BUILDER COMPLETE ({module.upper()})")
print(f"{'='*60}")
