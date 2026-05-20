---
name: dashboard-gen
version: 1.0.0
quality_score: 75.9
description: >
  Verification HTML dashboard generator. Creates interactive dashboards with
  coverage gauges, test result tables, regression trends, and heatmaps.
---
# dashboard-gen v1.0.0

**Verification Dashboard Generator** — Interactive HTML dashboards from simulation and coverage data.

## Quick Start
```bash
cd standalone-skills/dashboard-gen
python run.py --module i2c --output dashboard.html --total 66 --passed 66
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--module` | 字符串 | 是 | CLI 参数 | DUT 模块名称，用于标题和标识 |
| `--output` | 路径 | 是 | CLI 参数 | 输出 HTML 文件路径 |
| `--total` | 整数 | 否 | regression-manager | 总测试用例数 |
| `--passed` | 整数 | 否 | regression-manager | 通过测试数 |
| `--failed` | 整数 | 否 | regression-manager | 失败测试数 |
| `--toggle-cov` | 浮点数 | 否 | coverage-engine | 信号翻转覆盖率百分比 |
| `--fsm-cov` | 浮点数 | 否 | coverage-engine | FSM 状态覆盖率百分比 |
| `--func-cov` | 浮点数 | 否 | coverage-plan | 功能覆盖率百分比 |
| `--iterations` | 整数 | 否 | regression-manager | 回归迭代次数 |
| `--tests` | JSON 数组 | 否 | regression-manager | 测试结果明细的 JSON 数组 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `<output>.html` | HTML | 自包含交互式仪表盘（Chart.js 渲染）：覆盖度仪表 + 测试结果表 + 回归趋势 + FSM 热力图，无需外部服务端 |
## Capabilities

### 1. Coverage Gauges
- Animated gauge charts for toggle / FSM / functional coverage
- Color-coded thresholds (red < 70%, amber < 90%, green >= 90%)

### 2. Test Results Table
- Sortable by test name / status / duration
- Pass/fail icons with color coding
- Per-test details expandable

### 3. Regression Trend Charts
- Pass/fail over regression iterations
- Coverage convergence trends

### 4. FSM Coverage Visualization
- State visit counts
- Transition coverage heatmap

### 5. Coverage Heatmap
- Module-level coverage breakdown
- Color intensity by coverage percentage

## Validation

| **Example** | **Dashboard** | **Status** |
|------------|:-------------:|:----------:|
| ALU4 | 66/66 pass dashboard | ✅ Verified |
| OT DMA | 89.8% toggle + trends | ✅ Verified |
| I2C | Coverage gauges + test table | ✅ Verified |

## Dependencies

- **Python**: >= 3.8
- **Runtime**: Pure Python standard library
- **Browser**: Any modern browser (Chart.js loaded from CDN)
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Dashboard depth |
|--------|-----------------|
| lite | Basic gauges + test table |
| standard | Full dashboard + trend charts |
| intensive | All features + heatmap |
| exhaustive | Custom plugins + export |

## Upstream

- coverage-engine (coverage data)
- sim-runner (simulation results)
- regression-manager (regression history)

## Downstream

- doc-gen (dashboard screenshots for sign-off)
