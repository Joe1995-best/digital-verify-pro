---
name: coverage-engine
version: 2.0.0
quality_score: 79.4
description: >
  VCD-based toggle coverage analysis engine. Pure Python VCD parser with
  full-signal per-bit toggle analysis, activity classification, coverage gap
  detection, severity ranking, and zero stuck-signal verification.
---

# coverage-engine v2.0.0

**Coverage Analysis Engine** — Pure Python, no EDA tool dependency.

一键分析 VCD 文件的 toggle 覆盖率，产出 JSON + Markdown 报告。

## Quick Start

```bash
cd standalone-skills/coverage-engine
python run.py --vcd ../../i2c.vcd --report coverage_report.json --markdown
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--vcd` | VCD 文件 | 是 | 仿真工具 | 来自 iverilog/VCS/Questa 的 Value Change Dump 波形文件 |
| `--report` | 路径 | 否 | CLI 参数 | 输出的 JSON 报告路径，默认 `coverage_report.json` |
| `--top` | 字符串 | 否 | CLI 参数 | 顶层模块名，用于范围过滤和层次化分析 |
| `--markdown` | 标志 | 否 | CLI 参数 | 同时生成 Markdown 格式的可读报告 |
| `--clk` | 字符串 | 否 | CLI 参数 | 时钟信号名，用于时钟域感知的 toggle 分析 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `<report>.json` | JSON | 每信号逐 bit toggle 统计、活跃度分级 (NONE/LOW/MEDIUM/HIGH/VERY_HIGH)、覆盖缺口检测报告 |
| `<report>.md` | Markdown | 人类可读的覆盖度摘要：总信号数、转率、缺口分类、严重性排序 |
## Capabilities

### 1. Pure Python VCD Parsing
- Zero third-party dependencies
- Full scope hierarchy (`$scope`/`$upscope` tracking for scoped signal names)
- Multi-bit value parsing (binary strings, hex, decimal)

### 2. Per-Signal Toggle Analysis
- Every signal in VCD, every bit position
- Transition count (not just binary 0/1 presence)
- Activity level classification:
  - `VERY_HIGH`: >100 transitions
  - `HIGH`: 11-100 transitions
  - `MEDIUM`: 2-10 transitions
  - `LOW`: 1 transition
  - `NONE`: 0 transitions

### 3. Coverage Gap Detection
- Stuck-at signals (0 transitions) with severity ranking
- Critical: internal control signals stuck
- High: data bus bits stuck
- Medium/Low: other low-activity signals
- Sorted output (worst first) with test recommendations

### 4. Zero Stuck-Signal Verification
- When all signals show >0 transitions → proves toggle coverage convergence

### 5. CLI Usage

```bash
# Basic analysis
python run.py --vcd dump.vcd --report coverage.json

# With markdown report
python run.py --vcd dump.vcd --report coverage.json --markdown
```

## Validation

| Example | Signals | Stuck | Status |
|---------|---------|:-----:|:------:|
| i2c_full (i2c.vcd) | 37 | 0 | Verified |
| dma_full (dma_full_test.vcd) | 117 | 0 | Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: None (pure standard library)
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic toggle (binary 0/1) |
| standard | Per-bit toggle + activity levels |
| intensive | Gap detection + severity ranking |
| exhaustive | Cross-signal correlation + test generation bridge |

## Upstream

Simulators producing VCD: `sim-runner`, `tb-compiler` (iverilog / VCS / Questa)

## Downstream

- `coverage-gap-plugin` — gap JSON → targeted test generation
- `dashboard-gen` — coverage reports → HTML dashboards
