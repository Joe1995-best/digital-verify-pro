---
name: tb-compiler
version: 1.0.0
description: >
  Compile verification environment with EDA tool. Handles UVM package compilation,
  DUT RTL compilation, testbench compilation, generates compile scripts and
  Makefile targets for Questa/ModelSim, VCS, and Xcelium simulators.
---

# tb-compiler v1.0.0

**Runner Agent Phase 1** — Compile testbench + DUT.

## Quick Start

```bash
cd standalone-skills/tb-compiler
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --tool questa
python run.py --spec ../../i2c_spec.yml --tool vcs
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |
| `--tool <name>` | CLI arg | no | Simulator tool (questa, vcs, xcelium); auto-detect if omitted |

## Outputs

| Output | Description |
|--------|-------------|
| Compile scripts | `.do` / Makefile for target simulator |
| Compiled simv | Simulation executable (if tool available) |
| Compilation log | `compile.log` with results |

## Supported EDA Tools

| Tool | Script | Notes |
|------|--------|-------|
| Questa/ModelSim | `compile.do` | Full UVM 1.2/1800.2 support |
| VCS | `Makefile` + `.synopsys_dc.setup` | Full compile with UVM |
| Xcelium | `Makefile` + `cds.lib` | IUS/Xcelium support |

## Capabilities

### 1. UVM Package Compilation
- UVM 1.2 and IEEE 1800.2 support
- UVM library detection and path configuration
- Package compilation ordering

### 2. DUT RTL Compilation
- RTL source discovery and compilation
- Include path handling
- Macro definitions from spec

### 3. Testbench Compilation
- Full verification environment compilation
- Generated SV file compilation
- Scoreboard, coverage, assertions inclusion

### 4. Script Generation
- Simulator-specific compile scripts (Questa .do, VCS Makefile)
- Configurable compile options
- Automatic simulator detection

## Dependencies

- **Python**: >= 3.10
- **Runtime**: none (pure Python standard library)
- **Internal**: `lib/template_engine.py`, `lib/questa_vcs_support.py`
- **Optional**: Questa/ModelSim, VCS, or Xcelium installed
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | UVM package + DUT compile only |
| standard | Full testbench compile with scoreboard/coverage |
| intensive | Multi-library compile + optimization flags |
| exhaustive | All EDA tools with incremental compilation |

## Upstream

- `env-builder` — consumes generated verification environment
- `test-generator` — consumes generated test sequences
- Design RTL sources

## Downstream

- `sim-runner` — produces compiled simulation executable


## Effort

| Effort | Compile flags |
|--------|--------------|
| lite | Minimal flags, no debug |
| standard | Basic debug (waveform dump) |
| intensive | Full debug + coverage collection |
| exhaustive | Full + formal checks |

