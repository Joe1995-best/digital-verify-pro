---
name: fault-injector
version: 2.0.0
lifecycle: stable
---

# fault-injector v2.0.0

**Production-ready fault injection engine** — generates JSON plans, pure-SystemVerilog task libraries, parameterised wrapper modules, and UVM sequences. No DPI/PLI required; works with iverilog.

## Supported Fault Modes

| Mode | SV Task | Description |
|------|---------|-------------|
| bus_hang | fi_bus_hang | Force bus select low to create timeout |
| reset_glitch | fi_reset_glitch | Illegal posedge on active-low reset |
| seu | fi_seu | Single-event upset: flip one register bit |
| clk_stall | fi_clk_stall | Pause clock for N cycles |
| data_corrupt | fi_data_corrupt | Invert random bits on data bus |
| protocol_viol | fi_protocol_viol | Violate interface timing rule |
| stuck_at | fi_stuck_at | Force signal stuck-at-0/1 |
| glitch | fi_glitch | Transient pulse on combinational output |

## Usage (CLI)

```bash
# Generate everything (JSON + SV tasks + wrapper + UVM seq)
python engines/fault_injector.py --spec i2c_spec.yml --out ./fi/

# Generate only SV artefacts (no JSON plan)
python engines/fault_injector.py --rtl rtl/i2c.sv --mode seu,reset_glitch --sv-only --out ./fi/

# List all modes
python engines/fault_injector.py --list-modes
```

## Usage (API)

```python
from engines.fault_injector import FaultInjector, FaultMode

fi = FaultInjector(spec_path="i2c_spec.yml")
fi.set_modes([FaultMode.SEU, FaultMode.RESET_GLITCH])
paths = fi.generate_all(output_dir="./fi/", seed=42, iterations=20)

# paths = {
#   "plan":       "./fi/fault_injection_plan.json",
#   "sv_tasks":   "./fi/fault_injector_tasks.sv",
#   "sv_wrapper": "./fi/fault_injector.sv",
#   "uvm_seq":    "./fi/fault_injector_seq.sv",
# }
```

## Generated Artefacts

### 1. fault_injection_plan.json
Regression meta-data — seed, iterations, per-injection parameters. Human-readable and machine-parseable.

### 2. fault_injector_tasks.sv
Pure SystemVerilog `package fault_injector_tasks` with 8 tasks:
- Deterministic LCG PRNG (`fi_urandom_range`) — no `$urandom` dependency
- `force`/`release` based — supported by iverilog
- Seed configurable via plusarg: `+FI_SEED=123`

### 3. fault_injector.sv
Parameterised wrapper module:
```systemverilog
fault_injector #(
  .FAULT_MODE("seu"),
  .TRIGGER_CYCLE(100),
  .DURATION_NS(50)
) fi (.clk(clk), .rst_n(rst_n), .target(ctrl_reg_q), .target_out(ctrl_fi));
```

### 4. fault_injector_seq.sv
UVM sequence with randomised trigger delay and mode selection.

## Integration with Regression

```bash
# Step 1: generate fault injection wrapper
python engines/fault_injector.py --spec i2c_spec.yml --out output/fi/

# Step 2: compile with iverilog
iverilog -g2012 -s tb_top \
  output/rtl/rtl/i2c.sv \
  output/fi/fault_injector.sv \
  output/fi/fault_injector_tasks.sv \
  tb/tb_top.sv

# Step 3: run with seed override
vvp a.out +FI_SEED=123
```

## Dependencies

- **Python**: >= 3.10
- **Simulator**: iverilog >= 11 (or any SV simulator supporting `force`/`release`)
- **UVM** (optional): only needed if using `fault_injector_seq.sv`

## Changelog

### v2.0.0 (2026-05-21)
- Complete rewrite: 8 fault modes (was 3)
- Added pure-SystemVerilog task library (no DPI/PLI)
- Added parameterised wrapper module
- Added UVM sequence
- Added CLI with `--list-modes`, `--sv-only`, `--plan-only`
- Deterministic LCG PRNG for reproducibility
- Plusarg seed override: `+FI_SEED=N`

### v1.0.0
- JSON plan generation only (stub)
