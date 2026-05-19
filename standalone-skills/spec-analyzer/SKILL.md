---
name: spec-analyzer
version: 2.0.0
description: >
  Parse spec YAML into a full verification plan. Identifies protocols, interfaces,
  registers, FSM configurations, and generates test scenarios with functional
  coverage goals. Protocol-aware: I2C, APB, SPI, UART, DMA recognition.
---

# spec-analyzer v2.0.0

**Verification Plan Generator** — From spec YAML to structured verification plan.

## Quick Start

```bash
cd standalone-skills/spec-analyzer
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | yes | Output directory for generated artifacts |

## Outputs

| Output | Description |
|--------|-------------|
| `verification-plan.md` | Full verification plan with scenarios, coverage goals, pass criteria |
| `interface-list.yml` | All interfaces with protocol type, direction, signal list |
| `register-map.yml` | Complete register map from spec |
| `test-scenarios.yml` | Test cases derived from spec |

## Capabilities

### 1. Interface Detection
- APB / AHB / AXI / AXI-Stream / AXI-Lite
- I2C / SPI / UART / I2S / JTAG
- Custom interfaces (user-defined)
- Protocol version detection

### 2. Register Analysis
- Extract address map from spec
- Detect field types (RW/RO/WO/W1C/RW1C)
- Flag reserved spaces and address holes
- Generate IP-XACT from YAML, or vice versa

### 3. Protocol-Aware Scenario Generation (v2)
- I2C: write/read/RSTART/10bit addr/NACK/arbitration/clock stretch
- APB: single/sequential/error/back-to-back
- SPI: mode-0/1/2/3, single/dual/quad

### 4. Coverage Planning
- Functional cover points per feature
- Cross coverage between interfaces
- Protocol-specific coverage bins
- Register coverage (all addressable locations)

### 5. FSM Analysis (v2)
- FSM state extraction from spec
- Transition coverage goals
- State encoding detection

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml` (for YAML parsing)
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Scenarios | Coverage detail |
|--------|-----------|-----------------|
| lite | 3-5 basic tests | Functional only |
| standard | 8-12 tests | Functional + protocol |
| intensive | 15-25 tests | Full scenario matrix |
| exhaustive | 30+ tests | All scenarios + cross coverage + bugs |

## Upstream

Design specification (YAML)

## Downstream

- `env-builder` — consumes interface list + register map
- `test-generator` — consumes test scenarios
- `coverage-plan` — consumes coverage goals
