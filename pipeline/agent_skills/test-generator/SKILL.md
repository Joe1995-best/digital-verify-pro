---
name: test-generator
description: >
  Generate UVM test sequences for verification scenarios. Produces compilable
  SystemVerilog sequence classes from test scenario definitions.
---

# test-generator

**Verifier Agent**: test sequence generation.

Generates UVM sequence classes for each test scenario defined in the verification plan.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `test-scenarios.yml` | spec-analyzer | yes |
| `interface-list.yml` | spec-analyzer | yes |
| Reuse existing sequences | env-builder | yes |

## Outputs (into `rtl/verification/env/sequences/`)

| File | Description |
|------|-------------|
| `<test>_seq.sv` | Sequence class per test scenario |
| `stress_seq.sv` | Random back-to-back traffic |
| `error_seq.sv` | Protocol error injection sequences |
| `reg_access_seq.sv` | Register read/write sequences (if applicable) |
| `interrupt_seq.sv` | Interrupt test sequences (if applicable) |

## Sequence Generation Patterns

### Basic Functional Test
```systemverilog
class <test>_seq extends base_seq;
  `<uvm_object_utils(<test>_seq)

  function new(string name = "<test>_seq");
    super.new(name);
  endfunction

  virtual task body();
    `<uvm_info(get_type_name(), "Starting <test> sequence", UVM_LOW)
    
    // Generated sequence body from spec
    // Example: APB write then read back
    apb_write(32'h00, 32'hA5);  // write to ctrl_reg
    apb_read(32'h00);            // read back ctrl_reg
    
    `<uvm_info(get_type_name(), "Finished <test> sequence", UVM_LOW)
  endtask
endclass
```

### Protocol-Specific Tests
For each protocol type, the agent generates appropriate sequences:
- **APB**: single transfers, back-to-back, wait states, error responses
- **AXI**: burst of each type, unaligned addresses, out-of-order, split/retry
- **I2C**: start/stop/restart, address + data, clock stretching, NACK
- **SPI**: CPOL/CPHA variations, different data widths, CS deassert

### Random Stress Test
```systemverilog
class stress_seq extends base_seq;
  `<uvm_object_utils(stress_seq)
  rand int num_transactions;
  constraint num_tx_c { num_transactions inside {[100:1000]}; }

  virtual task body();
    repeat (num_transactions) begin
      // Randomize transaction fields
      // Send via driver
      // Wait random delay
    end
  endtask
endclass
```
