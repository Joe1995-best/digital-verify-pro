---
name: fsm-templates
version: 1.0.0
description: >
  FSM controller templates from spec YAML. Generates synthesizable FSM RTL
  with unified always_ff pattern, interrupt auto-management, and error handling.
  Supports DMA 8-state and simple 3-state controllers following dma.sv v4
  verified patterns.
---

# fsm-templates v1.0.0

FSM controller template generator for digital IC verification. Produces
synthesizable SystemVerilog FSM controllers with unified always_ff blocks,
interrupt auto-set with W1C clear, error_flag persistence, and coverage-friendly
patterns. Follows dma.sv v4 verified design style.

## Quick Start

```bash
cd standalone-skills/fsm-templates
python run.py --help
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| Spec YAML | Pipeline data | yes | Module spec with FSM configuration section |
| `fsm.name` | spec YAML | yes | FSM module name |
| `fsm.type` | spec YAML | no | FSM type: dma (8-state) or simple (3-state) |
| `fsm.host_width` | spec YAML | no | Host bus address width (default: 32) |
| `fsm.status_regs` | spec YAML | no | Status signal configuration list |
| `fsm.error_configs` | spec YAML | no | Error condition configurations |
| `fsm.interrupts` | spec YAML | no | Interrupt signal configurations |
| `fsm.combo_outputs` | spec YAML | no | Combinatorial output expressions |

## Outputs

| Output | Description |
|--------|-------------|
| `{module}_{fsm_name}.sv` | Generated SystemVerilog FSM controller module |

## Capabilities

### 1. DMA 8-State FSM Generation
- Full DMA read/write pipeline: Idle → Read → SendRead → WaitRead → Write → SendWrite → WaitWrite → Done
- Host bus interface with request/grant protocol
- Address increment and chunk counter support
- Remaining data count tracking with auto-complete detection

### 2. Simple 3-State FSM Generation
- Lightweight controller: Idle → Active → Done
- Minimal state machine for simple control flows
- Reduced port count for lower complexity designs

### 3. Interrupt Auto-Management
- Auto-set interrupt status registers on done/chunk/error events
- W1C (Write-1-to-Clear) support via APB interface
- Interrupt enable masking with AND-gated outputs
- Persistent interrupt state across clears

### 4. Error Handling and Coverage Compliance
- Error_flag persistence (NOT cleared every cycle — avoids coverage warnings)
- Error_code tracking with configurable error conditions
- No `inside` operator, no `unique case`, no `always_comb` reading FF vars
- Coverage-friendly RTL patterns (dma.sv v4 verified)

### 5. Spec-Driven Configuration
- Fully parameterized from spec YAML FSM section
- Automatic `fold_inside` conversion for iverilog 11 compatibility
- Port list auto-generated from status/interrupt/error configs

## Dependencies

- **Python**: >= 3.10
- **Runtime**: none (pure Python standard library)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Simple 3-state FSM only |
| standard | DMA 8-state FSM with default parameters |
| intensive | Full DMA FSM with custom status/interrupt/error configs |
| exhaustive | Complete FSM with combo outputs + custom host width |

## Upstream

- `spec-analyzer` — parsed spec dict with FSM configuration
- Design specification (YAML)

## Downstream

- `tb-compiler` — compiles generated FSM RTL
- `sim-runner` — simulates FSM behavior
- `dashboard-gen` — shows FSM coverage from dashboard
