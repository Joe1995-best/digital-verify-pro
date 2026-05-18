#!/usr/bin/env python3
"""
render_verification_plan.py — Feature-driven verification plan renderer.

Reads spec_data.json (with feature-driven testpoints), generates:
- verification-plan.md (human-readable)
- Can be extended to generate HJSON, HTML, etc.

Usage:
  python render_verification_plan.py --data <spec_data.json> --output <verification-plan.md>
"""

import os, sys, json, argparse
from collections import defaultdict
from datetime import datetime


def load_spec_data(path: str) -> dict:
    """Load spec_data.json and return the data dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render(data: dict) -> str:
    """Render verification plan markdown from spec_data.json."""
    module_name = data.get("module_name", "unknown")
    module_desc = data.get("module_desc", "")
    scenarios = data.get("test_scenarios", [])
    registers = data.get("registers", [])
    interfaces = data.get("interfaces", [])
    coverage = data.get("coverage_goals", {})
    all_fc = coverage.get("functional", [])
    all_cc = coverage.get("cross", [])

    # Count stats
    user_scenarios = [s for s in scenarios if s.get("category") == "user_defined"]
    feature_scenarios = [s for s in scenarios if s.get("category") != "user_defined"]
    gaps = [s for s in feature_scenarios if s.get("rtl_status", "IMPLEMENTED") != "IMPLEMENTED"]
    total = len(scenarios)

    # Group by feature
    by_feature = defaultdict(list)
    for s in feature_scenarios:
        by_feature[s.get("feature", "unknown")].append(s)

    # Stage counts
    v1 = sum(1 for s in scenarios if s.get("stage") == "V1")
    v2 = sum(1 for s in scenarios if s.get("stage") == "V2")
    v3 = sum(1 for s in scenarios if s.get("stage") == "V3")
    n_gaps = len(gaps)

    lines = []
    lines.append(f"# {module_name.upper()} Verification Plan (Feature-Driven)")
    lines.append(f"# Generated: {datetime.now()}")
    lines.append("")

    # ═══ 1. Overview ═══
    lines.append("## 1. Overview")
    lines.append("")
    lines.append(f"**Module**: {module_name}")
    lines.append(f"**Description**: {module_desc}")
    lines.append("")
    lines.append("**Verification Strategy:** Feature-driven decomposition. "
                 "Testpoints are generated from spec features, not RTL structure. "
                 "Each feature produces 1+ testpoints with explicit stimulus and checking. "
                 "Gaps (UNIMPLEMENTED features) are flagged explicitly.")
    lines.append("")

    # Interface summary
    if interfaces:
        lines.append("| Interface | Type | Direction | Signals |")
        lines.append("|-----------|------|-----------|---------|")
        for i in interfaces:
            lines.append(f"| {i.get('name','')} | {i.get('type','')} | {i.get('direction','')} | {len(i.get('signals',[]))} |")
        lines.append("")

    # Register map
    if registers:
        lines.append("## 2. Register Map Summary")
        lines.append("")
        lines.append("| Address | Register | Reset | Access | Fields |")
        lines.append("|---------|----------|-------|--------|--------|")
        for r in registers:
            name = r.get("name") if isinstance(r, dict) else r
            offset = r.get("offset") if isinstance(r, dict) else ""
            reset = r.get("reset") if isinstance(r, dict) else ""
            access = r.get("access") if isinstance(r, dict) else ""
            fields = r.get("fields") if isinstance(r, dict) else 0
            lines.append(f"| {offset} | {name} | {reset} | {access} | {fields} |")
        lines.append("")

    # ═══ 3. Test Plan ═══
    lines.append(f"## 3. Test Plan ({total} total: {len(user_scenarios)} user + {len(feature_scenarios)} feature-driven)")
    lines.append("")

    # Summary table
    lines.append("### Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total testpoints | {total} |")
    lines.append(f"| User-defined | {len(user_scenarios)} |")
    lines.append(f"| Feature-driven | {len(feature_scenarios)} |")
    lines.append(f"| V1 (smoke) | {v1} |")
    lines.append(f"| V2 (stress) | {v2} |")
    lines.append(f"| V3 (signoff) | {v3} |")
    lines.append(f"| Gaps (UNIMPLEMENTED) | {n_gaps} |")
    if n_gaps > 0:
        lines.append(f"| Coverage risk | **{n_gaps} features not yet implemented in RTL** |")
    lines.append("")

    # User scenarios
    if user_scenarios:
        lines.append("### User-Defined Scenarios")
        lines.append("")
        for s in user_scenarios:
            lines.append(f"- **{s['name']}**: {s.get('description','')}")
        lines.append("")

    # Feature-driven section
    lines.append("### Feature-Driven Testpoints")
    lines.append("")
    lines.append("_Each feature is decomposed into 1+ testpoints with explicit stimulus and checking._")
    lines.append("")

    for feat in sorted(by_feature.keys()):
        tps = by_feature[feat]
        n_ok = sum(1 for t in tps if t.get("rtl_status", "IMPLEMENTED") == "IMPLEMENTED")
        n_gap = sum(1 for t in tps if t.get("rtl_status", "IMPLEMENTED") != "IMPLEMENTED")
        tag = f"  [{n_gap} GAP]" if n_gap else ""
        lines.append(f"#### Feature: {feat}{tag}")
        lines.append("")
        lines.append("| Testpoint | Stage | Status | Stimulus | Checking |")
        lines.append("|-----------|-------|--------|----------|----------|")
        for tp in tps:
            stim = tp.get("stimulus", "")[:60]
            chk = tp.get("checking", "")[:60]
            status = tp.get("rtl_status", "IMPLEMENTED")
            lines.append(f"| {tp['name']} | {tp.get('stage','?')} | {status} | {stim}... | {chk}... |")
        lines.append("")

    # ═══ 4. Gaps ═══
    if gaps:
        lines.append("## 4. Coverage Gaps")
        lines.append("")
        lines.append("_These testpoints correspond to features described in the spec "
                     "but not yet implemented in the RTL. They serve as an RTL development backlog._")
        lines.append("")
        lines.append("| Testpoint | Feature | Stage | Status | Stimulus |")
        lines.append("|-----------|---------|-------|--------|----------|")
        for g in gaps:
            lines.append(f"| {g['name']} | {g.get('feature','?')} | {g.get('stage','?')} | {g.get('rtl_status','?')} | {g.get('stimulus','')[:50]} |")
        lines.append("")

    # ═══ 5. Coverage Plan ═══
    lines.append("## 5. Coverage Plan")
    lines.append("")

    if all_fc:
        lines.append("### Functional Coverage")
        lines.append("")
        for fc in all_fc:
            lines.append(f"- `{fc}`")
        lines.append("")

    if all_cc:
        lines.append("### Cross Coverage")
        lines.append("")
        for cc in all_cc:
            lines.append(f"- `{cc}`")
        lines.append("")

    # ═══ 6. Pass Criteria ═══
    lines.append("## 6. Pass Criteria")
    lines.append("")
    criteria = [
        ("All testpoints", "100% PASS"),
        ("Register reset values", "All match spec"),
        ("RW write/read consistency", "All RW registers/fields"),
        ("RO write-ignored", "All RO registers/fields"),
        ("Reserved bits stuck-at-0", "All reserved positions"),
        ("Protocol correctness", "Per-feature stimulus/checking"),
        ("Gap resolution", f"All {n_gaps} gaps closed before signoff"),
        ("Toggle coverage", ">80%"),
        ("Functional coverage", ">90%"),
    ]
    lines.append("| Criterion | Target |")
    lines.append("|-----------|--------|")
    for crit, target in criteria:
        lines.append(f"| {crit} | {target} |")
    lines.append("")

    # ═══ 7. Signoff ═══
    lines.append("## 7. Sign-off Checklist")
    lines.append("")
    checkboxes = [
        f"All {len(user_scenarios)} user-defined scenarios pass",
        f"All {len(feature_scenarios)} feature-driven testpoints pass",
        f"All {n_gaps} gaps resolved or explicitly waived",
        "All register reset values verified against spec",
        "All RW fields: write/read consistent",
        "All RO fields: write-ignored confirmed",
        "All reserved bits: read-as-zero confirmed",
        "Protocol correctness via feature testpoints",
        f"V1 smoke tests: {v1} testpoints",
        f"V2 stress tests: {v2} testpoints",
        f"V3 signoff tests: {v3} testpoints",
        "Toggle coverage >80%",
        "Functional coverage >90%",
    ]
    for cb in checkboxes:
        lines.append(f"- [ ] {cb}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Feature-driven verification plan renderer")
    parser.add_argument("--data", required=True, help="Path to spec_data.json")
    parser.add_argument("--output", "-o", default="", help="Output markdown path")
    args = parser.parse_args()

    data = load_spec_data(args.data)
    md = render(data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"[OK] Plan written to {args.output}")
    else:
        print(md)


if __name__ == "__main__":
    main()
