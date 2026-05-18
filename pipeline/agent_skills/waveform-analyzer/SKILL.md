---
name: waveform-analyzer
description: >
  Analyze simulation results, extract coverage metrics, identify failures
  from waveform dumps and log files.
---

# waveform-analyzer

**Runner Agent Phase 3**: post-simulation analysis.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Simulation logs | sim-runner | yes |
| Waveform dumps | sim-runner | optional |
| Coverage databases | sim-runner | optional |

## Capabilities

### 1. Log File Analysis
- Extract UVM_ERROR/UVM_FATAL messages with timestamps
- Count pass/fail per test
- Summarize covergroup coverage percentages
- Identify performance bottlenecks (long tests)

### 2. Coverage Analysis

```tcl
# urg report (VCS)
urg -dir simv.vdb -report coverage_report/

# imc report (Xcelium)
imc -load coverage_data -report coverage_report/

# merge and compare
urg -dir simv_*.vdb -dbname merged.vdb -report merged_report/
```

Coverage report summary:
```yaml
coverage_summary:
  functional:
    covergroups: 92%
    coverpoints: 87%
    cross_bins: 76%
  toggle: 95%
  line: 89%
  branch: 84%
  fsm: 91%
```

### 3. Failure Analysis
- Match UVM_ERROR messages with specific assertions
- Identify failing test sequences
- Group failures by root cause
- Produce debugging recommendations

## Outputs

| File | Description |
|------|-------------|
| `coverage_report.md` | Coverage summary and gaps |
| `failure_analysis.yml` | All failures grouped by type |
| `debug_recommendations.md` | Suggestions for fixing failures |
