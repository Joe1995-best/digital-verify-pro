#!/usr/bin/env python3
"""Tests for skill_common"""
import sys, os, json, tempfile
_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# _base = standalone-skills/ directory
if _base not in sys.path:
    sys.path.insert(0, _base)
from skill_common import ExitCode, get_logger, write_result, load_config, common_args

# ---- ExitCode ----
assert ExitCode.SUCCESS == 0
assert ExitCode.INPUT_ERROR == 1
assert "Input/argument" in ExitCode.describe(1)
assert ExitCode.describe(99) == "Internal error \u2014 unexpected exception"
assert "Unknown" in ExitCode.describe(98)
print("[PASS] ExitCode")

# ---- Logger ----
logger = get_logger("test_logger")
assert logger.level == 20
logger.info("test log (stderr)")
print("[PASS] Logger")

# ---- write_result ----
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "result.json")
    write_result({"status": "pass", "module": "test", "summary": "OK"}, p)
    with open(p) as f:
        d = json.load(f)
    assert d["status"] == "pass"
    assert d["module"] == "test"
    assert "timestamp" in d
print("[PASS] write_result")

# ---- load_config (missing) ----
cfg = load_config("/nonexistent/config.yaml")
assert cfg == {}
print("[PASS] load_config (missing)")

# ---- common_args ----
parser = common_args("test skill")
args = parser.parse_args(["--spec", "test.yml"])
assert args.spec == "test.yml"
assert args.out == "output"
print("[PASS] common_args")

print("\nAll skill_common tests PASS")
