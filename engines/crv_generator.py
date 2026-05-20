"""
CRV Generator — Constrained Random Verification.

Parses YAML spec constraints (range, enum, dist) and generates
SystemVerilog rand + constraint blocks.

Usage:
    from engines.crv_generator import parse_constraints, generate_sv_constraint

    constraints = parse_constraints("i2c_spec.yml")
    sv_code = generate_sv_constraint("i2c_ctrl", constraints)
"""

import yaml
import os
from typing import Any


# ── Constraint parsing ──────────────────────────────────────────────────────

Constraint = dict[str, Any]  # {"field": ..., "type": "range"|"enum"|"dist", ...}


def parse_constraints(spec_path: str) -> list[Constraint]:
    """Read a YAML spec file and extract the ``constraints`` top-level field.

    Returns a list of constraint dicts with keys:
        field  — signal/variable name
        type   — "range" | "enum" | "dist"
        width  — integer bit width
        body   — type-specific payload:
            range: {"min": …, "max": …, "align": …}  (align optional)
            enum:  {"values": [v1, v2, …]}            (or {})
            dist:  {"items": [{"value": …, "weight": …}, …]}

    If ``spec_path`` does not contain a ``constraints`` section, returns [].
    """
    if not os.path.isfile(spec_path):
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    with open(spec_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw = data.get("constraints", [])
    if not raw:
        return []

    constraints: list[Constraint] = []
    for entry in raw:
        c: Constraint = {
            "field": entry["field"],
            "type": entry["type"],
            "width": entry.get("width", 8),
            "body": {},
        }
        if c["type"] == "range":
            c["body"] = {
                "min": entry.get("min", 0),
                "max": entry.get("max", 2**c["width"] - 1),
                "align": entry.get("align"),
            }
        elif c["type"] == "enum":
            c["body"] = {
                "values": entry.get("values", []),
            }
        elif c["type"] == "dist":
            c["body"] = {
                "items": entry.get("items", []),
            }
        else:
            raise ValueError(f"Unknown constraint type: {c['type']}")
        constraints.append(c)

    return constraints


# ── SV code generation ──────────────────────────────────────────────────────

def _width_decl(width: int) -> str:
    if width <= 1:
        return ""
    return f"bit [{width-1}:0] "


def _emit_range(c: Constraint) -> list[str]:
    field = c["field"]
    body = c["body"]
    lines: list[str] = []
    w = c["width"]

    # Declare random variable
    lines.append(f"    rand {_width_decl(w)}{field};")

    # Constraint body
    lines.append(f"    constraint c_{field} {{")

    if body.get("align") is not None:
        align = body["align"]
        lines.append(f"        {field} inside {{[{body['min']}:{body['max']}]}};")
        if align == 2:
            lines.append(f"        {field}[0:0] == 1'b0;")
        elif align == 4:
            lines.append(f"        {field}[1:0] == 2'b00;")
        elif align == 8:
            lines.append(f"        {field}[2:0] == 3'b000;")
        else:
            lines.append(f"        {field} % {align} == 0;")
    else:
        lines.append(f"        {field} inside {{[{body['min']}:{body['max']}]}};")

    lines.append("    }")
    return lines


def _emit_enum(c: Constraint) -> list[str]:
    field = c["field"]
    values = c["body"].get("values", [])
    lines: list[str] = []
    w = c["width"]

    lines.append(f"    rand {_width_decl(w)}{field};")
    lines.append(f"    constraint c_{field} {{")
    vals = ", ".join(str(v) for v in values)
    lines.append(f"        {field} inside {{{vals}}};")
    lines.append("    }")
    return lines


def _emit_dist(c: Constraint) -> list[str]:
    field = c["field"]
    items = c["body"].get("items", [])
    lines: list[str] = []
    w = c["width"]

    lines.append(f"    rand {_width_decl(w)}{field};")
    lines.append(f"    constraint c_{field} {{")
    dist_entries = []
    for item in items:
        v = item["value"]
        wt = item.get("weight", 1)
        dist_entries.append(f"            {v} := {wt}")
    lines.append(f"        {field} dist {{")
    lines.append(",\n".join(dist_entries))
    lines.append("        };")
    lines.append("    }")
    return lines


_GENERATORS = {
    "range": _emit_range,
    "enum": _emit_enum,
    "dist": _emit_dist,
}


def generate_sv_constraint(class_name: str, constraints: list[Constraint]) -> str:
    """Generate complete SystemVerilog ``class …; rand …; constraint …; endclass``.

    Args:
        class_name: Identifier for the SV class wrapper.
        constraints: List of parsed constraint dicts.

    Returns:
        SV source code as a string.
    """
    lines: list[str] = []
    lines.append(f"class {class_name};")

    for c in constraints:
        gen = _GENERATORS.get(c["type"])
        if gen is None:
            raise ValueError(f"Unsupported constraint type: {c['type']}")
        lines.append("")
        lines.extend(gen(c))

    lines.append("")
    lines.append("endclass")
    lines.append("")
    return "\n".join(lines)


# ── Convenience ─────────────────────────────────────────────────────────────

def generate_from_spec(spec_path: str, class_name: str | None = None) -> str:
    """One-shot: parse spec constraints and emit SV code."""
    constraints = parse_constraints(spec_path)
    if not constraints:
        return f"// No constraints found in {spec_path}"
    name = class_name or "auto_crv"
    return generate_sv_constraint(name, constraints)
