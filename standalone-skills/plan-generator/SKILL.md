---
name: plan-generator
version: 2.0.0
quality_score: 76.9
description: >
  Verification plan generator from RTL source analysis. Deep RTL analysis with
  FSM extraction, state encoding detection, data path analysis, control complexity
  scoring, and differentiated test generation. Produces complete verification plan
  with coverage goals and topology-aware test scenarios.
---

# plan-generator v2.0.0

**Verification Plan Generator** — Deep RTL analysis + differentiated test generation.

从 RTL 源码出发，自动提取设计结构、生成差异化验证计划和测试场景。

## Quick Start

```bash
cd standalone-skills/plan-generator
python run.py --vcd dump.vcd --clk clk_i --fsm state_q --output plan_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--vcd` | VCD 文件 | 否 | 仿真工具 | VCD 波形文件，用于 toggle 覆盖度分析和覆盖缺口检测 |
| `--clk` | 字符串 | 否 | CLI 参数 | 时钟信号名称，用于时序分析 |
| `--fsm` | 字符串 | 否 | CLI 参数 | FSM 状态寄存器信号名，用于 FSM 自动提取 |
| `--output` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--rtl-dir` | 目录 | 否 | CLI 参数 | RTL 源码目录，用于静态代码分析 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `verification-plan.md` | Markdown | 完整验证计划：设计复杂度评分、FSM 分析结果、数据通路拓扑、差异化测试场景列表 |
| `test-scenarios.yml` | YAML | 差异化测试场景定义：基于设计拓扑而非模板化 "每端口一测试" 的智能生成 |
## Capabilities

### 1. Deep RTL Analysis
- **FSM Extraction**: Auto-detect FSM state registers, extract state encoding, identify one-hot/binary/gray encoding
- **Data Path Analysis**: Analyze signal widths, pipeline stages, datapath connectivity
- **Control Logic Complexity**: Score designs 1-10 based on FSM size, branching depth, interface count
- **Protocol Interface Recognition**: Auto-identify APB, AXI, I2C, SPI protocol types

### 2. Differentiated Test Generation
- Design-topology-aware test scenarios (not template-based "one test per port")
- Complexity-driven priority assignment (high-complexity modules get more scenarios)
- Scenario count scales with design complexity score

### 3. Coverage Closure Plan
- Toggle coverage gap analysis from VCD
- Functional coverage goal planning based on design structure
- Cross-coverage scenario recommendations

## Validation

| Example | Tests | Status |
|---------|:-----:|:------:|
| ALU4 (4-bit) | 66 scenarios | ✅ Verified |
| Dual Port Stack | FSM extraction + formal | ✅ Verified |
| OT DMA | 22 scenarios, 89.8% toggle | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: Pure Python standard library (optional: VCD file for toggle analysis)
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic RTL analysis + 5 scenarios |
| standard | FSM extraction + 10 scenarios |
| intensive | Full analysis + 20 scenarios + coverage plan |
| exhaustive | All + stress scenarios + FSM coverage + cross coverage |

## Upstream

- RTL source files (Verilog/SystemVerilog)
- VCD simulation dump (optional, for toggle analysis)

## Downstream

- `test-generator` — consumes test scenarios for UVM sequence generation
- `coverage-engine` — consumes coverage goals for gap analysis
