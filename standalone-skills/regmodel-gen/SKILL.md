---
name: regmodel-gen
version: 1.0.0
description: >
  Generate UVM Register Abstraction Layer (RAL) model from spec register map.
  Creates IEEE 1800.2 compliant uvm_reg_block, registers, and fields with
  full access methods and address decoding.
---

# regmodel-gen v1.0.0

**Verifier Agent** — UVM register model generation.

## Quick Start

```bash
cd standalone-skills/regmodel-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |

## Outputs (into `rtl/verification/env/ral/`)

| File | Description |
|------|-------------|
| `{module}_ral_block.sv` | UVM reg_block with all registers and fields |
| `{module}_ral_pkg.sv` | UVM package importing the RAL model |

## Capabilities

### 1. Register Model Generation
- IEEE 1800.2 compliant RAL model
- Reg_block with hierarchical register organization
- Register fields with access policy (RW, RO, WO, W1C, RW1C)
- Address map with correct address decoding

### 2. Field Access Method Generation
- Read/write methods per access type
- Volatile and non-volatile field handling
- Hardware vs software access differentiation

### 3. Package Structure
- Complete UVM package with all necessary imports
- Compilable with UVM 1.2 and 1800.2

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`
- **Internal**: `lib/template_engine.py`
- **OS**: Windows / Linux / macOS

## Effort

| Level | Registers | Fields |
|-------|-----------|--------|
| lite | Core address map only | Basic fields |
| standard | All registers | Full field definitions |
| intensive | Full model + aliases | All access types |
| exhaustive | Complete RAL + verification | Every register corner |

## Upstream

- `spec-analyzer` — consumes register map
- Design specification (YAML)

## Downstream

- `tb-compiler` — consumes RAL model for compilation
- `test-generator` — uses RAL for register sequences
- `scoreboard-gen` — uses RAL for expected value checking
