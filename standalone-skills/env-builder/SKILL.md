---
name: env-builder
version: 1.0.0
quality_score: 80.9
lifecycle: beta
description: >
  Generate UVM verification environment skeleton from specification. Builds tb_top,
  interface wrappers, UVM agent/monitor/sequencer, environment, and testbench harness.
  Protocol-agnostic: handles I2C, GPIO, SPI, UART, AXI, PCIe identically.
---

# env-builder v1.0.0

**Verification Architect Phase 2** — UVM environment generation.

## Quick Start

```bash
cd standalone-skills/env-builder
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 / spec-analyzer 输出 | IP 规格描述，含接口定义和寄存器映射 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--module` | 字符串 | 否 | CLI 参数 | 模块名覆盖（从 spec 自动提取失败时使用） |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `rtl/verification/env/tb_top.sv` | SystemVerilog | 顶层 testbench harness：时钟/复位生成、DUT 例化、接口连接 |
| `rtl/verification/env/env_pkg.sv` | SystemVerilog | UVM 包文件：包含所有 env 组件的 include 声明 |
| `rtl/verification/env/{module}_env.sv` | SystemVerilog | UVM environment 类：agent/scoreboard/coverage 的容器 |
| `rtl/verification/env/{module}_agent.sv` | SystemVerilog | UVM agent：driver + monitor + sequencer 的封装 |
| `rtl/verification/env/{module}_driver.sv` | SystemVerilog | 协议 driver：事务级驱动、时序控制 |
| `rtl/verification/env/{module}_monitor.sv` | SystemVerilog | 协议 monitor：总线监听、事务提取 |
| `rtl/verification/env/{module}_sequencer.sv` | SystemVerilog | UVM sequencer：测试序列调度 |
| `rtl/verification/env/{module}_if.sv` | SystemVerilog | SystemVerilog interface：信号声明、modport、时钟块 |
| `rtl/verification/env/sim/Makefile` | Makefile | 仿真编译脚本，支持 iverilog/VCS/Questa |
## Capabilities

### 1. UVM Skeleton Generation
- Generate complete UVM environment: agent, driver, monitor, sequencer
- Interface wrappers per protocol type
- Testbench harness with clock/reset generation

### 2. Protocol-Agnostic Architecture
- No protocol-specific code paths in templates
- All protocols handled identically through template iteration
- Supports: I2C, GPIO, SPI, UART, AXI, PCIe, and custom

### 3. Simulation Ready
- Generate compilable SystemVerilog immediately
- UVM 1.2 / 1800.2 compatible
- Makefile generation for common simulators

### 4. Validation
- Post-generation structural validation
- Checks for required component presence
- Interface signal consistency verification

## Validation

| **Example** | **Files** | **Status** |
|------------|:--------:|:----------:|
| I2C | 9 SV files (tb_top, env, agent, if, pkg) | ✅ Verified |
| GPIO PL061 | Full env with BFM | ✅ Verified |
| PCIe EP | 64 SV files, 0 template warnings | ✅ Verified |



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
- **Runtime**: `pyyaml`, `jinja2`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Level | Agents | Interfaces |
|-------|--------|------------|
| lite | 1 agent, minimal | 1 interface |
| standard | All agents | All interfaces |
| intensive | Agents + scoreboard hooks | Full interface matrix |
| exhaustive | Full UVM environment | Complete verification env |

## Upstream

- `spec-analyzer` — consumes interface list + register map
- Design specification (YAML)

## Downstream

- `test-generator` — consumes env structure for sequence generation
- `tb-compiler` — consumes env for compilation
- `assertion-gen` — consumes interface definitions
