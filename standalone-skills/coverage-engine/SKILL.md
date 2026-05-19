---
name: coverage-engine
version: 2.0.0
description: >
  VCD-based toggle coverage analysis engine. Pure Python VCD parser with
  full-signal per-bit toggle analysis, activity classification, coverage gap
  detection, severity ranking, and zero stuck-signal verification.
---

# coverage-engine v2.0.0

**Coverage Analysis Engine** — Pure Python, no EDA tool dependency.

一键分析 VCD 文件的 toggle 覆盖率，产出 JSON + Markdown 报告。

## Quick Start

```bash
cd standalone-skills/coverage-engine
python run.py --vcd ../../i2c.vcd --report coverage_report.json --markdown
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `*.vcd` file | Simulation output | yes | Value Change Dump from iverilog/VCS/Questa |
| `--report <path>` | CLI arg | no | Output JSON report path |
| `--top <module>` | CLI arg | no | Top module for scope filtering |
| `--markdown` | CLI arg | no | Also generate markdown report |

## Outputs

| Output | Description |
|--------|-------------|
| `<report>.json` | Full per-signal toggle stats, activity levels, gap analysis |
| `<report>.md` | Human-readable coverage summary (with `--markdown`) |

## Capabilities

### 1. Pure Python VCD Parsing
- Zero third-party dependencies
- Full scope hierarchy (`$scope`/`$upscope` tracking for scoped signal names)
- Multi-bit value parsing (binary strings, hex, decimal)

### 2. Per-Signal Toggle Analysis
- Every signal in VCD, every bit position
- Transition count (not just binary 0/1 presence)
- Activity level classification:
  - `VERY_HIGH`: >100 transitions
  - `HIGH`: 11-100 transitions
  - `MEDIUM`: 2-10 transitions
  - `LOW`: 1 transition
  - `NONE`: 0 transitions

### 3. Coverage Gap Detection
- Stuck-at signals (0 transitions) with severity ranking
- Critical: internal control signals stuck
- High: data bus bits stuck
- Medium/Low: other low-activity signals
- Sorted output (worst first) with test recommendations

### 4. Zero Stuck-Signal Verification
- When all signals show >0 transitions → proves toggle coverage convergence

### 5. CLI Usage

```bash
# Basic analysis
python run.py --vcd dump.vcd --report coverage.json

# With markdown report
python run.py --vcd dump.vcd --report coverage.json --markdown
```

## Validation

| Example | Signals | Stuck | Status |
|---------|---------|:-----:|:------:|
| i2c_full (i2c.vcd) | 37 | 0 | Verified |
| dma_full (dma_full_test.vcd) | 117 | 0 | Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: None (pure standard library)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic toggle (binary 0/1) |
| standard | Per-bit toggle + activity levels |
| intensive | Gap detection + severity ranking |
| exhaustive | Cross-signal correlation + test generation bridge |

## Upstream

Simulators producing VCD: `sim-runner`, `tb-compiler` (iverilog / VCS / Questa)

## Downstream

- `coverage-gap-plugin` — gap JSON → targeted test generation
- `dashboard-gen` — coverage reports → HTML dashboards
