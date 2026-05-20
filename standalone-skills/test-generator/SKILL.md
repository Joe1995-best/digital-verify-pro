---
name: test-generator
version: 2.0.0
quality_score: 80.4
description: >
  Generate UVM test sequences from verification scenarios. Protocol-aware,
  category-dispatched test sequence generator with coverage gap injection.
  Supports register, protocol, stress, FIFO, and interrupt sequence categories.
---

# test-generator v2.0.0

**Verifier Agent** — UVM test sequence generation.

## Quick Start

```bash
cd standalone-skills/test-generator
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --gaps coverage_gaps.json
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 / spec-analyzer 输出 | IP 规格描述，含测试场景定义和接口列表 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--gaps` | JSON 文件 | 否 | coverage-engine 输出 | 覆盖率缺口 JSON，用于生成靶向补充测试序列 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `rtl/verification/env/sequences/{module}_base_seq.sv` | SystemVerilog | UVM 基础序列类：寄存器初始化和公共方法 |
| `rtl/verification/env/sequences/{module}_reg_seq.sv` | SystemVerilog | 寄存器序列：RMW、bit-bash、保留位检查、原子操作 |
| `rtl/verification/env/sequences/{module}_protocol_seq.sv` | SystemVerilog | 协议序列：I2C 写/读、SPI 模式切换、APB 传输 |
| `rtl/verification/env/sequences/{module}_stress_seq.sv` | SystemVerilog | 压力序列：背靠背传输、随机延迟、最大吞吐量 |
| `rtl/verification/env/sequences/{module}_fifo_seq.sv` | SystemVerilog | FIFO 序列：填充/排空、溢出、水印越界 |
| `rtl/verification/env/sequences/{module}_intr_seq.sv` | SystemVerilog | 中断序列：断言/清除、嵌套中断、屏蔽中断 |
| `rtl/verification/env/sequences/{module}_gap_seq.sv` | SystemVerilog | 覆盖缺口补充序列：来自 coverage-engine 缺口分析结果 |
## Capabilities

### 1. Category-Based Sequence Generation
- Register: field-level RMW, bit-bash, reserved-bit, atomic operations
- Protocol: bus transactions per protocol (I2C, SPI, etc.)
- Stress: back-to-back, random delays, max throughput
- FIFO: fill/drain, overflow, watermark crossing
- Interrupt: assert/clear, nested, masked

### 2. Coverage Gap Injection
- Reads coverage gaps JSON from coverage-engine
- Generates targeted sequences to close specific coverage holes
- Self-checking assertions and coverage sampling built-in

### 3. Rich Register Sequences
- Field-level read-modify-write
- Bit-bash for all writable fields
- Reserved bits stability checking
- Atomic read-modify-write operations

## Validation

| **Example** | **Sequences** | **Status** |
|------------|:-----------:|:----------:|
| I2C | 13 base + 90 scenario sequences | ✅ Verified |
| OT DMA | 22 UVM sequences | ✅ Verified |
| PCIe EP | 12 protocol sequences | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`, `jinja2`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Level | Sequences | Coverage per test |
|-------|-----------|-------------------|
| lite | 3-5 basic | Functional only |
| standard | 8-12 | Functional + protocol |
| intensive | 15-25 | Full scenario matrix |
| exhaustive | 30+ | All scenarios + gaps |

## Upstream

- `spec-analyzer` — consumes test scenarios + interface list
- `env-builder` — consumes env structure for sequence reuse
- `coverage-engine` — optionally consumes coverage gaps

## Downstream

- `sim-runner` — consumes test sequences for simulation execution
- `tb-compiler` — consumes sequences for compilation
