#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
csr-test-gen — CSR verification test generation (iverilog-compatible, no tasks).

Inspired by OpenTitan:
1. hw_reset_test — verify all registers match spec reset values
2. rw_access_test — write/read all RW registers

No tasks or macros — inline APB operations (iverilog 11.0 workaround).
"""

import os, sys, argparse, glob, subprocess

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)
from template_engine import build_spec_data

def gen_apb_write(addr_hex, val_hex, clk="clk"):
    """Generate inline APB write sequence."""
    return f"""    psel=1;penable=0;pwrite=1;paddr=12'h{addr_hex};pwdata=32'h{val_hex};
    @(posedge {clk}); penable=1;
    @(posedge {clk}); while(!pready) @(posedge {clk});
    psel=0;penable=0; @(posedge {clk});"""

def gen_apb_read(addr_hex, exp_hex, clk="clk"):
    """Generate inline APB read + compare."""
    return f"""    psel=1;penable=0;pwrite=0;paddr=12'h{addr_hex};
    @(posedge {clk}); penable=1;
    @(posedge {clk}); while(!pready) @(posedge {clk});
    read_data=prdata;
    if(pslverr) $display("  WARN: PSLVERR on read %0h", 12'h{addr_hex});
    else if(read_data!==32'h{exp_hex}) begin
      $display("  FAIL: %0h = %0h (exp %0h)", 12'h{addr_hex}, read_data, 32'h{exp_hex}); errors=errors+1;
    end else $display("  PASS: %0h = %0h", 12'h{addr_hex}, read_data);
    psel=0;penable=0; @(posedge {clk});"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"))
    args = ap.parse_args()

    SPEC_PATH = args.spec
    if not SPEC_PATH:
        for c in ["i2c_spec.yml", "pcie_ep_spec.yml", "arm_pl061_gpio.yml"]:
            f = os.path.join(BASE_DIR, "..", c)
            if os.path.exists(f):
                SPEC_PATH = f; break
    if not SPEC_PATH or not os.path.exists(SPEC_PATH):
        print("  [X] No spec"); sys.exit(1)

    data = build_spec_data(SPEC_PATH)
    module, clk, rst = data["module_name"], data["clk_name"], data["rst_name"]
    OUT_DIR = os.path.abspath(args.out)
    CSR_DIR = os.path.join(OUT_DIR, "csr_test")
    os.makedirs(CSR_DIR, exist_ok=True)

    reg_addr_map = data["reg_addr_map"]
    date = data["date"]
    top = f"csr_test_{module}"

    # Classify
    rw_regs, ro_regs = [], []
    for r in data["registers"]:
        accs = set(f.get("access","rw") for f in r.get("fields",[]))
        if accs == {"ro"}: ro_regs.append(r)
        else: rw_regs.append(r)

    # ── Reset test ──
    reset_body = ""
    for r in data["registers"]:
        off = reg_addr_map.get(r["name"], "0x0000")
        rv_raw = r.get("reset", "0")
        try:
            rv = int(rv_raw, 16) if isinstance(rv_raw,str) and rv_raw.startswith("0x") else int(rv_raw)
        except: rv = 0
        reset_body += gen_apb_read(off[2:], f"{rv:08X}", clk) + "\n"

    tb = f"""// {date} CSR Reset Test - {module}
`timescale 1ns/1ps
module {top};
  reg {clk}; reg {rst}; reg psel,penable,pwrite;
  reg [11:0] paddr; reg [31:0] pwdata;
  wire [31:0] prdata; wire pready, pslverr;
  reg [31:0] read_data; int errors;
  wire [7:0] gpio; wire intr;
  {module} dut (.*);
  initial begin {clk}=0; forever #10 {clk}=~{clk}; end
  initial begin {rst}=0; #100; {rst}=1; end
  initial begin errors=0; $display("=== {module} CSR Reset ==="); #150;
{reset_body}#100;
  if(errors==0) $display("*** ALL RESET OK ***");
  else $display("*** %0d MISMATCH ***", errors);
  $finish; end
endmodule
"""
    p = os.path.join(CSR_DIR, f"{top}_reset.sv")
    with open(p, "w") as f: f.write(tb)
    print(f"  [GEN] csr_test/{top}_reset.sv")

    # ── RW test ──
    rw_body = ""
    for r in rw_regs:
        off = reg_addr_map.get(r["name"], "0x0000")
        rv_raw = r.get("reset", "0")
        try:
            rv = int(rv_raw, 16) if isinstance(rv_raw,str) and rv_raw.startswith("0x") else int(rv_raw)
        except: rv = 0
        tv = (rv ^ 0xFF) & 0xFF
        rw_body += gen_apb_write(off[2:], f"{tv:08X}", clk) + "\n"
        rw_body += gen_apb_read(off[2:], f"{tv:08X}", clk) + "\n"

    if rw_regs:
        tb2 = f"""// {date} CSR RW Test - {module}
`timescale 1ns/1ps
module {top}_rw;
  reg {clk}; reg {rst}; reg psel,penable,pwrite;
  reg [11:0] paddr; reg [31:0] pwdata;
  wire [31:0] prdata; wire pready, pslverr;
  reg [31:0] read_data; int errors;
  wire [7:0] gpio; wire intr;
  {module} dut (.*);
  initial begin {clk}=0; forever #10 {clk}=~{clk}; end
  initial begin {rst}=0; #100; {rst}=1; end
  initial begin errors=0; $display("=== {module} CSR RW ==="); #150;
{rw_body}#100;
  if(errors==0) $display("*** ALL RW PASS ***");
  else $display("*** %0d RW FAIL ***", errors);
  $finish; end
endmodule
"""
        p2 = os.path.join(CSR_DIR, f"{top}_rw.sv")
        with open(p2, "w") as f: f.write(tb2)
        print(f"  [GEN] csr_test/{top}_rw.sv")

    # ── Compile & run reset test ──
    rtl_files = sorted(glob.glob(os.path.join(OUT_DIR, "rtl", "rtl", "*.sv")))
    if rtl_files:
        sim_work = os.path.join(OUT_DIR, "sim_work")
        os.makedirs(sim_work, exist_ok=True)
        for tb_name, tb_file in [("reset", f"{top}_reset.sv")]:
            vvp = os.path.join(sim_work, f"{module}_csr_{tb_name}.vvp")
            r = subprocess.run(["iverilog","-g2012","-s",f"{top}", "-o", vvp] + rtl_files + [os.path.join(CSR_DIR, tb_file)],
                              capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                print(f"  [OK] csr_{tb_name} compiled")
                r2 = subprocess.run(["vvp", vvp], capture_output=True, text=True, timeout=60)
                print("  " + r2.stdout.replace("\n","\n  ").strip())
            else:
                print(f"  [X] csr_{tb_name} FAILED")
                for l in r.stderr.split("\n"):
                    if "error" in l.lower(): print(f"      {l}")

    print(f"{'='*60}\n  CSR-TEST-GEN COMPLETE\n{'='*60}")

if __name__ == "__main__":
    main()
