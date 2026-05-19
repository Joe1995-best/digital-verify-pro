---
name: sim-runner
version: 1.0.0
description: >
  Run simulations with generated testbenches. Manages test execution, seed
  variation, result logging, pass/fail determination, and simulation log
  analysis for Questa/ModelSim, VCS, and Xcelium simulators.
---

# sim-runner v1.0.0

**Runner Agent Phase 2** — Execute simulations.

## Quick Start

```bash
cd standalone-skills/sim-runner
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --tool questa
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |
| `--tool <name>` | CLI arg | no | Simulator tool (questa, vcs, xcelium) |

## Outputs

| Output | Description |
|--------|-------------|
| Simulation logs | Per-test log files with UVM messages |
| `sim_results.yml` | Pass/fail summary per test and seed |
| Waveform dumps | VCD/FSDB waveform files (optional) |

## Supported Flow

```bash
# Run all tests with multiple seeds
python run.py --spec ../../i2c_spec.yml
# Results saved to output/sim_results/
```

## Capabilities

### 1. Test Execution
- Run all tests from the test list with seed variation
- Configurable seeds per test based on effort level
- Sequential test execution with pass/fail logging

### 2. Log Analysis
- UVM_ERROR/UVM_FATAL message extraction with timestamps
- Pass/fail count per test
- Covergroup coverage percentage extraction

### 3. Result Aggregation
- `sim_results.yml` with per-test pass/fail summary
- Total pass/fail statistics
- Seed variation results

### 4. Post-Simulation Cleanup
- Waveform dump generation (optional)
- Simulation artifact organization

## Dependencies

- **Python**: >= 3.10
- **Runtime**: none (pure Python standard library)
- **Internal**: `lib/template_engine.py`, `lib/questa_vcs_support.py`
- **Required**: Questa/ModelSim, VCS, or Xcelium installed for actual simulation
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Single seed per test, basic pass/fail log |
| standard | Multiple seeds, UVM log analysis |
| intensive | Seed variation + coverage extraction |
| exhaustive | Full simulation + waveform collection + trends |

## Upstream

- `tb-compiler` — consumes compiled simulation executable
- `test-generator` — consumes test list for execution
- `coverage-plan` — coverage model active during simulation

## Downstream

- `waveform-analyzer` — produces post-simulation analysis
- `doc-gen` — consumes simulation results for documentation


## Effort

| Effort | Depth |
|--------|-------|
| lite | Single seed, no waveform |
| standard | 3 seeds, basic logging |
| intensive | 10 seeds, waveform dump |
| exhaustive | Full regression + coverage collection |

