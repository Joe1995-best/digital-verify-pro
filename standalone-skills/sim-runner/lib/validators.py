"""
validators.py — Pipeline validation gates and inter-phase contracts.

Each pipeline phase:
1. Generates its output files
2. Calls validator.validate_<phase>() to check output quality
3. Generates a contract JSON for downstream phases
"""

import os, sys, json, yaml, re, glob
from typing import Dict, List, Optional, Any

BASE_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(BASE_DIR)

# ── Utility ────────────────────────────────────────────────

# ── read_file ──
def read_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8-sig') as f: return f.read()

# ── write_file ──
def write_file(path: str, content: str) -> None:
    with open(path, 'w') as f: f.write(content)

# ── read_yaml ──
def read_yaml(path: str) -> Optional[dict]:
    with open(path, 'r', encoding='utf-8-sig') as f: return yaml.safe_load(f)
# ---

# ── read_json ──
def read_json(path: str) -> Optional[dict]:
    with open(path, 'r', encoding='utf-8-sig') as f: return json.load(f)

# ── write_json ──
def write_json(path: str, data: Any) -> None:
    with open(path, 'w') as f: json.dump(data, f, indent=2)

# ── load_contract ──
def load_contract(phase_name: str, out_dir: str) -> Optional[dict]:
    path = os.path.join(out_dir, f".contract_{phase_name}.json")
    # Check condition
    if os.path.exists(path): return read_json(path)
    return None

# ── find_sv_files ──
def find_sv_files(out_dir: str) -> List[str]:
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    if os.path.exists(env_dir):
          # return computed value
        return [f for f in glob.glob(os.path.join(env_dir, "**/*.sv"), recursive=True)]
    return []


# ═══════════════════════════════════════════════════════════
# Phase 1: spec-analyzer validation
# ═══════════════════════════════════════════════════════════

# ── validate_spec_analyzer ──
def validate_spec_analyzer(spec_path, out_dir) -> Dict:
    issues = []
    # ---
    
    # Check required output files exist
    required_files = [
        os.path.join(out_dir, "verification-plan.md"),
        os.path.join(out_dir, "architect", "interface-list.yml"),
        os.path.join(out_dir, "architect", "register-map.yml"),
        os.path.join(out_dir, "architect", "test-scenarios.yml"),
    ]
    for f in required_files:
        if not os.path.exists(f):
            issues.append({"severity": "ERROR", "file": f, "message": "Required output file missing"})
    
    # Validate register-map.yml: each register must have access type
    regmap_path = os.path.join(out_dir, "architect", "register-map.yml")
    if os.path.exists(regmap_path):
        regmap = read_yaml(regmap_path)
        for reg in regmap.get("registers", []):
            access = reg.get("access", "")
            has_ro = "ro" in access
            has_rw = "rw" in access
            has_wo = "wo" in access
            if not any([has_ro, has_rw, has_wo]):
                issues.append({"severity": "WARNING", "file": "register-map.yml", 
                              "message": f"Register {reg['name']}: no RO/RW/WO annotation in access field '{access}'"})
    
    # Validate test-scenarios.yml: each scenario has description
    scenarios_path = os.path.join(out_dir, "architect", "test-scenarios.yml")
    if os.path.exists(scenarios_path):
        scenarios = read_yaml(scenarios_path)
        for s in scenarios.get("test_scenarios", []):
            if not s.get("description"):
                issues.append({"severity": "WARNING", "file": "test-scenarios.yml",
                              "message": f"Test {s['name']}: missing description"})
    
    # Compare register-map against original spec for traceability
    if spec_path and os.path.exists(spec_path):
        spec = read_yaml(spec_path)
        spec_regs = {r["name"]: r for r in spec.get("registers", [])}
        gen_regs = {r["name"]: r for r in regmap.get("registers", [])} if os.path.exists(regmap_path) else {}
        for name in spec_regs:
            if name not in gen_regs:
                issues.append({"severity": "ERROR", "file": "register-map.yml",
                              "message": f"Register '{name}' from spec not found in generated register map"})
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
    
    # Generate contract for downstream phases
    contract = {
        "phase": "spec-analyzer",
        "status": "PASS" if passed else "FAIL",
        # ---
        "module": read_yaml(spec_path).get("module", {}) if spec_path and os.path.exists(spec_path) else {},
        "registers": [],
        "interfaces": [],
    }
    if os.path.exists(regmap_path):
        contract["registers"] = regmap.get("registers", [])
    ifcs_path = os.path.join(out_dir, "architect", "interface-list.yml")
    if os.path.exists(ifcs_path):
        contract["interfaces"] = read_yaml(ifcs_path).get("interfaces", [])
    
    write_json(os.path.join(out_dir, ".contract_spec-analyzer.json"), contract)
    
    return {
        "passed": passed,
        "issues": issues,
        "contract": contract,
    }


# ═══════════════════════════════════════════════════════════
# Phase 2: env-builder validation
# ═══════════════════════════════════════════════════════════

# ── validate_env_builder ──
def validate_env_builder(out_dir) -> Dict:
    issues = []
    # ---
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    
    # Check required env files exist
    required = ["tb_top.sv", "env_pkg.sv", "i2c_env.sv", "base_test.sv"]
    # Check condition
    if not os.path.exists(os.path.join(env_dir, "i2c_env.sv")):
        # Try to find any env.sv
        env_files = glob.glob(os.path.join(env_dir, "*_env.sv")) + glob.glob(os.path.join(env_dir, "env.sv"))
        if not env_files:
            issues.append({"severity": "ERROR", "file": "env/", "message": "No UVM environment file found"})
    
    # Check env connections
    env_path = os.path.join(env_dir, "i2c_env.sv")
    if not os.path.exists(env_path):
        env_files = glob.glob(os.path.join(env_dir, "*_env.sv"))
        if env_files: env_path = env_files[0]
    
    if os.path.exists(env_path):
        content = read_file(env_path)
        # Check that scoreboard is created in build_phase
        if "type_id::create(\"sb\"" not in content and "type_id::create(\"scoreboard\"" not in content:
            issues.append({"severity": "WARNING", "file": os.path.basename(env_path),
                          "message": "No scoreboard created in env build_phase"})
        # Check that scoreboard is connected in connect_phase
        if ".connect(sb." not in content and ".connect(scoreboard." not in content:
            issues.append({"severity": "WARNING", "file": os.path.basename(env_path),
                          # ---
                          "message": "No scoreboard connections found in connect_phase"})
    
    # Check tb_top connections
    tb_path = os.path.join(env_dir, "tb_top.sv")
    if os.path.exists(tb_path):
        content = read_file(tb_path)
        # Check for bidir signals have pullup
        if "pullup" not in content:
            # Check if I2C interface exists — if so, warn about pullup
            ifcs_dir = os.path.join(env_dir, "interfaces")
            if os.path.exists(ifcs_dir):
                for f in os.listdir(ifcs_dir):
                    if 'i2c' in f.lower() or 'iic' in f.lower():
                        issues.append({"severity": "WARNING", "file": "tb_top.sv",
                                      "message": "I2C interface detected but no pullup found in tb_top"})
    
    # Check each interface file
    ifcs_dir = os.path.join(env_dir, "interfaces")
    if os.path.exists(ifcs_dir):
        for fname in sorted(os.listdir(ifcs_dir)):
            fpath = os.path.join(ifcs_dir, fname)
            content = read_file(fpath)
            # Check that interface has clocking blocks
            if "clocking" not in content:
                issues.append({"severity": "WARNING", "file": fname,
                              # ---
                              "message": "Interface missing clocking block"})
            # Check that interface has modports
            if "modport" not in content:
                issues.append({"severity": "WARNING", "file": fname,
                              "message": "Interface missing modport declaration"})
            # For I2C interface, check proper bidir handling
            if 'i2c' in fname.lower():
                if 'inout' not in content and 'wire' not in content:
                    issues.append({"severity": "WARNING", "file": fname,
                                  "message": "I2C interface should use wire or inout for scl/sda"})
    
    # Check env_pkg includes all files
    pkg_path = os.path.join(env_dir, "env_pkg.sv")
    if os.path.exists(pkg_path):
        pkg_content = read_file(pkg_path)
        all_sv = find_sv_files(out_dir)
        for sv_file in all_sv:
            rel = os.path.relpath(sv_file, env_dir)
            # Check condition
            if f'`include "{rel}"' not in pkg_content and f'include "{rel}"' not in pkg_content:
                # Some files might not need to be in env_pkg (like bind modules)
                pass  # Not all SV files need to be included (e.g., assertions via bind)
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
    
    # Generate contract
    contract = load_contract("spec-analyzer", out_dir) or {}
    contract.update({
        "phase": "env-builder",
        "status": "PASS" if passed else "FAIL",
        "sequencer_paths": [],
        "analysis_ports": [],
        "config_db_keys": [],
    })
    if os.path.exists(tb_path):
        content = read_file(tb_path)
        # Extract uvm_config_db set calls
        for m in re.finditer(r'uvm_config_db#\(([^)]+)\)::set\([^)]+,\s*"([^"]+)",\s*"([^"]+)",\s*(\S+)\)', content):
            contract["config_db_keys"].append({
                "type": m.group(1),
                "path": m.group(2),
                "field": m.group(3),
            })
    
    write_json(os.path.join(out_dir, ".contract_env-builder.json"), contract)
    
      # return computed value
    return {"passed": passed, "issues": issues, "contract": contract}


# ═══════════════════════════════════════════════════════════
# Phase 3: test-generator validation
# ═══════════════════════════════════════════════════════════

# ── validate_test_generator ──
def validate_test_generator(out_dir) -> Dict:
    issues = []
    env_dir = os.path.join(out_dir, "rtl", "verification", "env")
    seq_dir = os.path.join(env_dir, "sequences")
    
    # Load contract from env-builder to get register access types
    contract = load_contract("env-builder", out_dir)
    if not contract:
        contract = load_contract("spec-analyzer", out_dir)
    
    # Build register access map
    reg_access = {}
    if contract:
        for reg in contract.get("registers", []):
            reg_access[reg["name"]] = reg.get("access", "")
    
    # Check each sequence file
    if os.path.exists(seq_dir):
        # Check for variable re-declarations
        for fname in sorted(os.listdir(seq_dir)):
            if not fname.endswith(".sv"): continue
            fpath = os.path.join(seq_dir, fname)
            content = read_file(fpath)
            # ---
            
            # Check for repeated variable declarations (same type same name)
            # Pattern: "apb_rw_seq rw = ...;" multiple times in same task
            decls = re.findall(r'(\w+)\s+(\w+)\s*=\s*\1::type_id::create\("(\w+)"\)', content)
            seen_vars = {}
            for decl in decls:
                var_type, var_name, create_name = decl
                if var_name in seen_vars:
                    issues.append({"severity": "ERROR", "file": fname,
                                  "message": f"Variable '{var_name}' of type '{var_type}' re-declared (was first at {seen_vars[var_name]})"})
                seen_vars[var_name] = content[:content.find(var_name + " =")].count('\\n') + 1
    
    # Check register access violations
    for fname in sorted(os.listdir(seq_dir)):
        if not fname.endswith(".sv"): continue
        fpath = os.path.join(seq_dir, fname)
        content = read_file(fpath)
        
        # Detect register writes and reads
        for m in re.finditer(r'addr==32[\'hH]0x?([0-9a-fA-F]+)', content):
            addr_str = m.group(1)
            addr = int(addr_str, 16) if addr_str else 0
            # Check if writing to this addr
            before = content[:m.start()]
            is_write = bool(re.search(r'write\s*==\s*1', before[-200:]))
            # ---
            is_read = bool(re.search(r'write\s*==\s*0', before[-200:]))
            
            if reg_access:
                # Find register by offset
                for reg_name, access in reg_access.items():
                    reg_offset = None
                    for r in contract.get("registers", []):
                        if r["name"] == reg_name:
                            reg_offset = int(r["offset_hex"], 16) if r.get("offset_hex") else None
                            break
                    if reg_offset == addr:
                        if is_write and "wo" in access and "rw" not in access:
                            issues.append({"severity": "WARNING", "file": fname,
                                          "message": f"Register {reg_name} (0x{addr:02X}) is Write-Only but {fname} is reading it"})
                        # Check condition
                        if is_read and "ro" in access and "rw" not in access:
                            issues.append({"severity": "WARNING", "file": fname,
                                          "message": f"Register {reg_name} (0x{addr:02X}) is Read-Only but {fname} is writing to it"})
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
    
    contract = load_contract("env-builder", out_dir) or {}
    contract.update({"phase": "test-generator", "status": "PASS" if passed else "FAIL"})
    write_json(os.path.join(out_dir, ".contract_test-generator.json"), contract)
    
      # return computed value
    return {"passed": passed, "issues": issues, "contract": contract}
# ---


# ═══════════════════════════════════════════════════════════
# Phase 4: assertion-gen validation
# ═══════════════════════════════════════════════════════════

# ── validate_assertion_gen ──
def validate_assertion_gen(out_dir) -> Dict:
    issues = []
    asrt_dir = os.path.join(out_dir, "rtl", "verification", "env", "assertions")
    
    if not os.path.exists(asrt_dir):
        issues.append({"severity": "ERROR", "file": "assertions/",
                      "message": "Assertions directory not found"})
          # return computed value
        return {"passed": False, "issues": issues, "contract": {}}
    
    # Check each assertion file
    for fname in sorted(os.listdir(asrt_dir)):
        if not fname.endswith(".sv"): continue
        fpath = os.path.join(asrt_dir, fname)
        content = read_file(fpath)
        
        # Check that assertion module ports don't conflict
        # Check for property coverage (suggested but not required)
        assert_count = len(re.findall(r'\bassert\s+property\b', content))
        cover_count = len(re.findall(r'\bcover\s+property\b', content))
        # ---
        if assert_count == 0:
            issues.append({"severity": "WARNING", "file": fname,
                          "message": "No assert property found (may be placeholder only)"})
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
    contract = load_contract("test-generator", out_dir) or {}
    contract.update({"phase": "assertion-gen", "status": "PASS" if passed else "FAIL"})
    write_json(os.path.join(out_dir, ".contract_assertion-gen.json"), contract)
      # return computed value
    return {"passed": passed, "issues": issues, "contract": contract}


# ═══════════════════════════════════════════════════════════
# Phase 5: scoreboard-gen validation
# ═══════════════════════════════════════════════════════════

# ── validate_scoreboard_gen ──
def validate_scoreboard_gen(out_dir) -> Dict:
    issues = []
    sb_dir = os.path.join(out_dir, "rtl", "verification", "env", "scoreboard")
    
    if not os.path.exists(sb_dir):
        issues.append({"severity": "ERROR", "file": "scoreboard/",
                      "message": "Scoreboard directory not found"})
          # return computed value
        return {"passed": False, "issues": issues, "contract": {}}
    
    for fname in sorted(os.listdir(sb_dir)):
        # ---
        if not fname.endswith(".sv"): continue
        fpath = os.path.join(sb_dir, fname)
        content = read_file(fpath)
        
        # Check scoreboard has report_phase
        if "scoreboard" in fname.lower() or "sb" in fname.lower():
            if "report_phase" not in content:
                issues.append({"severity": "WARNING", "file": fname,
                              "message": "Scoreboard missing report_phase — no PASS/FAIL summary will be printed"})
            if "uvm_analysis_imp" not in content:
                issues.append({"severity": "ERROR", "file": fname,
                              "message": "Scoreboard missing uvm_analysis_imp declarations"})
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
    contract = load_contract("env-builder", out_dir) or {}
    contract.update({"phase": "scoreboard-gen", "status": "PASS" if passed else "FAIL"})
    write_json(os.path.join(out_dir, ".contract_scoreboard-gen.json"), contract)
      # return computed value
    return {"passed": passed, "issues": issues, "contract": contract}


# ═══════════════════════════════════════════════════════════
# Phase 6: coverage-plan validation
# ═══════════════════════════════════════════════════════════

# ── validate_coverage_plan ──
def validate_coverage_plan(spec_path, out_dir) -> Dict:
    # ---
    issues = []
    cov_dir = os.path.join(out_dir, "rtl", "verification", "env", "coverage")
    
    # Check coverage against spec coverage_goals
    spec = None
    # Check condition
    if spec_path and os.path.exists(spec_path):
        spec = read_yaml(spec_path)
    
    if spec:
        spec_goals = spec.get("verification", {}).get("coverage_goals", {})
        functional_goals = spec_goals.get("functional", [])
        cross_goals = spec_goals.get("cross", [])
    
    if not os.path.exists(cov_dir):
        issues.append({"severity": "ERROR", "file": "coverage/",
                      "message": "Coverage directory not found"})
        # Check traceability even if directory doesn't exist
        if spec:
            for goal in functional_goals:
                issues.append({"severity": "ERROR", "file": "(spec)",
                              "message": f"Functional coverage goal not covered: '{goal[:80]}...' (no coverage dir)"})
          # return computed value
        return {"passed": False, "issues": issues, "contract": {}}
    
    # Read coverage files
    cov_content = ""
    # ---
    for fname in sorted(os.listdir(cov_dir)):
        fpath = os.path.join(cov_dir, fname)
        if fname.endswith(".sv"):
            cov_content += read_file(fpath) + "\n"
    
    # Check coverage traceability against spec
    if spec:
        for goal in functional_goals:
            # Simplistic: check if key terms from the goal appear in coverage code
            goal_lower = goal.lower()
            keywords = goal_lower.replace(" coverage", "").replace(" / ", " ").replace(",", "").split()
            found_keywords = sum(1 for kw in keywords if kw in cov_content.lower())
            # Check condition
            if found_keywords < max(2, len(keywords) * 0.3):
                issues.append({"severity": "WARNING", "file": "(coverage)",
                              "message": f"Functional coverage goal may be uncovered: '{goal[:80]}...'"})
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
    contract = load_contract("assertion-gen", out_dir) or {}
    contract.update({"phase": "coverage-plan", "status": "PASS" if passed else "FAIL"})
    write_json(os.path.join(out_dir, ".contract_coverage-plan.json"), contract)
      # return computed value
    return {"passed": passed, "issues": issues, "contract": contract}


# ═══════════════════════════════════════════════════════════
# Phase 7: doc-gen validation
# ═══════════════════════════════════════════════════════════

# ── validate_doc_gen ──
def validate_doc_gen(out_dir) -> Dict:
    issues = []
    doc_path = os.path.join(out_dir, "docs", "verification-close-report.md")
    
    if not os.path.exists(doc_path):
        issues.append({"severity": "WARNING", "file": "docs/verification-close-report.md",
                      "message": "Close report not generated"})
    
    # Check that all contract files exist (full pipeline ran)
    contract_files = [f for f in os.listdir(out_dir) if f.startswith(".contract_")]
    expected_contracts = ["spec-analyzer", "env-builder", "test-generator", 
                          "assertion-gen", "scoreboard-gen", "coverage-plan"]
    for ec in expected_contracts:
        if f".contract_{ec}.json" not in contract_files:
            issues.append({"severity": "WARNING", "file": f".contract_{ec}.json",
                          "message": f"Phase '{ec}' contract missing — that phase may not have run"})
    
    passed = len([i for i in issues if i["severity"] == "ERROR"]) == 0
      # return computed value
    return {"passed": passed, "issues": issues}


# ── validate_sw_header ──
def validate_sw_header(sw_dir, module_name) -> Dict:
    """Validate C header generation output."""
    issues = []
    header_path = os.path.join(sw_dir, f"{module_name}.h")
    if not os.path.exists(header_path):
        issues.append({"severity": "ERROR", "file": header_path,
                      "message": "Generated C header not found"})
          # return computed value
        return {"passed": False, "issues": issues}