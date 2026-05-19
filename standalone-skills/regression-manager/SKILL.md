---
name: regression-manager
version: 1.0.0
description: >
  Regression test suite manager. Multi-run regression tracking with history,
  performance trend analysis, result comparison, and historical database.
---
# regression-manager v1.0.0

Standalone skill from digital-verify-pro.

## Quick Start
```bash
cd standalone-skills/regression-manager
python run.py --module TOP --total 66 --passed 66
python run.py --list
python run.py --compare --run-a run001 --run-b run002
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--module` | CLI arg | yes | Module name for this regression run |
| `--total` | CLI arg | yes | Total test count |
| `--passed` / `--failed` | CLI arg | yes | Pass/fail counts |
| `--coverage` | CLI arg | no | Coverage percentage |
| `--iterations` | CLI arg | no | Number of regression iterations |
| `--list` | CLI arg | no | List all historical runs |
| `--compare` | CLI arg | no | Compare two runs |

## Outputs

| Output | Description |
|--------|-------------|
| `regression_db.json` | Historical regression database (JSON) |
| `trends.json` | Trend chart data (pass rate, coverage over time) |

## Capabilities

### 1. Multi-Run Regression Tracking
- Auto-run-id generation (timestamp-based)
- Persistent JSON database
- Rich metadata per run (module, RTL hash, git commit)

### 2. Run Comparison
- Pass/fail diff between any two runs
- Performance delta (compile/sim time)
- Coverage change tracking

### 3. Performance Trend Analysis
- Sim time trends over iterations
- Compile time history
- Pass rate evolution

### 4. Trend Chart Data Generation
- Clean JSON output ready for dashboard ingestion
- Coverage convergence tracking
- Test count trends

## Dependencies

- **Python**: >= 3.10
- **Runtime**: Pure Python standard library (no third-party deps)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic run recording + list |
| standard | Full tracking + run comparison |
| intensive | Trend analysis + coverage tracking |
| exhaustive | CI integration + webhook notifications |

## Upstream

- sim-runner (simulation results)
- coverage-engine (coverage data)

## Downstream

- dashboard-gen (trend visualization)
- doc-gen (regression summary in sign-off report)
