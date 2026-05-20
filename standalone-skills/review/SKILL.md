---
name: review
version: 2.0.0
quality_score: 77.4
description: >
  Cross-model RTL review engine. Scans SystemVerilog for connectivity bugs,
  unconnected ports, multiple-driver conflicts, FIFO read-enable issues,
  interrupt signal completeness, and coverage-sensitive design patterns.
  Supports local pattern-based checks and multi-LLM consensus review.
---

# review v2.0.0 — RTL Code Review with Coverage-Aware Checks

**Reviewer Engine** — Catches RTL bugs before simulation, targets coverage gaps.

## Quick Start

```bash
cd standalone-skills/review
python run.py --dir output_i2c/rtl/rtl/ --output review_report.md
python run.py --dir output/rtl/verification/ --reviewers reviewers.yml
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--dir` | 目录 | 是 | CLI 参数 | RTL 源码目录，扫描其中 .sv/.v/.vhd 文件 |
| `--output` | 路径 | 否 | CLI 参数 | 输出审查报告路径，默认 `review_report.md` |
| `--json` | 标志 | 否 | CLI 参数 | 同时输出 JSON 格式的结构化审查结果 |
| `--rules` | YAML 文件 | 否 | CLI 参数 | 自定义审查规则配置，覆盖默认规则集 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `review_report.md` | Markdown | 结构化审查结果：每个发现的严重性等级、代码位置、修复建议 |
| `review_report.json` | JSON | 机器可读的审查发现：规则名、行号、严重性、修复指引 |
## Capabilities

### 1. Critical — Connectivity / Data Path

| Rule | Detection | Example Bug |
|------|-----------|-------------|
| **PORT_UNCONNECTED** | Module instantiation ports with unconnected signals | `u_rx_fifo (.rd_en(1'b0), .rdata(), .empty())` → RX FIFO never read |
| **DUAL_ASSIGN_OVERRIDE** | Same signal driven by multiple `assign` statements | `rx_data_reg_q` assigned twice (hw path overrides FSM path) |
| **HW_PORT_ZOMBIE** | Module has `hw_*` input ports that are never connected at top level | `hw_rx_data_i, hw_busy_i, hw_tx_intr_i` unconnected in `i2c.sv` → overrides FSM data |
| **FIFO_RD_STUCK** | FIFO `rd_en` hardwired to 0 | RX FIFO receives data but SW never reads it out |

### 2. High — Interrupt / Status Path

| Rule | Detection | Example Bug |
|------|-----------|-------------|
| **INTR_MULTI_SOURCE** | Interrupt output driven from multiple combinatorial paths | `intr_o` ORs multiple conditions without debounce |
| **W1C_MISSING** | Interrupt status register is a wire (not flop) → W1C has no effect | `intr_status_reg_q` is `wire`, writing 0xFFFFFFFF doesn't clear bits |
| **STATUS_OVERRIDE** | Status bits driven by both FSM path and hw_* path (last wins) | `status_reg_q[0] = hw_busy_i` overrides `busy_i2c` |

### 3. Medium — Coverage-Sensitive Patterns

| Rule | Detection | Impact |
|------|-----------|--------|
| **NO_TOGGLE_GAP** | Signal written but never read back | Toggle coverage gap, signal is dead |
| **ASYNC_ASSIGN** | Always_comb reading flip-flop outputs (could cause sim/synth mismatch) | Simulation coverage mismatch with silicon |
| **NBA_ORDER** | next-state and action in wrong always_ff order | FSM coverage never reaches certain states |

## Review Workflow (Coverage-Closure)

```
1. Run simulation → generate VCD
2. Coverage engine → gap analysis → gaps.json
3. Review engine (--dir rtl/) → review_report.md
   ├─ Checks each RTL file for known bug patterns
   ├─ Cross-references against coverage gaps
   └─ Flags signals that should toggle but can't due to RTL bug
4. Fix RTL bugs found by review
5. Re-run simulation → verify coverage improvement
```

## Example Findings

```
[RTL REVIEW] i2c_regs.sv
────────────────────────────────────────
🔴 CRIT PORT_UNCONNECTED at i2c_regs.sv:3
  Signal 'hw_rx_data_i[7:0]' is module INPUT that is:
  - Declared in port list
  - Used in 'assign rx_data_reg_q[7:0] = hw_rx_data_i;'
  - But NEVER CONNECTED at top-level i2c.sv
  → rx_data_reg reads 0x00 regardless of actual I2C RX data
  Fix: Remove hw_* override, use direct FSM connection rx_data_i2c

🔴 CRIT FIFO_RD_STUCK at i2c.sv:85
  simple_fifo u_rx_fifo (.rd_en(1'b0), .rdata(), .empty())
  → rd_en hardwired to 0: RX FIFO fills but never empties
  → rdata unconnected: even if read, data goes nowhere
  Fix: Connect rd_en to APB rx_data_reg read strobe

🟡 HIGH W1C_MISSING at i2c_regs.sv:40
  'intr_status_reg_q' is a wire (combinatorial assign)
  → Writing 0xFFFFFFFF to intr_status has NO EFFECT
  → Bits can't be W1C cleared
  Fix: Make intr_status_reg a flop with W1C logic
```

## Validation

| **Example** | **Findings** | **Status** |
|------------|:----------:|:----------:|
| I2C RTL review | PORT_UNCONNECTED, FIFO_RD_STUCK | ✅ Verified |
| OT DMA review | Coverage gap cross-reference | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: Pure Python standard library
- **OS**: Windows / Linux / macOS
- **External** (optional): GPT-4o / Claude / Kimi for LLM-based consensus review
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Review scope |
|--------|-------------|
| lite | Syntax + basic style checks |
| standard | Connectivity + port analysis |
| intensive | Coverage-aware + signal path tracing |
| exhaustive | Full multi-LLM consensus + formal property audit |

## Upstream

- RTL source files (from rtl-gen or hand-written)
- Coverage gap data (from coverage-engine)

## Downstream

- Coverage convergence loop (re-run simulation after fixes)
- Sign-off documentation (from doc-gen)
