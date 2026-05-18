---
name: coverage-plan
description: >
  Generate functional coverage groups from verification plan. Creates covergroup
  definitions for interfaces, registers, internal states, and cross coverage.
---

# coverage-plan

**Verification Architect Phase 1 (post-spec)**: coverage definition.

Generates SystemVerilog covergroups for functional coverage closure.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `verification-plan.md` | spec-analyzer | yes |
| `test-scenarios.yml` | spec-analyzer | yes |

## Outputs (into `rtl/verification/env/coverage/`)

| File | Description |
|------|-------------|
| `cov_groups.sv` | All functional covergroups |
| `cov_iface.sv` | Interface-specific coverage |
| `cov_reg.sv` | Register access coverage |
| `cov_cross.sv` | Cross coverage bins |

## Coverage Types Generated

### 1. Interface Coverage
```systemverilog
covergroup apb_cg @(posedge clk);
  // Transaction type: read vs write
  tran_type: coverpoint pwrite {
    bins write = {1};
    bins read  = {0};
  }

  // Address range coverage
  addr_range: coverpoint paddr[7:0] {
    bins ctrl   = {8'h00};
    bins status = {8'h04};
    bins data   = {8'h08};
    bins others = default;
  }

  // Wait states
  wait_states: coverpoint wait_cycles {
    bins zero = {0};
    bins one  = {1};
    bins few  = {[2:5]};
    bins many = {[6:$]};
  }

  // Cross coverage
  tran_addr: cross tran_type, addr_range;
endgroup
```

### 2. Register Coverage
```systemverilog
covergroup reg_cg @(posedge clk);
  // All registers accessed at least once
  reg_addr: coverpoint reg_addr {
    bins all_regs[] = {[0:NUM_REGS-1]};
  }

  // Access type per register
  reg_access: coverpoint {reg_addr, reg_write} {
    bins reg_reads[NUM_REGS] = {[0:NUM_REGS-1], 0};
    bins reg_writes[NUM_REGS] = {[0:NUM_REGS-1], 1};
  }

  // Field-level coverage for specific registers
  ctrl_tx_en: coverpoint reg_wdata[0] iff (reg_addr == CTRL_ADDR);
  ctrl_rx_en: coverpoint reg_wdata[1] iff (reg_addr == CTRL_ADDR);
endgroup
```

### 3. Internal State Coverage
```systemverilog
covergroup fsm_cg @(posedge clk);
  state: coverpoint fsm_state {
    bins idle    = {IDLE};
    bins active  = {ACTIVE};
    bins wait_s  = {WAIT};
    bins error   = {ERROR};
    illegal_bins illegal_states = default;
  }

  // State transitions
  state_trans: coverpoint fsm_state {
    bins idle_to_active = (IDLE => ACTIVE);
    bins active_to_wait = (ACTIVE => WAIT);
    bins wait_to_idle   = (WAIT => IDLE);
    bins wait_to_active = (WAIT => ACTIVE);
    bins any_to_error   = (IDLE, ACTIVE, WAIT => ERROR);
  }
endgroup
```

### 4. Cross Coverage (Protocol + Data)
```systemverilog
covergroup protocol_cross_cg @(posedge clk);
  // AXI-specific cross coverage
  burst_type: coverpoint awburst;
  burst_len:  coverpoint awlen {
    bins short = {[0:3]};
    bins med   = {[4:7]};
    bins long  = {[8:15]};
  }
  burst_cross: cross burst_type, burst_len;
endgroup
```

## Effort Interaction

| Effort | Coverage detail |
|--------|-----------------|
| lite | Interface coverage only |
| standard | Interface + register coverage |
| intensive | Interface + register + FSM coverage |
| exhaustive | All + cross coverage + toggle + cover directives on RTL |
