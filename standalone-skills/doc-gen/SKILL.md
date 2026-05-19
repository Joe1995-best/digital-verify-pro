---
name: doc-gen
version: 1.0.0
description: >
  Generate verification documentation: verification close report and documentation
  from all verification artifacts. Protocol-agnostic documentation generation that
  counts and catalogs all generated verification environment files.
---

# doc-gen v1.0.0

**Documentation Agent** — Verification close documentation generation.

## Quick Start

```bash
cd standalone-skills/doc-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |
| Pipeline output | `--out/rtl/verification/env/` | no | Generated environment files for counting |

## Outputs

| Output | Description |
|--------|-------------|
| `docs/verification-close-report.md` | Complete verification closure report |

## Capabilities

### 1. Verification Close Report
- Module and spec summary
- Interface, register, and test scenario counts
- Generated SV file inventory (interfaces, agents, sequences, assertions, scoreboards, coverage)
- Test scenario descriptions

### 2. Environment Inventory
- Report counts of all generated verification components
- Breakdown by category (IF, agent, sequence, assertion, scoreboard, coverage)
- Key file listing (testbench, environment, package, Makefile)

### 3. Post-Generation Validation
- Validate report generation completeness
- Check output directory structure

## Dependencies

- **Python**: >= 3.10
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Upstream

All verification generation tools:
- `env-builder` — environment component counts
- `test-generator` — sequence counts
- `assertion-gen` — assertion counts
- `scoreboard-gen` — scoreboard counts
- `coverage-plan` — coverage counts
- `sim-runner` — simulation results
- `waveform-analyzer` — coverage metrics

## Downstream

- Final verification sign-off documentation
