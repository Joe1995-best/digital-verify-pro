---
name: dashboard-gen
version: 1.0.0
description: >
  Verification HTML dashboard generator. Creates interactive dashboards with
  coverage gauges, test result tables, regression trends, and heatmaps.
---
# dashboard-gen v1.0.0

Standalone skill from digital-verify-pro.

## Quick Start
```bash
cd standalone-skills/dashboard-gen
python run.py --module i2c --output dashboard.html --total 66 --passed 66
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--module` | CLI arg | yes | DUT module name |
| `--output` | CLI arg | yes | Output HTML file path |
| `--total` | CLI arg | no | Total test count |
| `--passed` | CLI arg | no | Passed test count |
| `--failed` | CLI arg | no | Failed test count |
| `--toggle-cov` | CLI arg | no | Toggle coverage percentage |
| `--fsm-cov` | CLI arg | no | FSM coverage percentage |
| `--func-cov` | CLI arg | no | Functional coverage percentage |
| `--iterations` | CLI arg | no | Regression iteration count |
| `--tests` | CLI arg | no | JSON array of test results |

## Outputs

| Output | Description |
|--------|-------------|
| `dashboard.html` | Interactive HTML dashboard (self-contained, no server needed) |

## Capabilities

### 1. Coverage Gauges
- Animated gauge charts for toggle / FSM / functional coverage
- Color-coded thresholds (red < 70%, amber < 90%, green >= 90%)

### 2. Test Results Table
- Sortable by test name / status / duration
- Pass/fail icons with color coding
- Per-test details expandable

### 3. Regression Trend Charts
- Pass/fail over regression iterations
- Coverage convergence trends

### 4. FSM Coverage Visualization
- State visit counts
- Transition coverage heatmap

### 5. Coverage Heatmap
- Module-level coverage breakdown
- Color intensity by coverage percentage

## Dependencies

- **Python**: >= 3.8
- **Runtime**: Pure Python standard library
- **Browser**: Any modern browser (Chart.js loaded from CDN)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Dashboard depth |
|--------|-----------------|
| lite | Basic gauges + test table |
| standard | Full dashboard + trend charts |
| intensive | All features + heatmap |
| exhaustive | Custom plugins + export |

## Upstream

- coverage-engine (coverage data)
- sim-runner (simulation results)
- regression-manager (regression history)

## Downstream

- doc-gen (dashboard screenshots for sign-off)
