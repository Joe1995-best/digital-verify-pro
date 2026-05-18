# AGENTS.md — AI Agent Guide for digital-verify-pro

Start here for any new session involving digital verification.

## Quick Orientation

```
digital-verify-pro/
├── pro_verify.py           ← Main orchestrator (Track 1 RTL + Track 2 Pipeline)
├── pipeline/               ← 10 pipeline phase scripts
│   ├── run_*.py            ← Individual phase runners
│   ├── templates/          ← Jinja2 SV templates (protocol-agnostic)
│   └── template_engine.py  ← Template renderer
├── engines/                ← Track 1 verification engines
├── templates/              ← UVM code templates
├── effort/                 ← Verification effort levels
├── references/             ← Testbench patterns
├── quickstart/             ← Quick start guide
├── wiki/                   ← Knowledge base (patterns/protocols/lessons)
├── uvm/                    ← UVM stubs for iverilog
└── config/                 ← Shared configuration
```

## Workflow

### Track 2 (Spec-driven Pipeline) — Main Path

```bash
# 1. Write YAML spec → 2. Run pipeline → 3. Simulate → 4. Verify
python pro_verify.py --pipeline my_spec.yml
python run_sim.py --spec my_spec.yml -o ./output --check-only
python run_csr_test_gen.py --spec my_spec.yml -o ./output
python run_sim.py --spec my_spec.yml -o ./output --gen-tb
```

### Track 1 (RTL Verification) — Quick Path

```bash
python pro_verify.py <rtl_file>.v --spec "description"
```

## Key Files

| File | Purpose |
|------|---------|
| `pro_verify.py` | Multi-agent orchestrator — see `--help` |
| `pipeline/run_*.py` | Phase agents: spec-analyzer, rtl-gen, env-builder... |
| `pipeline/templates/*.tpl` | Protocol-agnostic Jinja2 SV templates |
| `pipeline/run_sim.py` | Simulation engine: check-only / gen-tb / gen-eda |
| `pipeline/run_csr_test_gen.py` | CSR auto-verification (reset + RW) |
| `pipeline/questa_vcs_support.py` | EDA compile/simulation script generator |
| `PRO_SKILL.md` | Full skill definition with methodology |

## Examples

Three complete protocol examples ready to run:

```bash
python pro_verify.py --pipeline i2c_spec.yml       # I2C Controller
python pro_verify.py --pipeline arm_pl061_gpio.yml   # ARM GPIO PL061
python pro_verify.py --pipeline pcie_ep_spec.yml     # PCIe EP
python pro_verify.py --pipeline ot_dma_spec.yml      # OpenTitan DMA
```

## Known Constraints

- **iverilog 11.0**: No `0x` hex literals (use `12'hXX`), no multi-arg task >1 call
- **UVM full sim**: Requires Questa/VCS (not iverilog compatible)
- **RTL gen bug**: `get_reg_reset()` computes per-field reset values; spec-level reset must be consistent
