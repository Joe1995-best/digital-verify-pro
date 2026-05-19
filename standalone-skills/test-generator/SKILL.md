---
name: test-generator
version: 2.0.0
description: >
  Generate UVM test sequences from verification scenarios. Protocol-aware,
  category-dispatched test sequence generator with coverage gap injection.
  Supports register, protocol, stress, FIFO, and interrupt sequence categories.
---

# test-generator v2.0.0

**Verifier Agent** — UVM test sequence generation.

## Quick Start

```bash
cd standalone-skills/test-generator
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --gaps coverage_gaps.json
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |
| `--gaps <file>` | CLI arg | no | Coverage gaps JSON for targeted test generation |

## Outputs (into `rtl/verification/env/sequences/`)

| File | Description |
|------|-------------|
| `{module}_base_seq.sv` | Base sequence class |
| `{module}_reg_seq.sv` | Register access sequences |
| `{module}_protocol_seq.sv` | Protocol sequences |
| `{module}_stress_seq.sv` | Stress test sequences |
| `{module}_fifo_seq.sv` | FIFO fill/drain sequences |
| `{module}_intr_seq.sv` | Interrupt sequences |
| `{module}_gap_seq.sv` | Coverage gap closure sequences |

## Capabilities

### 1. Category-Based Sequence Generation
- Register: field-level RMW, bit-bash, reserved-bit, atomic operations
- Protocol: bus transactions per protocol (I2C, SPI, etc.)
- Stress: back-to-back, random delays, max throughput
- FIFO: fill/drain, overflow, watermark crossing
- Interrupt: assert/clear, nested, masked

### 2. Coverage Gap Injection
- Reads coverage gaps JSON from coverage-engine
- Generates targeted sequences to close specific coverage holes
- Self-checking assertions and coverage sampling built-in

### 3. Rich Register Sequences
- Field-level read-modify-write
- Bit-bash for all writable fields
- Reserved bits stability checking
- Atomic read-modify-write operations

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`, `jinja2`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Effort

| Level | Sequences | Coverage per test |
|-------|-----------|-------------------|
| lite | 3-5 basic | Functional only |
| standard | 8-12 | Functional + protocol |
| intensive | 15-25 | Full scenario matrix |
| exhaustive | 30+ | All scenarios + gaps |

## Upstream

- `spec-analyzer` — consumes test scenarios + interface list
- `env-builder` — consumes env structure for sequence reuse
- `coverage-engine` — optionally consumes coverage gaps

## Downstream

- `sim-runner` — consumes test sequences for simulation execution
- `tb-compiler` — consumes sequences for compilation
