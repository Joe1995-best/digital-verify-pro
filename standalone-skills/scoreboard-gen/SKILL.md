---
name: scoreboard-gen
version: 2.0.0
description: >
  UVM scoreboard and checker generator (v2). Generates full UVM scoreboard
  with TLM analysis ports, predictor, comparator, coverage collection,
  and end-to-end data integrity verification.
---

# scoreboard-gen v2.0.0

**UVM Scoreboard Generator** — From spec to complete, compilable scoreboard.

## Quick Start

```bash
cd standalone-skills/scoreboard-gen
python run.py --spec ../../i2c_spec.yml --out output
```

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `--spec <file>` | CLI arg | yes |
| `--out <dir>` | CLI arg | no |

## Outputs

| File | Description |
|------|-------------|
| `sb.sv` | Main scoreboard: TLM analysis ports, packet queue, comparison loop |
| `sb_predictor.sv` | Predictor: generates expected transactions from monitored activity |
| `sb_coverage.sv` | Coverage collector: functional coverage for all transactions |

## Capabilities

### 1. Full UVM Scoreboard
- TLM analysis exports (mon_a_export, mon_b_export)
- Transaction queue with expected/actual matching
- Out-of-order transaction support
- Timeout detection for lost transactions

### 2. Programmable Predictor
- Register-model-aware prediction
- Supports pipelined transactions
- Configurable latency model

### 3. Coverage Collection
- Per-transaction-type covergroups
- Data value coverage (bins for each byte lane)
- Protocol-specific cross coverage
