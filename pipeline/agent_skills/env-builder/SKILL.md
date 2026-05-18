---
name: env-builder
description: >
  Generate UVM environment skeleton from verification plan. Builds tb_top,
  interface wrappers, UVM agent/monitor/sequencer, and testbench harness.
---

# env-builder

**Verification Architect Phase 2**: UVM environment generation.

Takes the output from spec-analyzer and generates a complete, compilable UVM verification environment skeleton.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `verification-plan.md` | spec-analyzer | yes |
| `interface-list.yml` | spec-analyzer | yes |
| `register-map.yml` | spec-analyzer | optional |

## Outputs (into `rtl/verification/env/`)

| File | Description |
|------|-------------|
| `tb_top.sv` | Testbench top with clock/reset generation, DUT instantiation, interface connections |
| `interfaces/<iface>_if.sv` | SystemVerilog interface per protocol, with clocking blocks and modports |
| `agents/<iface>_agent.sv` | UVM agent: sequencer + driver + monitor |
| `agents/<iface>_driver.sv` | Protocol driver (sequences → pin wiggles) |
| `agents/<iface>_monitor.sv` | Protocol monitor (pin wiggles → transactions) |
| `agents/<iface>_sequencer.sv` | UVM sequencer parameterized by transaction type |
| `env_pkg.sv` | Package file with all includes |
| `env.sv` | Top-level UVM environment connecting all agents |
| `sequences/base_seq.sv` | Base sequence with common methods |
| `sequences/reset_seq.sv` | Reset sequence |

## Generated Environment Architecture

```
tb_top
  ├── clock_if     → clock generation
  ├── reset_if     → reset driver
  ├── <iface>_if   → DUT interface
  ├── DUT instance
  └── uvm_root
       └── env (env.sv)
            ├── clock_agent
            │    ├── sequencer
            │    ├── driver
            │    └── monitor
            ├── reset_agent
            │    ├── sequencer
            │    ├── driver
            │    └── monitor
            ├── <iface>_agent
            │    ├── sequencer
            │    ├── driver
            │    └── monitor
            ├── scoreboard (placeholder)
            ├── coverage (placeholder)
            └── regmodel (placeholder, if registers exist)
```

### Interface Template Pattern

```systemverilog
interface <iface>_if (
  input logic clk,
  input logic rstn
);
  // Signal declarations from interface-list.yml
  logic psel;
  logic penable;
  logic pwrite;
  logic [31:0] paddr;
  logic [31:0] pwdata;
  logic [31:0] prdata;
  logic pready;
  logic pslverr;

  // Clocking block for driver
  clocking drv_cb @(posedge clk);
    output psel, penable, pwrite, paddr, pwdata;
    input prdata, pready, pslverr;
  endclocking

  // Clocking block for monitor
  clocking mon_cb @(posedge clk);
    input psel, penable, pwrite, paddr, pwdata, prdata, pready, pslverr;
  endclocking

  modport driver  (clocking drv_cb);
  modport monitor (clocking mon_cb);
endinterface
```

### UVM Agent Pattern

```systemverilog
class <iface>_agent extends uvm_agent;
  `<uvm_component_utils(<iface>_agent)

  <iface>_sequencer seqr;
  <iface>_driver    drv;
  <iface>_monitor  mon;

  function void build_phase(uvm_phase phase);
    seqr = <iface>_sequencer::type_id::create("seqr", this);
    drv  = <iface>_driver::type_id::create("drv", this);
    mon  = <iface>_monitor::type_id::create("mon", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    drv.seq_item_port.connect(seqr.seq_item_export);
  endfunction
endclass
```
