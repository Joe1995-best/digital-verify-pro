---
name: coverage-plan
version: 1.0.0
description: >
  Generate functional coverage groups from verification plan. Creates covergroup
  definitions for interfaces, registers, internal states, and cross coverage.
  Protocol-agnostic coverage generation from spec YAML.
---

# coverage-plan v1.0.0

**Verification Architect Phase 1** — Coverage definition.

## Quick Start

```bash
cd standalone-skills/coverage-plan
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |

## Outputs (into `rtl/verification/env/coverage/`)

| File | Description |
|------|-------------|
| `{module}_cov.sv` | Generated functional coverage groups |

## Capabilities

### 1. Interface Coverage
- Transaction type coverage bins
- Address range coverage
- Data value coverage

### 2. Register Coverage
- All register address access coverage
- Field-level value coverage
- Read/write operation coverage

### 3. Cross Coverage
- Interface × Register cross coverage
- Protocol state × data cross coverage

### 4. Post-Generation Validation
- Coverage group structural validation
- Coverage model completeness check

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Effort

| Level | Coverpoints | Cross coverage |
|-------|-------------|----------------|
| lite | Interface only | None |
| standard | Interface + registers | Basic cross |
| intensive | Full coverage plan | Full cross coverage |
| exhaustive | All + corner cases | Complete closure plan |

## Upstream

- `spec-analyzer` — consumes interface list + register map + test scenarios
- `formal-check` — optionally consumes formal coverage results

## Downstream

- `sim-runner` — coverage collected during simulation
- `waveform-analyzer` — coverage metrics extracted post-sim
