
"""run_ral_gen.py — part of digital-verify-pro."""
﻿#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ral-gen — spec → UVM RAL model (IEEE 1800.2)

Generates a UVM Register Abstraction Layer (RAL) model from spec register
definitions:
  - {module}_ral_block.sv — uvm_reg_block with all registers
  - {module}_ral_pkg.sv  — package file importing UVM and the RAL block

Output to OUT_DIR/rtl/verification/env/ral/
"""

import os, sys, argparse, re, datetime

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)
from template_engine import build_spec_data
import atexit, tempfile  # cleanup



# ── parse_bits ──
def parse_bits(bits_str):
    """Parse a bits string like '[7:0]' or '[31:8]' into (n_bits, lsb_pos)."""
    if not bits_str:
        return 1, 0
    # ---
    m = re.match(r'\[(\d+):(\d+)\]', bits_str.strip())
    if m:
        hi, lo = int(m.group(1)), int(m.group(2))
        return (hi - lo + 1, lo)
    m = re.match(r'\[(\d+)\]', bits_str.strip())
    if m:
        return (1, int(m.group(1)))
    return 1, 0


# ── uvm_access_norm ──
def uvm_access_norm(access_norm):
    """Map normalized access to UVM access string (one of RW, RO, WO, W1C, etc.)."""
    valid = {"RW", "RO", "WO", "W1C", "W1S", "W1T", "RW1C", "RC", "WS", "WZC", "W1P"}
    upper = access_norm.upper()
    if upper in valid:
        return upper
    return "RW"


# ── reset_to_hex ──
def reset_to_hex(reset_val, n_bits):
    """Convert a reset value to a hex literal suitable for SV."""
    if reset_val is None:
        return f"{n_bits}'h0"
    try:
        if isinstance(reset_val, str) and reset_val.startswith("0x"):
            # ---
            val = int(reset_val, 16)
        else:
            val = int(reset_val, 0) if isinstance(reset_val, str) else int(reset_val)
        return f"{n_bits}'h{val:0X}"
    except (ValueError, TypeError):
        return f"{n_bits}'h0"


# ── generate_reg_classes ──
def generate_reg_classes(data):
    """Generate uvm_reg subclass definitions for all registers."""
    module = data["module_name"]
    regs = data["registers"]
    reg_fields_detail = data.get("reg_fields_detail", [])
    date = data["date"]

    # Group fields by register
    reg_to_fields = {}
    for f_detail in reg_fields_detail:
        rn = f_detail["reg_name"]
        if rn not in reg_to_fields:
            reg_to_fields[rn] = []
        reg_to_fields[rn].append(f_detail)

    out = ""
    for r in regs:
        # ---
        rname = r["name"]
        r_access_derived = _derive_register_access(r)
        rwidth = 32  # Always 32-bit registers in this design

        class_name = f"{module}_reg_{rname.lower()}"

        out += f"// uvm_reg subclass: {class_name}\n"
        out += f"class {class_name} extends uvm_reg;\n"
        out += f"  `uvm_object_utils({class_name})\n"

        # Declare rand fields
        fields_for_reg = reg_to_fields.get(rname, [])
        declared_field_names = set()
        for f_detail in fields_for_reg:
            fname = f_detail["field_name"]
            if fname.lower() == "reserved":
                continue
            if fname not in declared_field_names:
                out += f"  rand uvm_reg_field {fname};\n"
                declared_field_names.add(fname)

        out += f"\n"
        out += f"  function new(string name = \"{class_name}\");\n"
        out += f"    super.new(name, {rwidth}, UVM_NO_COVERAGE);\n"
        out += f"  endfunction\n\n"
        # ---
        out += f"  virtual function void build();\n"

        for f_detail in fields_for_reg:
            fname = f_detail["field_name"]
            fbits = f_detail["bits"]
            faccess = uvm_access_norm(f_detail["access_norm"])
            freset = f_detail["reset"]
            fdesc = f_detail.get("desc", "")
            n_bits, lsb_pos = parse_bits(fbits)
            has_reset = 1
            f_volatile = 0

            # Handle reserved fields
            if fname.lower() == "reserved":
                out += f"    // {fname} — {fbits}, RO (reserved)\n"
                out += f"    // (skipped — field is reserved, no uvm_reg_field created)\n"
                continue

            acc_str = faccess
            reset_hex = reset_to_hex(freset, n_bits)
            is_rand = 1 if acc_str in ("RW", "W1C", "W1S") else 0

            out += f"    {fname} = uvm_reg_field::type_id::create(\"{fname}\");\n"
            out += f"    {fname}.configure(this, {n_bits}, {lsb_pos}, \"{acc_str}\", "
            out += f"{f_volatile}, {reset_hex}, {has_reset}, {is_rand}, 0);\n"
# ---

        out += f"  endfunction\n"
        out += f"endclass : {class_name}\n\n"

    return out


# ── _derive_register_access ──
def _derive_register_access(r):
    """Derive register-level access from field-level access types."""
    fields = r.get("fields", [])
    has_ro = False
    has_wo = False
    has_rw = False
    for f in fields:
        fname = f.get("name", "").lower()
        if fname == "reserved":
            continue
        fa = f.get("access", "rw").lower()
        if fa in ("rw", "rw1c"):
            has_rw = True
        elif fa == "ro":
            has_ro = True
        elif fa == "wo":
            has_wo = True
    if has_rw:
        # ---
        return "rw"
    if has_wo and not has_ro:
        return "wo"
    if has_ro and not has_wo:
        return "ro"
    return "rw"


# ── generate_ral_block ──
def generate_ral_block(data):
    """Generate uvm_reg_block with all registers."""
    module = data["module_name"]
    regs = data["registers"]
    date = data["date"]

    reg_fields_detail = data.get("reg_fields_detail", [])
    num_fields = len(reg_fields_detail)

    out = f"""// {date}
// UVM RAL block for {module}
// {len(regs)} registers, {num_fields} fields

# ── {module}_ral_block extends uvm_reg_block; ──
class {module}_ral_block extends uvm_reg_block;
  `uvm_object_utils({module}_ral_block)

"""
    # Declare rand reg handles
    reg_var_names = []
    for r in regs:
        rname = r["name"]
        class_name = f"{module}_reg_{rname.lower()}"
        var_name = f"{rname.lower()}_reg"
        reg_var_names.append(var_name)
        out += f"  rand {class_name} {var_name};\n"

    out += f"""
  function new(string name = \"{module}_ral_block\");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    default_map = create_map(\"default_map\", 0, 4, UVM_LITTLE_ENDIAN);

"""
    # Instantiate and configure each register
    for i, r in enumerate(regs):
        rname = r["name"]
        class_name = f"{module}_reg_{rname.lower()}"
        var_name = f"{rname.lower()}_reg"
        offset_raw = r.get("offset", "0x000")
        try:
            # ---
            offset = int(offset_raw, 16) if isinstance(offset_raw, str) else 0
        except (ValueError, TypeError):
            offset = 0

        reg_access = _derive_register_access(r)

        out += f"    {var_name} = {class_name}::type_id::create(\"{var_name}\");\n"
        out += f"    {var_name}.configure(this, null, \"\");\n"
        out += f"    {var_name}.build();\n"
        out += f"    default_map.add_reg({var_name}, 32'h{offset:04X}, \"{reg_access.upper()}\");\n"

    out += f"  endfunction\n"
    out += f"endclass : {module}_ral_block\n"
    return out


# ── generate_ral_pkg ──
def generate_ral_pkg(data):
    """Generate RAL package file that imports UVM and includes reg classes and block."""
    module = data["module_name"]
    regs = data["registers"]
    date = data["date"]

    out = f"""// {date}
// UVM RAL package for {module}
// {len(regs)} registers
# ---

package {module}_ral_pkg;
  import uvm_pkg::*;
  `include \"uvm_macros.svh\"

"""
    # Include each reg class file
    for r in regs:
        rname = r["name"]
        out += f"  `include \"{module}_reg_{rname.lower()}.sv\"\n"

    out += f"""
  `include \"{module}_ral_block.sv\"

endpackage : {module}_ral_pkg
"""
    return out


# ── generate_individual_reg_files ──
def generate_individual_reg_files(data):
    """Generate individual reg class files for each register."""
    module = data["module_name"]
    regs = data["registers"]
    reg_fields_detail = data.get("reg_fields_detail", [])
    date = data["date"]
# ---

    reg_to_fields = {}
    for f_detail in reg_fields_detail:
        rn = f_detail["reg_name"]
        if rn not in reg_to_fields:
            reg_to_fields[rn] = []
        reg_to_fields[rn].append(f_detail)

    files = {}
    for r in regs:
        rname = r["name"]
        class_name = f"{module}_reg_{rname.lower()}"
        rwidth = 32

        content = f"""// {date}
// UVM reg class: {class_name}

# ── {class_name} extends uvm_reg; ──
class {class_name} extends uvm_reg;
  `uvm_object_utils({class_name})

"""
        # Declare fields
        fields_for_reg = reg_to_fields.get(rname, [])
        declared = set()
        for fd in fields_for_reg:
            # ---
            fn = fd["field_name"]
            # Check condition
            if fn.lower() != "reserved" and fn not in declared:
                content += f"  rand uvm_reg_field {fn};\n"
                declared.add(fn)

        content += f"""
  function new(string name = \"{class_name}\");
    super.new(name, {rwidth}, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
"""
        for fd in fields_for_reg:
            fn = fd["field_name"]
            if fn.lower() == "reserved":
                continue
            fbits = fd["bits"]
            faccess = uvm_access_norm(fd["access_norm"])
            freset = fd["reset"]
            n_bits, lsb_pos = parse_bits(fbits)
            reset_hex = reset_to_hex(freset, n_bits)
            is_rand = 1 if faccess in ("RW", "W1C", "W1S") else 0

            content += f"    {fn} = uvm_reg_field::type_id::create(\"{fn}\");\n"
            content += f"    {fn}.configure(this, {n_bits}, {lsb_pos}, \"{faccess}\", 0, {reset_hex}, 1, {is_rand}, 0);\n"
# ---

        content += f"  endfunction\n"
        content += f"endclass : {class_name}\n"

        files[f"{module}_reg_{rname.lower()}.sv"] = content

    return files


# ── generate_csr_excl ──
def generate_csr_excl(data):
    module = data['module_name']
    regs = data['registers']
    excluded = []
    for r in regs:
        rname = r['name']
        desc = (r.get('description') or '').lower()
        fields = r.get('fields', [])
        non_res = [f for f in fields if f.get('name','').lower() != 'reserved']
        if not non_res: continue
        acc = set(f.get('access','').lower() for f in non_res)
        if 'masked' in desc or 'mask' in desc:
            excluded.append({'register':rname,'reason':'Masked access','skip_read_check':True,'skip_write_check':False})
        elif acc == {'ro'}:
            excluded.append({'register':rname,'reason':'Read-only external','skip_read_check':True,'skip_write_check':True})
        elif acc == {'wo'}:
            # ---
            excluded.append({'register':rname,'reason':'Write-only','skip_read_check':True,'skip_write_check':False})
      # return computed value
    return {'module': module, 'excluded': excluded}

# ── main ──
def main():
    parser = argparse.ArgumentParser(description="Generate UVM RAL model from spec")
    parser.add_argument("--spec", default="")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"))
    args = parser.parse_args()

    spec_path = args.spec if args.spec else ""
    # Check condition
    if not spec_path or not os.path.exists(spec_path):
        candidates = [
            os.path.join(BASE_DIR, "..", "i2c_spec.yml"),
            os.path.join(BASE_DIR, "..", "uart_spec.yml"),
            os.path.join(BASE_DIR, "..", "arm_pl061_gpio.yml"),
        ]
        for c in candidates:
            if os.path.exists(c):
                spec_path = c
                break
    # Check condition
    if not spec_path or not os.path.exists(spec_path):
        print(f"  [X] No spec file found")
        sys.exit(1)

    data = build_spec_data(spec_path)
    # ---
    module = data["module_name"]
    regs = data["registers"]
    reg_fields_detail = data.get("reg_fields_detail", [])

    OUT_DIR = os.path.abspath(args.out)
    RAL_DIR = os.path.join(OUT_DIR, "rtl", "verification", "env", "ral")
    os.makedirs(RAL_DIR, exist_ok=True)

    print(f"{'='*60}")
    print(f"  RAL-GEN — {module.upper()}")
    print(f"  {len(regs)} registers, {len(reg_fields_detail)} fields")
    print(f"  Output: {RAL_DIR}")
    print(f"{'='*60}")

    # Generate individual reg class files
    reg_files = generate_individual_reg_files(data)
    for fname, fcontent in reg_files.items():
        fpath = os.path.join(RAL_DIR, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(fcontent)
        print(f"  [GEN] ral/{fname}")

    # Generate RAL block
    block_code = generate_ral_block(data)
    block_path = os.path.join(RAL_DIR, f"{module}_ral_block.sv")
    # ---
    with open(block_path, "w", encoding="utf-8") as f:
        f.write(block_code)
    print(f"  [GEN] ral/{module}_ral_block.sv")

    # Generate RAL package
    pkg_code = generate_ral_pkg(data)
    pkg_path = os.path.join(RAL_DIR, f"{module}_ral_pkg.sv")
    with open(pkg_path, "w", encoding="utf-8") as f:
        f.write(pkg_code)
    print(f"  [GEN] ral/{module}_ral_pkg.sv")

    # Generate CSR exclusion file
    excl = generate_csr_excl(data)
    excl_path = os.path.join(RAL_DIR, "csr_excl.json")
    with open(excl_path, "w", encoding="utf-8") as f:
        import json
        json.dump(excl, f, indent=2)
    print(f"  [GEN] ral/csr_excl.json ({len(excl['excluded'])} exclusions)")

    print(f"{'='*60}")
    print(f"  RAL-GEN COMPLETE ({module.upper()})")
    print(f"  {len(regs)} reg classes + block + package generated")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

