---
name: regression-manager
version: 1.0.0
quality_score: 76.4
lifecycle: beta
description: >
  Regression test suite manager. Multi-run regression tracking with history,
  performance trend analysis, result comparison, and historical database.
---
# regression-manager v1.0.0

**Regression Test Suite Manager** — Multi-run regression tracking with history and trend analysis.

## Quick Start
```bash
cd standalone-skills/regression-manager
python run.py --module TOP --total 66 --passed 66
python run.py --list
python run.py --compare --run-a run001 --run-b run002
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--module` | 字符串 | 否 | CLI 参数 | 模块名称，本次回归的标识 |
| `--total` | 整数 | 否 | sim-runner | 总测试用例数 |
| `--passed` | 整数 | 否 | sim-runner | 通过测试数 |
| `--failed` | 整数 | 否 | sim-runner | 失败测试数 |
| `--coverage` | 浮点数 | 否 | coverage-engine | 覆盖率百分比，用于收敛趋势追踪 |
| `--iterations` | 整数 | 否 | CLI 参数 | 回归迭代次数 |
| `--list` | 标志 | 否 | CLI 参数 | 列出所有历史回归记录 |
| `--compare` | 标志 | 否 | CLI 参数 | 比较两次回归结果，需配合 `--run-a` 和 `--run-b` |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `regression_db.json` | JSON | 历史回归数据库：每次运行的测试数/通过率/覆盖率/耗时/种子列表 |
| `trends.json` | JSON | 趋势图表数据：通过率演进、覆盖率收敛曲线、编译/仿真时间变化 |
## Capabilities

### 1. Multi-Run Regression Tracking
- Auto-run-id generation (timestamp-based)
- Persistent JSON database
- Rich metadata per run (module, RTL hash, git commit)

### 2. Run Comparison
- Pass/fail diff between any two runs
- Performance delta (compile/sim time)
- Coverage change tracking

### 3. Performance Trend Analysis
- Sim time trends over iterations
- Compile time history
- Pass rate evolution

### 4. Trend Chart Data Generation
- Clean JSON output ready for dashboard ingestion
- Coverage convergence tracking
- Test count trends

## Validation

| **Example** | **Runs** | **Status** |
|------------|:------:|:----------:|
| ALU4 regression | 66 tests, multiple runs | ✅ Verified |
| OT DMA convergence | 22 tests, trend tracking | ✅ Verified |



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
- **Runtime**: Pure Python standard library (no third-party deps)
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic run recording + list |
| standard | Full tracking + run comparison |
| intensive | Trend analysis + coverage tracking |
| exhaustive | CI integration + webhook notifications |

## Upstream

- sim-runner (simulation results)
- coverage-engine (coverage data)

## Downstream

- dashboard-gen (trend visualization)
- doc-gen (regression summary in sign-off report)
