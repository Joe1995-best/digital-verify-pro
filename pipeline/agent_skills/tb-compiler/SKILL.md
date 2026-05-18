---
name: tb-compiler
description: >
  Compile verification environment with EDA tool. Handles UVM package compilation,
  DUT RTL compilation, testbench compilation, and generates compile script.
---

# tb-compiler

**Runner Agent Phase 1**: compile testbench + DUT.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Generated env | pipeline | yes |
| DUT RTL source | User | yes |

## Supported EDA Tools

| Tool | Script | Notes |
|------|--------|-------|
| VCS | `Makefile` + `.synopsys_dc.setup` | Full compile with UVM 1.2/1800.2 |
| Xcelium | `Makefile` + `cds.lib` | IES/XRUN flow |
| Questa | `Makefile` + `modelsim.ini` | vsim flow |
| Verilator | `CMakeLists.txt` | Open-source, Verilog only |
| Icarus | `Makefile` | Open-source, Verilog only |

## Compilation Flow

```tcl
# compile.tcl (generated for VCS)
set UVM_HOME $env(UVM_HOME)
set TOP tb_top

# Compile UVM
vlogan -work work -l comp_uvm.log \
  -ntb_opts uvm-1.2 \
  $UVM_HOME/src/uvm_pkg.sv

# Compile DUT RTL
vlogan -work work -l comp_dut.log \
  +define+SIMULATION \
  ../rtl/*.sv

# Compile verification environment
vlogan -work work -l comp_env.log \
  -ntb_opts uvm-1.2 \
  -f env_files.f

# Elaborate
vcs tb_top -l comp_elab.log \
  -debug_access+all \
  -lca -kdb

# Output: simv
```

## Effort Interaction

| Effort | Compile flags |
|--------|--------------|
| lite | Minimal flags, no debug |
| standard | Basic debug (waveform dump) |
| intensive | Full debug + coverage collection |
| exhaustive | Full debug + coverage + formal checks |
