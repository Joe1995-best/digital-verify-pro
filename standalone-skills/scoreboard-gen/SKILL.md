---
name: scoreboard-gen
version: 2.0.0
quality_score: 79.4
lifecycle: beta
description: >
  UVM scoreboard and checker generator (v2). Generates full UVM scoreboard
  with TLM analysis ports, predictor, comparator, coverage collection,
  and end-to-end data integrity verification.
---

# scoreboard-gen v2.0.0

**UVM Scoreboard Generator** — From spec to complete, compilable scoreboard.

## Quick Start

```bash
cd standalone-skills/scoreboard-gen
python run.py --spec ../../i2c_spec.yml --out output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 / spec-analyzer 输出 | IP 规格描述，含接口列表和寄存器映射 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--width` | 整数 | 否 | CLI 参数 | 数据总线宽度，默认 `32` |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `rtl/verification/env/sb.sv` | SystemVerilog | UVM scoreboard 主体：TLM analysis export 接收事务、期望/实际队列比对、超时检测 |
| `rtl/verification/env/sb_predictor.sv` | SystemVerilog | 预测器：基于寄存器模型和流水线配置生成期望事务 |
| `rtl/verification/env/sb_coverage.sv` | SystemVerilog | 覆盖收集器：逐事务类型 covergroup、数据值 bin、协议特定交叉覆盖 |
## Capabilities

### 1. Full UVM Scoreboard
- TLM analysis exports (mon_a_export, mon_b_export)
- Transaction queue with expected/actual matching
- Out-of-order transaction support
- Timeout detection for lost transactions

### 2. Programmable Predictor
- Register-model-aware prediction
- Supports pipelined transactions
- Configurable latency model

### 3. Coverage Collection
- Per-transaction-type covergroups
- Data value coverage (bins for each byte lane)
- Protocol-specific cross coverage

## Validation

| Example | Generated | Status |
|---------|:---------:|:------:|
| I2C | sb.sv + sb_predictor.sv + sb_coverage.sv | ✅ Verified |
| OT DMA | Full scoreboard with TLM analysis exports | ✅ Verified |



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
- **Internal**: `lib/template_engine.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Scoreboard depth |
|--------|------------------|
| lite | Basic compare-only scoreboard |
| standard | Predictor + comparator |
| intensive | Full scoreboard + coverage collection |
| exhaustive | All features + out-of-order + timeout |

## Upstream

- `spec-analyzer` — consumes register map + interface list
- `env-builder` — consumes env structure for scoreboard integration

## Downstream

- `tb-compiler` — consumes scoreboard for compilation
- `sim-runner` — scoreboard active during simulation
- `coverage-engine` — scoreboard coverage data for gap analysis
