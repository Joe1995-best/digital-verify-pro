---
name: assertion-gen
description: >
  Generate SystemVerilog Assertions (SVA) from specification. Covers interface
  protocols, internal invariants, register access rules, and timing requirements.
---

# assertion-gen

**Verifier Agent**: SVA assertion generation.

Generates SystemVerilog Assertions for interface protocols, internal design invariants, register access timing, and reset behavior.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `interface-list.yml` | spec-analyzer | yes |
| `spec.yml` | Working directory | yes |
| Protocol timing diagrams | Wiki | optional |

## Outputs (into `rtl/verification/env/assertions/`)

| File | Description |
|------|-------------|
| `<iface>_assert.sv` | Interface protocol assertions |
| `register_assert.sv` | Register access timing assertions |
| `reset_assert.sv` | Reset behavior assertions |
| `clk_assert.sv` | Clock-domain assertions |

## Common Protocol Assertion Patterns

### APB Protocol
```systemverilog
// PSEL must be high for exactly one PENABLE assertion
property psel_to_penable;
  @(posedge clk) $rose(psel) |=> ##[0:1] $rose(penable);
endproperty

// PREADY must be asserted within N cycles of PENABLE
property pready_within;
  @(posedge clk) $rose(penable) |=> ##[1:MAX_WAIT] pready;
endproperty

// No X/Z on valid interface signals
property no_x_on_psel;
  @(posedge clk) disable iff (!rstn)
    !$isunknown(psel);
endproperty
```

### AXI Protocol
```systemverilog
// AW and W channels must have matching AWID/WID
property aw_w_id_match;
  @(posedge clk) disable iff (!rstn)
    $rose(awvalid) |-> ##[0:$] wvalid && (awid == wid);
endproperty

// Burst length must be 1-16 for INCR bursts
property burst_len_legal;
  @(posedge clk) disable iff (!rstn)
    awvalid && awburst == INCR |-> awlen inside {[0:15]};
endproperty

// Last transfer must have WLAST asserted
property wlast_at_end;
  @(posedge clk) disable iff (!rstn)
    wvalid && wready && wlast |=> !wlast until ##1 awvalid || wvalid;
endproperty
```

### Register Access Assertions
```systemverilog
// Reserved fields must always read as 0
property reserved_read_zero;
  @(posedge clk) disable iff (!rstn)
    reg_read_addr == RESERVED_OFFSET |-> reg_rdata == 0;
endproperty

// W1C fields: writing 1 clears, writing 0 has no effect
property w1c_behavior;
  @(posedge clk) disable iff (!rstn)
    reg_write && reg_wdata[W1C_BIT] == 1 |=> reg_rdata[W1C_BIT] == 0;
endproperty
```

### Reset Assertions
```systemverilog
// All outputs must be reset within N cycles
property reset_outputs;
  @(posedge clk) $fell(rstn) |-> ##[1:MAX_RESET_CYCLES]
    (txd === 0) && (intr === 0);
endproperty
```

## Effort Interaction

| Effort | Assertion depth |
|--------|-----------------|
| lite | Basic protocol checks only |
| standard | Protocol + register access + reset |
| intensive | Full protocol + register + X/Z + timing |
| exhaustive | All + property coverage + SVA formal-ready |
