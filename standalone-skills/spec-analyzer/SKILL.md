---
name: spec-analyzer
version: 2.0.0
quality_score: 79.9
description: >
  Parse spec YAML into a full verification plan. Identifies protocols, interfaces,
  registers, FSM configurations, and generates test scenarios with functional
  coverage goals. Protocol-aware: I2C, APB, SPI, UART, DMA recognition.
---

# spec-analyzer v2.0.0

**Verification Plan Generator** — From spec YAML to structured verification plan.

## Quick Start

```bash
cd standalone-skills/spec-analyzer
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述，含接口定义、寄存器映射、时序要求和 FSM 配置 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--effort` | 字符串 | 否 | CLI 参数 | 分析深度：`lite`/`standard`/`intensive`/`exhaustive`，默认 `standard` |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `verification-plan.md` | Markdown | 完整验证计划：自动识别的协议列表、接口信号表、场景描述及通过标准 |
| `interface-list.yml` | YAML | 接口定义清单：协议类型、信号方向、位宽、时钟域 |
| `register-map.yml` | YAML | 寄存器映射表：地址、域定义、访问类型、复位值、硬件可达性 |
| `test-scenarios.yml` | YAML | 测试场景列表：协议感知场景生成 (I2C/APB/SPI)、寄存器场景、stress场景 |
## Capabilities

### 1. Interface Detection
- APB / AHB / AXI / AXI-Stream / AXI-Lite
- I2C / SPI / UART / I2S / JTAG
- Custom interfaces (user-defined)
- Protocol version detection

### 2. Register Analysis
- Extract address map from spec
- Detect field types (RW/RO/WO/W1C/RW1C)
- Flag reserved spaces and address holes
- Generate IP-XACT from YAML, or vice versa

### 3. Protocol-Aware Scenario Generation (v2)
- I2C: write/read/RSTART/10bit addr/NACK/arbitration/clock stretch
- APB: single/sequential/error/back-to-back
- SPI: mode-0/1/2/3, single/dual/quad

### 4. Coverage Planning
- Functional cover points per feature
- Cross coverage between interfaces
- Protocol-specific coverage bins
- Register coverage (all addressable locations)

### 5. FSM Analysis (v2)
- FSM state extraction from spec
- Transition coverage goals
- State encoding detection

## Validation

| **Example** | **Scenarios** | **Protocols** | **Status** |
|------------|:-----------:|:-----------:|:----------:|
| I2C | 90 scenarios (11 user + 79 auto) | I2C, APB | ✅ Verified |
| OT DMA | 66 scenarios (9 user + 57 auto) | DMA, APB | ✅ Verified |
| PCIe EP | 12 scenarios | PCIe, APB, INTR | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml` (for YAML parsing)
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Scenarios | Coverage detail |
|--------|-----------|-----------------|
| lite | 3-5 basic tests | Functional only |
| standard | 8-12 tests | Functional + protocol |
| intensive | 15-25 tests | Full scenario matrix |
| exhaustive | 30+ tests | All scenarios + cross coverage + bugs |

## Upstream

Design specification (YAML)

## Downstream

- `env-builder` — consumes interface list + register map
- `test-generator` — consumes test scenarios
- `coverage-plan` — consumes coverage goals
