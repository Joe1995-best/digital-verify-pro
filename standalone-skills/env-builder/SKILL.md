---
name: env-builder
version: 1.0.0
description: >
  Generate UVM verification environment skeleton from specification. Builds tb_top,
  interface wrappers, UVM agent/monitor/sequencer, environment, and testbench harness.
  Protocol-agnostic: handles I2C, GPIO, SPI, UART, AXI, PCIe identically.
---

# env-builder v1.0.0

**Verification Architect Phase 2** — UVM environment generation.

## Quick Start

```bash
cd standalone-skills/env-builder
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |

## Outputs (into `rtl/verification/env/`)

| File | Description |
|------|-------------|
| `tb_top.sv` | Top-level testbench harness |
| `{module}_env.sv` | UVM environment class |
| `env_pkg.sv` | UVM package with includes |
| `{module}_agent.sv` | UVM agent (driver, monitor, sequencer) |
| `{module}_driver.sv` | Protocol driver |
| `{module}_monitor.sv` | Protocol monitor |
| `{module}_sequencer.sv` | UVM sequencer |
| `{module}_if.sv` | SystemVerilog interface |
| `sim/Makefile` | Simulation Makefile |

## Capabilities

### 1. UVM Skeleton Generation
- Generate complete UVM environment: agent, driver, monitor, sequencer
- Interface wrappers per protocol type
- Testbench harness with clock/reset generation

### 2. Protocol-Agnostic Architecture
- No protocol-specific code paths in templates
- All protocols handled identically through template iteration
- Supports: I2C, GPIO, SPI, UART, AXI, PCIe, and custom

### 3. Simulation Ready
- Generate compilable SystemVerilog immediately
- UVM 1.2 / 1800.2 compatible
- Makefile generation for common simulators

### 4. Validation
- Post-generation structural validation
- Checks for required component presence
- Interface signal consistency verification

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`, `jinja2`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS

## Effort

| Level | Agents | Interfaces |
|-------|--------|------------|
| lite | 1 agent, minimal | 1 interface |
| standard | All agents | All interfaces |
| intensive | Agents + scoreboard hooks | Full interface matrix |
| exhaustive | Full UVM environment | Complete verification env |

## Upstream

- `spec-analyzer` — consumes interface list + register map
- Design specification (YAML)

## Downstream

- `test-generator` — consumes env structure for sequence generation
- `tb-compiler` — consumes env for compilation
- `assertion-gen` — consumes interface definitions
