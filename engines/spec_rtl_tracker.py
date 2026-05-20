#!/usr/bin/env python3
"""
spec_rtl_tracker.py — Spec-RTL consistency tracking.

Extracts register declarations from RTL (.sv) files and cross-references
them against the spec YAML to detect mismatches, missing registers,
and bit-width inconsistencies.

Usage:
    report = compare_with_spec("spec.yml", "rtl/")
    for issue in report:
        print(issue)
"""
import os
import re
import json
from pathlib import Path
from typing import Optional


def extract_regs_from_rtl(rtl_dir: str) -> list[dict]:
    """Extract register/logic declarations from .sv files in rtl_dir.

    Returns list of dicts with keys: name, width, file, line.

    Matches common patterns:
      - logic [N:0] name;
      - reg [N:0] name;
      - logic name;  (width=1 implied)
    """
    rtl_root = Path(rtl_dir)
    if not rtl_root.is_dir():
        return []

    results: list[dict] = []
    # Pattern: optional 'reg' or 'logic' followed by optional range, then name
    # Matches:
    #   logic [3:0]  ctrl_reg;
    #   reg  [7:0]   data;
    #   logic        flag;
    #   logic [31:0] mem [0:1023];  (we skip the array part)
    re_reg = re.compile(
        r"^\s*(?:reg|logic)\s+"           # type
        r"(?:\[(\d+)\s*:\s*(\d+)\]\s+)?"  # optional bit range [msb:lsb]
        r"(\w+)"                           # name
        r"(?:\s*\[.*?\])?"                 # optional array dimension (skip)
        r"\s*[;=]",                         # terminator: ; or =
        re.MULTILINE
    )

    # Also match 'wire' with range that looks like a register
    re_wire_reg = re.compile(
        r"^\s*wire\s+"
        r"(?:\[(\d+)\s*:\s*(\d+)\]\s+)?"
        r"(\w+)\s*[;=]",
        re.MULTILINE
    )

    for sv_path in sorted(rtl_root.rglob("*.sv")):
        rel_path = sv_path.relative_to(rtl_root)
        try:
            text = sv_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue

        for m in re_reg.finditer(text):
            msb = m.group(1)
            lsb = m.group(2)
            name = m.group(3)
            if msb and lsb:
                width = int(msb) - int(lsb) + 1
            else:
                width = 1
            lineno = text[:m.start()].count("\n") + 1
            results.append({
                "name": name,
                "width": width,
                "file": str(rel_path),
                "line": lineno,
            })

        for m in re_wire_reg.finditer(text):
            msb = m.group(1)
            lsb = m.group(2)
            name = m.group(3)
            if not any(r["name"] == name for r in results):
                if msb and lsb:
                    width = int(msb) - int(lsb) + 1
                else:
                    width = 1
                lineno = text[:m.start()].count("\n") + 1
                results.append({
                    "name": name,
                    "width": width,
                    "file": str(rel_path),
                    "line": lineno,
                })

    return results


def compare_with_spec(spec_path: str, rtl_dir: str) -> list[dict]:
    """Compare spec.yml register definitions with RTL declarations.

    Args:
        spec_path: Path to spec YAML file with a "registers" array.
        rtl_dir: Path to RTL source directory.

    Returns:
        List of inconsistency reports, each a dict with:
          type: "missing_in_rtl", "missing_in_spec", "width_mismatch"
          name: register name
          spec_width: width from spec (or None)
          rtl_width: width from RTL (or None)
          description: human-readable explanation
    """
    import yaml  # lazy import

    issues: list[dict] = []

    # 1. Load spec
    try:
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        return [{"type": "error", "description": f"Cannot load spec: {e}"}]

    spec_regs: dict[str, int] = {}
    for reg in spec.get("registers", []):
        rname = reg.get("name", "")
        # Infer width from fields if not directly specified
        fields = reg.get("fields", [])
        if fields:
            max_bit = 0
            for f in fields:
                bits = str(f.get("bits", "0"))
                if ":" in bits:
                    try:
                        msb, lsb = bits.split(":")
                        max_bit = max(max_bit, int(msb))
                    except ValueError:
                        pass
                else:
                    try:
                        max_bit = max(max_bit, int(bits))
                    except ValueError:
                        pass
            width = max_bit + 1
        else:
            width = 32  # default register width
        spec_regs[rname] = width

    # 2. Extract RTL regs
    rtl_regs: dict[str, int] = {}
    for r in extract_regs_from_rtl(rtl_dir):
        rtl_regs[r["name"]] = r["width"]

    # 3. Compare
    all_names = set(spec_regs) | set(rtl_regs)

    for name in sorted(all_names):
        sw = spec_regs.get(name)
        rw = rtl_regs.get(name)

        if sw is not None and rw is None:
            issues.append({
                "type": "missing_in_rtl",
                "name": name,
                "spec_width": sw,
                "rtl_width": None,
                "description": f"Register '{name}' (width={sw}) defined in spec but not found in RTL",
            })
        elif sw is None and rw is not None:
            issues.append({
                "type": "missing_in_spec",
                "name": name,
                "spec_width": None,
                "rtl_width": rw,
                "description": f"Register '{name}' (width={rw}) found in RTL but not in spec",
            })
        elif sw is not None and rw is not None and sw != rw:
            issues.append({
                "type": "width_mismatch",
                "name": name,
                "spec_width": sw,
                "rtl_width": rw,
                "description": f"Register '{name}': spec width={sw} but RTL width={rw}",
            })

    return issues
