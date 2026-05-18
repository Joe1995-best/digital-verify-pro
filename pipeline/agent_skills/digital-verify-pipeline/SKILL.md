---
name: digital-verify-pipeline
description: >
  MANDATORY — MUST load when the user mentions: digital verification, UVM,
  SystemVerilog, testbench, simulation, RTL verification, functional verification,
  coverage, register model, C header, CSR test, or any digital IC verification task.
  OpenTitan-inspired verification pipeline: spec -> env/C headers/CSR tests -> sim -> sign-off.
  Orchestrates: spec-analyzer, rtl-gen, ral-gen, env-builder, test-generator,
  assertion-gen, scoreboard-gen, coverage-plan, doc-gen, sw-header-gen, csr-test-gen.
---

# digital-verify-pipeline

**Pipeline Orchestrator** (OpenTitan methodology):
One source spec → multiple outputs: RTL + UVM env + C headers + CSR auto-tests + docs.
No hand-maintained duplication. Every generated artifact is derived from `spec.yml`.

## When to Use

Use when:
- Starting verification for a new digital IP/block from a register spec
- Need register RTL + UVM RAL + SW driver headers from one spec
- Want CSR auto-tests (reset value + RW access verification)
- Generating standalone simulation testbenches
- Preparing verification sign-off documentation

Do NOT use for:
- Analog/mixed-signal verification
- Pure RTL coding without verification intent
- FPGA board-level testing

## Pipeline Sequence (10 Phases)

```
Phase 1: Parse
===============
spec-analyzer    → Parse YAML spec → verification plan + register map

Phase 2: Generate Design
=========================
rtl-gen          → Spec → synthesizable RTL (top + regs + irq)

Phase 3: Generate Verification IP
===================================
ral-gen          → Spec → UVM RAL (reg_block + reg_pkg)
env-builder      → Spec → UVM env (interfaces, agents, BFM, sequences)
test-generator   → Spec → test sequences per scenario
assertion-gen    → Spec → SVA assertions (APB protocol + register)
scoreboard-gen   → Spec → APB transaction scoreboard
coverage-plan    → Spec → functional/cross/toggle coverage goals

Phase 4: Document
==================
doc-gen          → Verification close report (SV file counts, test listing)

Phase 5: SW Interface
======================
sw-header-gen    → Spec → C header (register offsets + field bit definitions + driver helpers)

Offline (post-pipeline):
=========================
csr-test-gen     → Spec → CSR reset/RW auto-test → compile + simulate
run-sim          → RTL syntax check + simple TB simulation
```

## Key Design Principles (OpenTitan)

### 1. Single Source of Truth
One `spec.yml` → RTL + UVM + C headers + CSR tests + docs.
No manual synchronization needed.

### 2. Protocol-Agnostic Templates
Templates iterate over spec signals — any protocol works.
Adding UART/SPI/AXI = write YAML only, zero code changes.

### 3. Checkpoint/Resume
Every phase saves state to `.pipeline_state.json`.
`--resume` skips completed phases after a fix.

### 4. CSR Auto-Verification
- hw_reset_test: Every register matches spec reset value
- rw_access_test: Every RW register write/read consistency
- Compiles + runs automatically

### 5. CI-Ready
```bash
pro_verify.py --pipeline <spec>.yml     # 10 phases
run_sim.py --spec <spec>.yml --check-only  # RTL syntax
run_csr_test_gen.py --spec <spec>.yml      # CSR tests
```

## State Tracking

```yaml
# From .pipeline_state.json (auto-generated)
phases:
  spec-analyzer: { status: completed }
  rtl-gen: { status: completed }
  ral-gen: { status: completed }
  env-builder: { status: completed }
  test-generator: { status: completed }
  assertion-gen: { status: completed }
  scoreboard-gen: { status: completed }
  coverage-plan: { status: completed }
  doc-gen: { status: completed }
  sw-header-gen: { status: completed }
```

## Generating Bugs Found (CSR Reset Tests)

```
=== i2c CSR Reset ===
    PASS: ctrl_reg    = 0x14    (reset correct)
    PASS: status_reg  = 0x36    (reset correct)
    PASS: fifo_ctrl   = 0x110   (reset correct)
  *** ALL 9/9 RESET VALUES CORRECT ***
```

If mismatches found, the spec or RTL generation needs fixing.
