---
name: formal-check
version: 1.0.0
description: >
  Formal property verification engine. Reads spec YAML, generates SVA assertions
  for registers, FSM, and interfaces, produces SymbiYosys .sby config, optionally
  runs sby, and writes formal_report.md summary.
---

# formal-check v1.0.0

**Formal Verification Agent** — Generate and run formal properties.

## Quick Start

```bash
cd standalone-skills/formal-check
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../spi_slave_spec.yml --no-run
```

## Inputs

| Input | Source | Required | Description |
|-------|--------|----------|-------------|
| `--spec <file>` | CLI arg | yes | Path to spec YAML file |
| `--out <dir>` | CLI arg | no | Output directory (default: output/) |
| `--no-run` | CLI flag | no | Skip SymbiYosys execution (generate only) |

## Outputs

| Output | Description |
|--------|-------------|
| SVA `assert_*.sv` files | Generated SystemVerilog assertions for registers, FSM, interfaces |
| `.sby` config | SymbiYosys configuration for formal tools |
| `formal_report.md` | Formal verification summary report |

## Capabilities

### 1. Register Property Generation
- Generate SVA assertions for register read/write behavior
- Assert field-level access permissions (RW, RO, WO, W1C, RW1C)
- Generate assume properties for valid address ranges
- Check reserved bit stability

### 2. FSM Property Generation
- State reachability assertions
- Transition legality checks
- One-hot encoding verification
- Deadlock/livelock detection properties

### 3. Interface Protocol Properties
- Protocol timing assertions (setup/hold, handshake sequences)
- Data integrity covers across bus transactions
- Arbitration fairness guarantees

### 4. SymbiYosys Integration
- Generate complete .sby configuration files
- Specify clock/reset assumptions
- Configure BMC depth and k-induction parameters
- Optional sby execution with result parsing

### 5. Formal Report Generation
- Pass/fail summary per property category
- Coverage metrics (proven properties vs bounded)
- Warning for unreachable cover statements

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`, `jinja2`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`, `lib/formal_check_gen.py`
- **Optional**: SymbiYosys (sby) for formal execution
- **OS**: Windows / Linux / macOS

## Effort

| Level | Properties | Coverage |
|-------|-----------|----------|
| lite | Core register assertions | Basic address checking |
| standard | Registers + FSM properties | State reachability |
| intensive | Full property suite | Exhaustive formal coverage |
| exhaustive | All properties + custom | Full formal sign-off |

## Upstream

Design specification (YAML)

## Downstream

- `coverage-plan` — consumes formal coverage results
- `doc-gen` — includes formal report in verification close document
