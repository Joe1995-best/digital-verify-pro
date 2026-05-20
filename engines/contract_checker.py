"""
CI contract compatibility checker.

Reads a skill's ``skill_spec.json`` and validates that the declared
``outputs.schema`` is compatible with the schemas required by any
``downstream_consumers`` listed in the same file.

Inspired by the principle that skills in a CI pipeline should publish
contracts that downstream consumers can actually consume.

Usage:
    from engines.contract_checker import check_contract_compatibility

    report = check_contract_compatibility("standalone-skills/coverage-engine")
    # report["status"] == "pass" | "warn" | "fail"
"""

import json
import os
from typing import Any


# ── Schema compatibility helpers ────────────────────────────────────────────

def _type_is_compatible(producer_type: Any, consumer_type: Any) -> bool:
    """Naïve type compatibility check (simple structural subtyping).

    Supports: dict, list, string, number, integer, boolean, null, and "any".
    ``null`` is treated as "match anything".  ``object`` aliases ``dict``.
    """
    if consumer_type is None or consumer_type == "any":
        return True
    if producer_type is None:
        return False

    pt = str(producer_type).lower()
    ct = str(consumer_type).lower()

    # Expand aliases
    _expand = {"object": "dict", "map": "dict", "str": "string", "int": "integer",
               "bool": "boolean", "float": "number"}
    pt = _expand.get(pt, pt)
    ct = _expand.get(ct, ct)

    return pt == ct


def _check_properties(producer: dict, consumer: dict, path: str = "") -> list[str]:
    """Recursively check that consumer-required properties exist in producer."""
    issues: list[str] = []
    producer_props = producer.get("properties", {}) if isinstance(producer, dict) else {}
    consumer_props = consumer.get("properties", {}) if isinstance(consumer, dict) else {}
    required = consumer.get("required", [])

    for req_key in required:
        if req_key not in producer_props:
            issues.append(f"{path}.{req_key}: required by consumer but missing from producer")
            continue

        p_schema = producer_props[req_key]
        c_schema = consumer_props.get(req_key, {})
        p_type = p_schema.get("type")
        c_type = c_schema.get("type")

        if not _type_is_compatible(p_type, c_type):
            issues.append(
                f"{path}.{req_key}: type mismatch "
                f"(producer={p_type}, consumer={c_type})"
            )

        # Recurse into nested object properties
        if isinstance(p_schema, dict) and isinstance(c_schema, dict):
            if p_schema.get("type", "object") == "object" or c_schema.get("type", "object") == "object":
                issues.extend(
                    _check_properties(p_schema, c_schema, f"{path}.{req_key}")
                )

    return issues


def _schema_fetch(spec: dict, schema_key: str) -> dict | None:
    """Resolve a schema reference inside the spec.

    *schema_key* can be a path e.g. ``outputs.result_schema`` or inline dict.
    Returns a dict schema or None if unresolvable.
    """
    parts = schema_key.split(".")
    obj = spec
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part, {})
        else:
            return None
    return obj if isinstance(obj, dict) else None


# ── Main entry point ────────────────────────────────────────────────────────

def check_contract_compatibility(skill_dir: str) -> dict[str, Any]:
    """Validate *skill_dir*'s output contract against downstream consumers.

    Returns a report dict with keys:
        skill_name  : str
        status      : "pass" | "warn" | "fail"
        issues      : list[str]
        details     : dict (structure depends on spec found)
    """
    spec_path = os.path.join(skill_dir, "skill_spec.json")
    if not os.path.isfile(spec_path):
        return {
            "skill_name": os.path.basename(skill_dir),
            "status": "fail",
            "issues": [f"skill_spec.json not found in {skill_dir}"],
            "details": {},
        }

    with open(spec_path, encoding="utf-8") as f:
        spec: dict = json.load(f)

    skill_name = spec.get("name", os.path.basename(skill_dir))
    issues: list[str] = []
    details: dict[str, Any] = {}

    # ── Outputs schema ──────────────────────────────────────────────────
    outputs = spec.get("interface", {}).get("outputs", {})
    output_schema_ref = outputs.get("schema") or outputs.get("result_schema")

    if output_schema_ref is None:
        issues.append("No output schema declared in interface.outputs.schema")
    else:
        details["output_schema"] = output_schema_ref

    # ── Downstream consumers ────────────────────────────────────────────
    consumers = spec.get("downstream_consumers", [])
    if not consumers:
        details["consumers"] = []
        issue_msg = "No downstream_consumers declared — contract cannot be verified"
        issues.append(issue_msg)
    else:
        details["consumers"] = []
        for consumer in consumers:
            consumer_name = consumer.get("name", "unknown")
            consumer_inputs = consumer.get("inputs", {}).get("files", [])
            for ci in consumer_inputs:
                schema_key = ci.get("schema")
                if not schema_key:
                    continue
                consumer_schema = _schema_fetch(spec, schema_key)
                if consumer_schema is None:
                    issues.append(
                        f"Consumer '{consumer_name}' requires schema '{schema_key}' "
                        "which is not resolvable in skill_spec.json"
                    )
                    continue

                # Validate producer output schema against consumer expectations
                producer_schema = _schema_fetch(spec, output_schema_ref) if isinstance(output_schema_ref, str) else output_schema_ref
                if producer_schema is None:
                    issues.append(
                        f"Producer output schema '{output_schema_ref}' not resolvable"
                    )
                    continue

                prop_issues = _check_properties(producer_schema, consumer_schema)
                issues.extend(prop_issues)
                details["consumers"].append({
                    "name": consumer_name,
                    "input_file": ci.get("path"),
                    "issues": prop_issues,
                })

    # ── Status ──────────────────────────────────────────────────────────
    if issues:
        # Some issues exist — fail if structural mismatch, warn if advisory
        severity = "fail"
        status = severity
    else:
        status = "pass"

    return {
        "skill_name": skill_name,
        "status": status,
        "issues": issues,
        "details": details,
    }
