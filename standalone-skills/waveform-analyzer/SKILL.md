---
name: waveform-analyzer
version: 1.0.0
description: >
  Analyze simulation results, extract coverage metrics, and identify failures
  from waveform dumps and log files. Post-simulation analysis for verification
  closure assessment.
---

# waveform-analyzer v1.0.0

**Runner Agent Phase 3** — Post-simulation analysis.

## Quick Start

```bash
cd standalone-skills/waveform-analyzer
python run.py --log sim_results/sim.log
python run.py --vcd output.vcd --report coverage_report.json
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| Simulation logs | sim-runner | yes | Test execution log files |
| Waveform dumps | sim-runner | optional | VCD/FSDB waveform files |
| Coverage databases | sim-runner | optional | Coverage data for analysis |

## Outputs

| Output | Description |
|--------|-------------|
| `coverage_report.md` | Coverage metrics summary |
| `failure_report.json` | Identified failures with details |
| `coverage_report.json` | Structured coverage data |

## Capabilities

### 1. Log File Analysis
- Extract UVM_ERROR/UVM_FATAL messages with timestamps
- Count pass/fail per test
- Summarize covergroup coverage percentage
- Identify simulation runtime warnings

### 2. Waveform Analysis
- VCD file parsing and signal dump analysis
- Signal toggle counting for coverage
- Protocol timing violation detection
- Bus transaction extraction and validation

### 3. Coverage Metrics Extraction
- Functional coverage percentage from logs
- Toggle coverage from VCD
- Coverage gap identification
- Coverage closure assessment

### 4. Failure Classification
- Timeout detection
- Assertion failures with hierarchy paths
- Protocol violation classification
- Severity-based failure ranking

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml` (optional, for structured reports)
- **OS**: Windows / Linux / macOS
- **Optional**: PyVCD or VCD parsing library for waveform analysis

## Upstream

- `sim-runner` — consumes simulation logs and waveform dumps

## Downstream

- `doc-gen` — consumed for verification close documentation
- `coverage-plan` — coverage gap feedback for targeted generation
