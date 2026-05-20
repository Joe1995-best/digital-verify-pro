---
name: assertion-gen
version: 1.0.0
quality_score: 78.9
lifecycle: beta
description: >
  Generate SystemVerilog Assertions (SVA) from specification. Covers interface
  protocols, internal invariants, register access rules, and timing requirements.
  Protocol-agnostic — handles any interface type defined in spec YAML.
---

# assertion-gen v1.0.0

**Verifier Agent** — SVA assertion generation.

## Quick Start

```bash
cd standalone-skills/assertion-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述文件，包含接口定义、寄存器映射、时序要求 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--format` | 字符串 | 否 | CLI 参数 | 断言格式：`sv` (SystemVerilog) 或 `sva` (纯SVA模块)，默认 `sv` |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `rtl/verification/env/assertions/apb_assert.sv` | SystemVerilog | APB 协议时序断言：地址/数据/控制信号握手检查 |
| `rtl/verification/env/assertions/reset_assert.sv` | SystemVerilog | 复位行为断言：异步/同步复位释放、复位状态保持 |
| `rtl/verification/env/assertions/reg_assert.sv` | SystemVerilog | 寄存器访问规则断言：RW/RO 权限检查、地址越界检测 |
| `rtl/verification/env/assertions/clk_assert.sv` | SystemVerilog | 时钟域断言：时钟门控、时钟频率、时钟抖动检查 |
## Capabilities

### 1. Interface Protocol Assertions
- APB read/write protocol timing checks
- Handshake sequence verification
- Address/data phase separation

### 2. Reset Assertions
- Active-low/active-high reset timing
- Async/sync reset assertion/deassertion
- Reset state entry/exit conditions

### 3. Register Assertions
- Read-only vs writable field verification
- Reserved bit stability assertions
- Address decode bounds checking

### 4. Post-Generation Validation
- Structural integrity checks on generated SV files
- Assertion count verification
- Syntax-level consistency validation

## Validation

| **Example** | **Assertions** | **Status** |
|------------|:------------:|:----------:|
| I2C | apb_assert + reset_assert + reg_assert | ✅ Verified |
| SPI Slave | Full protocol assertions | ✅ Verified |
| OT DMA | Register + FSM assertions | ✅ Verified |



## Config

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `timeout_seconds` | int | 300 | 执行超时（秒） |
| `log_level` | enum | `info` | 日志级别：debug/info/warn/error |
| `out_dir` | string | `output/` | 输出目录 |



## Known Limitations

- 依赖上游 skill 的输出格式，版本变更可能破坏兼容性
- 当前为 standalone 模式，未深度集成 pipeline 上下文
- 大文件处理可能受 Python 单线程性能限制

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Level | Assertions | Coverage |
|-------|------------|----------|
| lite | Core APB + reset | Basic protocol compliance |
| standard | APB + reset + register | Full interface compliance |
| intensive | All + protocol-specific | Comprehensive assertions |
| exhaustive | Full + custom properties | Sign-off ready |

## Upstream

- `spec-analyzer` — consumes interface list + register map
- Design specification (YAML)

## Downstream

- `tb-compiler` — consumes assertions for compilation
- `sim-runner` — assertions active during simulation
- `formal-check` — assertions reusable for formal verification
