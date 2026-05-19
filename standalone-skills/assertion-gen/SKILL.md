---
name: assertion-gen
version: 1.0.0
description: >
  Generate SystemVerilog Assertions (SVA) from specification. Covers interface
  protocols, internal invariants, register access rules, and timing requirements.
  Protocol-agnostic — handles any interface type defined in spec YAML.
---

# assertion-gen v1.0.0

**Verifier Agent** — SVA assertion generation.

## Quick Start

```bash
cd standalone-skills/assertion-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |

## Outputs (into `rtl/verification/env/assertions/`)

| File | Description |
|------|-------------|
| `apb_assert.sv` | APB protocol assertions |
| `reset_assert.sv` | Reset behavior assertions |
| `reg_assert.sv` | Register access rule assertions |

## Capabilities

### 1. Interface Protocol Assertions
- APB read/write protocol timing checks
- Handshake sequence verification
- Address/data phase separation

### 2. Reset Assertions
- Active-low/active-high reset timing
- Async/sync reset assertion/deassertion
- Reset state entry/exit conditions

### 3. Register Assertions
- Read-only vs writable field verification
- Reserved bit stability assertions
- Address decode bounds checking

### 4. Post-Generation Validation
- Structural integrity checks on generated SV files
- Assertion count verification
- Syntax-level consistency validation

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Effort

| Level | Assertions | Coverage |
|-------|------------|----------|
| lite | Core APB + reset | Basic protocol compliance |
| standard | APB + reset + register | Full interface compliance |
| intensive | All + protocol-specific | Comprehensive assertions |
| exhaustive | Full + custom properties | Sign-off ready |

## Upstream

- `spec-analyzer` — consumes interface list + register map
- Design specification (YAML)

## Downstream

- `tb-compiler` — consumes assertions for compilation
- `sim-runner` — assertions active during simulation
- `formal-check` — assertions reusable for formal verification
