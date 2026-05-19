#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coverage-plan — protocol-agnostic coverage generation"""

import os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from template_engine import build_spec_data, render_to_file

BASE_DIR = os.path.dirname(__file__)
parser = argparse.ArgumentParser()
parser.add_argument("--spec", default="")
parser.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"))
args = parser.parse_args()

SPEC_PATH = args.spec if args.spec else os.path.join(BASE_DIR, "..", "i2c_spec.yml")
if not os.path.exists(SPEC_PATH):
    SPEC_PATH = os.path.join(BASE_DIR, "..", "uart_spec.yml")
if not os.path.exists(SPEC_PATH):
    print(f"  [X] No spec file found"); sys.exit(1)

data = build_spec_data(SPEC_PATH)
module = data["module_name"]
OUT_DIR = os.path.abspath(args.out)
COV_DIR = os.path.join(OUT_DIR, "rtl", "verification", "env", "coverage")
os.makedirs(COV_DIR, exist_ok=True)

ok = render_to_file("coverage/cov.sv.tpl", data, os.path.join(COV_DIR, f"{module}_cov.sv"))
if not ok:
    print(f"  [X] Coverage template render failed — aborting")
    sys.exit(1)

print(f"{'='*60}")
print(f"  COVERAGE-PLAN — {module.upper()}")
print(f"{'='*60}")

from validators import validate_coverage_plan
result = validate_coverage_plan(SPEC_PATH if args.spec else "", OUT_DIR)
for iss in result["issues"]:
    print(f"  [{iss['severity']}] {iss.get('file','')}: {iss['message']}")
if not result["passed"]:
    print(f"  [VALIDATION] coverage-plan FAILED"); sys.exit(1)
else:
    print(f"  [VALIDATION] coverage-plan PASSED")
print(f"{'='*60}\n  COVERAGE-PLAN COMPLETE ({module.upper()})\n{'='*60}")
