---
name: waveform-analyzer
version: 1.0.0
quality_score: 77.4
lifecycle: development
description: >
  Analyze simulation results, extract coverage metrics, and identify failures
  from waveform dumps and log files. Post-simulation analysis for verification
  closure assessment.
---

# waveform-analyzer v1.0.0

**Runner Agent Phase 3** — Post-simulation analysis.

## Quick Start

```bash
cd standalone-skills/waveform-analyzer
python run.py --log sim_results/sim.log
python run.py --vcd output.vcd --report coverage_report.json
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--log` | 日志文件 | 否 | sim-runner 输出 | UVM 仿真日志，用于提取错误信息和覆盖度数据 |
| `--vcd` | VCD 文件 | 否 | sim-runner 输出 | 波形文件，用于信号分析 |
| `--report` | 路径 | 否 | CLI 参数 | 输出报告路径，默认覆盖日志目录 |
| `--top` | 字符串 | 否 | CLI 参数 | 顶层模块名，用于范围过滤 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `failure_report.json` | JSON | 失败分析报告：UVM_ERROR/FATAL 提取、断言失败层次路径、严重性排名 |
| `coverage_report.json` | JSON | 覆盖度量数据：功能覆盖百分比、toggle 统计、覆盖缺口识别 |
| `coverage_report.md` | Markdown | 可读的覆盖度量摘要和失败概览 |
## Capabilities

### 1. Log File Analysis
- Extract UVM_ERROR/UVM_FATAL messages with timestamps
- Count pass/fail per test
- Summarize covergroup coverage percentage
- Identify simulation runtime warnings

### 2. Waveform Analysis
- VCD file parsing and signal dump analysis
- Signal toggle counting for coverage
- Protocol timing violation detection
- Bus transaction extraction and validation

### 3. Coverage Metrics Extraction
- Functional coverage percentage from logs
- Toggle coverage from VCD
- Coverage gap identification
- Coverage closure assessment

### 4. Failure Classification
- Timeout detection
- Assertion failures with hierarchy paths
- Protocol violation classification
- Severity-based failure ranking

## Validation

| **Example** | **Signals** | **Status** |
|------------|:---------:|:----------:|
| I2C | 37 signals analyzed | ✅ Verified |
| OT DMA | 117 signals, 89.8% toggle | ✅ Verified |

## Effort

| Effort | Analysis depth |
|--------|----------------|
| lite | Log pass/fail extraction only |
| standard | Log analysis + VCD toggle count |
| intensive | Full coverage extraction + gap detection |
| exhaustive | Failure classification + trend analysis |



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
- **Runtime**: `pyyaml` (optional, for structured reports)
- **OS**: Windows / Linux / macOS
- **Optional**: PyVCD or VCD parsing library for waveform analysis
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Upstream

- `sim-runner` — consumes simulation logs and waveform dumps

## Downstream

- `doc-gen` — consumed for verification close documentation
- `coverage-plan` — coverage gap feedback for targeted generation
