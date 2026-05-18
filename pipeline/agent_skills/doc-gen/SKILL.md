---
name: doc-gen
description: >
  Generate verification documentation: verification plan, test specification,
  coverage report, and verification close report.
---

# doc-gen

**Documentation Agent**: generate verification close documentation.

Produces structured documentation from all verification artifacts for sign-off ready reporting.

## Inputs

| Input | Source |
|-------|--------|
| All pipeline outputs | pipeline |
| `sim_results.yml` | sim-runner |
| `coverage_report.md` | waveform-analyzer |

## Outputs

| Output | Description |
|--------|-------------|
| `verification-close-report.md` | Complete sign-off report |
| `test-specification.md` | All tests with descriptions and results |
| `coverage-analysis.md` | Coverage closure analysis |
| `bug-list.md` | All bugs found during verification |
| `regression-summary.md` | Regression pass/fail matrix |
