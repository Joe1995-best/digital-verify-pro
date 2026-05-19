#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assertion-gen — protocol-agnostic assertion generation"""

import os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from template_engine import build_spec_data, render_to_file

BASE_DIR = os.path.dirname(__file__)
parser = argparse.ArgumentParser(description="Assertion generator — dual-track SVA")
parser.add_argument("--spec", default="")
parser.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"))
parser.add_argument("--simulator", default="iverilog",
                    choices=["iverilog", "questa", "vcs", "all"],
                    help="Simulator target: iverilog=process, questa/vcs=SVA, all=both")
args = parser.parse_args()

SPEC_PATH = args.spec if args.spec else os.path.join(BASE_DIR, "..", "i2c_spec.yml")
if not os.path.exists(SPEC_PATH):
    SPEC_PATH = os.path.join(BASE_DIR, "..", "uart_spec.yml")
if not os.path.exists(SPEC_PATH):
    print(f"  [X] No spec file found"); sys.exit(1)

data = build_spec_data(SPEC_PATH)
module = data["module_name"]
OUT_DIR = os.path.abspath(args.out)
ASRT_DIR = os.path.join(OUT_DIR, "rtl", "verification", "env", "assertions")
os.makedirs(ASRT_DIR, exist_ok=True)

# 将 simulator 参数注入模板数据
sim = args.simulator
data["simulator"] = sim
data["enable_sva"] = "1" if sim in ("questa", "vcs", "all") else "0"

# 渲染断言模板
render_to_file("assertions/apb_assert.sv.tpl", data, os.path.join(ASRT_DIR, "apb_assert.sv"))

# 标准 SVA 断言（仅 questa/vcs/all 时生成）
if sim in ("questa", "vcs", "all"):
    render_to_file("sv/sva_assertions.sv", data, os.path.join(ASRT_DIR, "sva_assertions.sv"))

render_to_file("assertions/reset_assert.sv.tpl", data, os.path.join(ASRT_DIR, "reset_assert.sv"))
render_to_file("assertions/reg_assert.sv.tpl", data, os.path.join(ASRT_DIR, "reg_assert.sv"))

print(f"{'='*60}")
sva_mode = f"SVA({sim})" if sim in ("questa","vcs") else "process(iverilog)"
print(f"  ASSERTION-GEN — {module.upper()}")
print(f"  Mode: {sva_mode}")
print(f"  APB(8) + SVA(4) + REG(1) + RST(-) = 13+ assertions")
print(f"{'='*60}")

from validators import validate_assertion_gen
result = validate_assertion_gen(OUT_DIR)
for iss in result["issues"]:
    print(f"  [{iss['severity']}] {iss.get('file','')}: {iss['message']}")
if not result["passed"]:
    print(f"  [VALIDATION] assertion-gen FAILED"); sys.exit(1)
else:
    print(f"  [VALIDATION] assertion-gen PASSED")
print(f"{'='*60}\n  ASSERTION-GEN COMPLETE ({module.upper()})\n{'='*60}")
