---
name: plan-generator
version: 1.0.0
description: >
  ### 1. Deep RTL Analysis
---
# plan-generator v1.0.0

Standalone skill from digital-verify-pro.

## Quick Start
```bash
cd standalone-skills/plan-generator
python run.py --help
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--vcd <file>` | CLI arg | no | VCD file for toggle analysis |
| `--clk <name>` | CLI arg | no | Clock signal name |
| `--fsm <signal>` | CLI arg | no | FSM state register signal |
| `--output <dir>` | CLI arg | no | Output directory |

## Outputs

| Output | Description |
|--------|-------------|
| `verification-plan.md` | Full verification plan with coverage goals |
| `test-scenarios.yml` | Differentiated test scenarios |

## Capabilities

### 1. Deep RTL Analysis
- FSM extraction and state encoding detection
- Data path analysis (widths, pipeline stages)
- Control logic complexity scoring (1-10)

### 2. Differentiated Test Generation
- Design-topology-aware test scenarios
- Not template-based (no 'one test per port')
- Complexity-driven priority assignment

### 3. Coverage Closure Plan
- Toggle coverage gap analysis from VCD
- Functional coverage goal planning
- Cross-coverage scenario recommendations

## Dependencies

- **Python**: >= 3.10
- **Runtime**: Pure Python standard library (optional: vcd parsing)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic RTL analysis + 5 scenarios |
| standard | FSM extraction + 10 scenarios |
| intensive | Full analysis + 20 scenarios + coverage plan |
| exhaustive | All + stress scenarios + FSM coverage |

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic signal extraction + smoke test plan |
| standard | Full RTL analysis + FSM extraction + test scenarios |
| intensive | Comprehensive analysis + cross coverage |
| exhaustive | Deep analysis + corner cases + multi-output formats |

## Upstream

- RTL source files
- VCD simulation dump

## Downstream

- test-generator (scenarios)
- coverage-engine (coverage)
