---
name: sim-runner
version: 1.0.0
quality_score: 76.4
lifecycle: development
description: >
  Run simulations with generated testbenches. Manages test execution, seed
  variation, result logging, pass/fail determination, and simulation log
  analysis for Questa/ModelSim, VCS, and Xcelium simulators.
---

# sim-runner v1.0.0

**Runner Agent Phase 2** — Execute simulations.

## Quick Start

```bash
cd standalone-skills/sim-runner
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --tool questa
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述，用于解析模块名和测试列表 |
| `--outdir` | 目录 | 否 | CLI 参数 | 输出/工作目录，默认 `output/` |
| `--test` | 字符串 | 否 | CLI 参数 | 指定单个测试名运行 |
| `--all` | 标志 | 否 | CLI 参数 | 运行所有已发现的测试 |
| `--list` | 标志 | 否 | CLI 参数 | 列出可用测试用例 |
| `--seeds` | 整数 | 否 | CLI 参数 | 每测试随机种子数，默认 `1` |
| `--simv` | 路径 | 否 | tb-compiler 输出 | simv 路径覆盖（自动检测失败时使用） |
| `--dump-vcd` | 标志 | 否 | CLI 参数 | 使能 VCD 波形 dump |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `sim_results.yml` | YAML | 逐测试逐种子的 PASS/FAIL 汇总：含仿真耗时、日志路径、失败原因 |
| `{test_name}_s{seed}.log` | 日志 | 每次仿真运行的完整日志：UVM 消息、断言结果、覆盖率摘要 |
| `output.vcd` | VCD | 仿真波形 dump（`--dump-vcd` 时可选生成） |
## Supported Flow

```bash
# Run all tests with multiple seeds
python run.py --spec ../../i2c_spec.yml
# Results saved to output/sim_results/
```

## Capabilities

### 1. Test Execution
- Run all tests from the test list with seed variation
- Configurable seeds per test based on effort level
- Sequential test execution with pass/fail logging

### 2. Log Analysis
- UVM_ERROR/UVM_FATAL message extraction with timestamps
- Pass/fail count per test
- Covergroup coverage percentage extraction

### 3. Result Aggregation
- `sim_results.yml` with per-test pass/fail summary
- Total pass/fail statistics
- Seed variation results

### 4. Post-Simulation Cleanup
- Waveform dump generation (optional)
- Simulation artifact organization

## Validation

| **Example** | **Tests** | **Status** |
|------------|:-------:|:----------:|
| ALU4 | 66/66 PASS | ✅ Verified |
| OT DMA | 22/22 PASS + VCD dump | ✅ Verified |
| I2C | 10/10 PASS (with CSR tests) | ✅ Verified |



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
- **Required**: Questa/ModelSim, VCS, or Xcelium installed for actual simulation
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Single seed per test, basic pass/fail log |
| standard | Multiple seeds, UVM log analysis |
| intensive | Seed variation + coverage extraction |
| exhaustive | Full simulation + waveform collection + trends |

## Upstream

- `tb-compiler` — consumes compiled simulation executable
- `test-generator` — consumes test list for execution
- `coverage-plan` — coverage model active during simulation

## Downstream

- `waveform-analyzer` — produces post-simulation analysis
- `doc-gen` — consumes simulation results for documentation

