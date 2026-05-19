---
name: feature-decomposer
version: 1.0.0
description: >
  Feature-driven testpoint decomposition engine. Decomposes spec features into
  verification testpoints with stimulus, checking, and coverage goals. Generates
  testpoints from spec FEATURES (not RTL code), marking unimplemented features
  as gaps for verification completeness tracking.
---

# feature-decomposer v1.0.0

Verification testpoint decomposition engine. Takes a spec YAML and produces a
complete set of verification testpoints derived from feature definitions.
Each testpoint includes stimulus description, checking mechanism, verification
stage (V1 smoke / V2 stress / V3 signoff), and RTL implementation status
(IMPLEMENTED / PARTIAL / UNIMPLEMENTED).

## Quick Start

```bash
cd standalone-skills/feature-decomposer
python run.py --help
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| Spec dict | Pipeline | yes | Parsed spec YAML dictionary with features, registers, interfaces |
| `features` | spec YAML | yes | Feature definitions with name, description, category, rtl_status |
| `registers` | spec YAML | no | Register map for register-level testpoints |
| `interfaces` | spec YAML | no | Interface definitions for protocol detection |

## Outputs

| Output | Description |
|--------|-------------|
| Testpoint list | List of `Testpoint` dataclass instances |
| Verification plan (MD) | Markdown verification plan with per-feature testpoint tables |
| Verification plan (JSON) | JSON-serializable testpoint data for downstream tools |

## Capabilities

### 1. Spec-Driven Testpoint Decomposition
- Decomposes each spec feature into 1+ focused testpoints
- Protocol-specific testpoint generation (I2C controller, I2C target, multi-controller, etc.)
- Auto-detection of features from module description and register fields
- Feature-driven approach: testpoints generated from spec, not RTL

### 2. Register-Focused Testpoint Generation
- UVM register testpoints (read/write, reset value, bit-bash)
- Reserved bit checking with write-1s-read-0 verification
- Field-level access policy validation
- Register address decoding verification

### 3. Protocol-Aware Feature Detection
- Automatic I2C protocol feature detection from spec description
- Multi-controller / clock-stretching / 10-bit address detection
- Speed configuration, FIFO, interrupt, DMA transfer features
- Reset, error handling, host interface register-level detection

### 4. Multi-Stage Verification Planning
- V1 smoke testpoints for basic bring-up
- V2 stress/feature testpoints for comprehensive testing
- V3 signoff testpoints for coverage closure
- RTL status tracking (IMPLEMENTED / PARTIAL / UNIMPLEMENTED)

### 5. Gap Analysis and Coverage Tracking
- UNIMPLEMENTED features automatically marked in generated testpoints
- Per-feature implementation status summary
- Summary statistics: total testpoints, V1/V2/V3 breakdown, gap count

## Dependencies

- **Python**: >= 3.10
- **Runtime**: none (pure Python standard library)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic feature decomposition (default templates only) |
| standard | Protocol-aware decomposition with register testpoints |
| intensive | Full decomposition with all protocol-specific testpoints |
| exhaustive | Complete decomposition + custom feature mapping + JSON plan |

## Upstream

- `plan-generator` — verification plan with RTL analysis
- `spec-analyzer` — parsed spec dictionary with features and registers

## Downstream

- `test-generator` — consumes testpoints to generate UVM test sequences
- `regmodel-gen` — cross-references register testpoints with RAL model
- `coverage-plan` — coverage goals derived from testpoint list
- `dashboard-gen` — test results match testpoint plan
