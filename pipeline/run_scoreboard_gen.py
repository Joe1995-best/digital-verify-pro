#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scoreboard-gen — protocol-agnostic scoreboard generation"""

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
SB_DIR = os.path.join(OUT_DIR, "rtl", "verification", "env", "scoreboard")
os.makedirs(SB_DIR, exist_ok=True)

render_to_file("scoreboard.sv.tpl", data, os.path.join(SB_DIR, f"{module}_sb.sv"))
print(f"{'='*60}")
print(f"  SCOREBOARD-GEN — {module.upper()}")
print(f"{'='*60}")

from validators import validate_scoreboard_gen
result = validate_scoreboard_gen(OUT_DIR)
for iss in result["issues"]:
    print(f"  [{iss['severity']}] {iss.get('file','')}: {iss['message']}")
if not result["passed"]:
    print(f"  [VALIDATION] scoreboard-gen FAILED"); sys.exit(1)
else:
    print(f"  [VALIDATION] scoreboard-gen PASSED")
print(f"{'='*60}\n  SCOREBOARD-GEN COMPLETE ({module.upper()})\n{'='*60}")
