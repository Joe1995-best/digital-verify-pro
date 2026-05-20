---
name: tb-compiler
version: 1.0.0
quality_score: 76.4
lifecycle: development
description: >
  Compile verification environment with EDA tool. Handles UVM package compilation,
  DUT RTL compilation, testbench compilation, generates compile scripts and
  Makefile targets for Questa/ModelSim, VCS, and Xcelium simulators.
---

# tb-compiler v1.0.0

**Runner Agent Phase 1** — Compile testbench + DUT.

## Quick Start

```bash
cd standalone-skills/tb-compiler
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --tool questa
python run.py --spec ../../i2c_spec.yml --tool vcs
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述，用于定位 RTL 和 UVM env 目录 |
| `--outdir` | 目录 | 否 | CLI 参数 | 编译输出目录，默认 `output/` |
| `--tool` | 字符串 | 否 | CLI 参数 | 仿真器选择：`auto`/`iverilog`/`verilator`/`vcs`/`questa`，默认 `auto` |
| `--check-only` | 标志 | 否 | CLI 参数 | 仅做 RTL 语法检查（不需要 UVM 环境） |
| `--gen-tb` | 标志 | 否 | CLI 参数 | 生成简化 testbench + 编译（不需要 UVM 环境） |
| `--detect` | 标志 | 否 | CLI 参数 | 检测可用仿真器 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `compile.log` | 日志 | 编译日志：编译器版本、编译选项、错误/警告信息、耗时统计 |
| `simv` | 二进制 | 编译生成的仿真可执行文件（编译成功时产生），供 sim-runner 使用 |
| `compile.do` | TCL | Questa/ModelSim 编译脚本（`--tool questa` 时生成） |
| `Makefile` | Makefile | VCS/iverilog 编译后脚本（`--tool vcs` 或自动检测时生成） |
## Supported EDA Tools

| Tool | Script | Notes |
|------|--------|-------|
| Questa/ModelSim | `compile.do` | Full UVM 1.2/1800.2 support |
| VCS | `Makefile` + `.synopsys_dc.setup` | Full compile with UVM |
| Xcelium | `Makefile` + `cds.lib` | IUS/Xcelium support |

## Capabilities

### 1. UVM Package Compilation
- UVM 1.2 and IEEE 1800.2 support
- UVM library detection and path configuration
- Package compilation ordering

### 2. DUT RTL Compilation
- RTL source discovery and compilation
- Include path handling
- Macro definitions from spec

### 3. Testbench Compilation
- Full verification environment compilation
- Generated SV file compilation
- Scoreboard, coverage, assertions inclusion

### 4. Script Generation
- Simulator-specific compile scripts (Questa .do, VCS Makefile)
- Configurable compile options
- Automatic simulator detection

## Validation

| **Example** | **Tool** | **Status** |
|------------|:------:|:----------:|
| ALU4 | iverilog | ✅ Verified |
| OT DMA | iverilog | ✅ Verified |
| I2C | iverilog | ✅ Verified |



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
- **Runtime**: none (pure Python standard library)
- **Internal**: `lib/template_engine.py`, `lib/questa_vcs_support.py`
- **Optional**: Questa/ModelSim, VCS, or Xcelium installed
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | UVM package + DUT compile only |
| standard | Full testbench compile with scoreboard/coverage |
| intensive | Multi-library compile + optimization flags |
| exhaustive | All EDA tools with incremental compilation |

## Upstream

- `env-builder` — consumes generated verification environment
- `test-generator` — consumes generated test sequences
- Design RTL sources

## Downstream

- `sim-runner` — produces compiled simulation executable

