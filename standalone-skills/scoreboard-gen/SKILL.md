---
name: scoreboard-gen
version: 1.0.0
description: >
  Generate UVM scoreboard and checker components. Creates data comparison,
  protocol checking, and end-to-end data integrity verification.
  Protocol-agnostic scoreboard generation from spec YAML.
---

# scoreboard-gen v1.0.0

**Verifier Agent** — Scoreboard and checker generation.

## Quick Start

```bash
cd standalone-skills/scoreboard-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |

## Outputs (into `rtl/verification/env/scoreboard/`)

| File | Description |
|------|-------------|
| `{module}_sb.sv` | Scoreboard with comparison logic |

## Capabilities

### 1. Scoreboard Generation
- Expected vs actual data comparison
- Transaction-level checking
- Ordering checks for in-order protocols

### 2. Protocol Checking
- Interface-level protocol compliance
- Data integrity verification
- End-to-end transaction checking

### 3. Post-Generation Validation
- Scoreboard structural validation
- SV file consistency checks

## Dependencies

- **Python**: >= 3.10
- **Runtime**: none (pure Python standard library)
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Upstream

- `spec-analyzer` — consumes verification plan + interface list
- `regmodel-gen` — optionally consumes register map for expected values

## Downstream

- `tb-compiler` — consumes scoreboard for compilation
- `sim-runner` — scoreboard active during simulation
- `doc-gen` — includes scoreboard in verification close report
