---
name: scoreboard-gen
description: >
  Generate UVM scoreboard and checker components. Creates data comparison,
  protocol checking, and end-to-end data integrity verification.
---

# scoreboard-gen

**Verifier Agent**: scoreboard and checker generation.

Generates UVM scoreboard, data checkers, and protocol monitors for end-to-end verification.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `verification-plan.md`, `interface-list.yml` | spec-analyzer | yes |
| `register-map.yml` | spec-analyzer | optional |

## Outputs (into `rtl/verification/env/scoreboard/`)

| File | Description |
|------|-------------|
| `sb.sv` | Main scoreboard with TLM analysis ports |
| `sb_compare.sv` | Data comparison logic |
| `sb_predictor.sv` | Prediction logic (expected data generation) |

## Scoreboard Architecture

```
[Monitor A] ──analysis_port──▶ Scoreboard ──analysis_port──▶ [Monitor B]
                                   │
                            ┌──────┴──────┐
                            │   Compare    │
                            └──────┬──────┘
                                   │
                               PASS/FAIL
```

### Main Scoreboard Template
```systemverilog
class sb extends uvm_scoreboard;
  `<uvm_component_utils(sb)

  uvm_analysis_imp_mon_a  #(txn, sb) mon_a_export;
  uvm_analysis_imp_mon_b  #(txn, sb) mon_b_export;

  // Prediction queue
  txn expected_q[$];

  function void build_phase(uvm_phase phase);
    mon_a_export = new("mon_a_export", this);
    mon_b_export = new("mon_b_export", this);
  endfunction

  // Write from input monitor (prediction)
  function void write_mon_a(txn t);
    expected_q.push_back(t);
  endfunction

  // Write from output monitor (comparison)
  function void write_mon_b(txn t);
    txn expected = expected_q.pop_front();
    if (!t.compare(expected)) begin
      `<uvm_error("SB_MISMATCH", $sformatf(
        "Expected: %0s\nActual: %0s", expected.sprint(), t.sprint()))
    end
  endfunction
endclass
```
