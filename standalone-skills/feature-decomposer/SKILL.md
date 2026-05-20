---
name: feature-decomposer
version: 1.0.0
quality_score: 76.4
lifecycle: beta
description: >
  Feature-driven testpoint decomposition engine. Decomposes spec features into
  verification testpoints with stimulus, checking, and coverage goals. Generates
  testpoints from spec FEATURES (not RTL code), marking unimplemented features
  as gaps for verification completeness tracking.
---

# feature-decomposer v1.0.0

Verification testpoint decomposition engine. Takes a spec YAML and produces a
complete set of verification testpoints derived from feature definitions.
Each testpoint includes stimulus description, checking mechanism, verification
stage (V1 smoke / V2 stress / V3 signoff), and RTL implementation status
(IMPLEMENTED / PARTIAL / UNIMPLEMENTED).

## Quick Start

```bash
cd standalone-skills/feature-decomposer
python run.py --help
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 / spec-analyzer 输出 | IP 规格描述，需含 `features` 段定义功能点 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--format` | 字符串 | 否 | CLI 参数 | 输出格式：`md`（Markdown）或 `json`，默认 `md` |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `verification-plan.md` | Markdown | 逐功能测试点分解表：每个 feature 展开为 1+ 测试点，标注验证阶段 (V1/V2/V3) 和 RTL 实现状态 |
| `testpoint_plan.json` | JSON | 机器可读的测试点数据：含测试点名称、验证阶段、关联 feature、RTL 实现状态 |
## Capabilities

### 1. Spec-Driven Testpoint Decomposition
- Decomposes each spec feature into 1+ focused testpoints
- Protocol-specific testpoint generation (I2C controller, I2C target, multi-controller, etc.)
- Auto-detection of features from module description and register fields
- Feature-driven approach: testpoints generated from spec, not RTL

### 2. Register-Focused Testpoint Generation
- UVM register testpoints (read/write, reset value, bit-bash)
- Reserved bit checking with write-1s-read-0 verification
- Field-level access policy validation
- Register address decoding verification

### 3. Protocol-Aware Feature Detection
- Automatic I2C protocol feature detection from spec description
- Multi-controller / clock-stretching / 10-bit address detection
- Speed configuration, FIFO, interrupt, DMA transfer features
- Reset, error handling, host interface register-level detection

### 4. Multi-Stage Verification Planning
- V1 smoke testpoints for basic bring-up
- V2 stress/feature testpoints for comprehensive testing
- V3 signoff testpoints for coverage closure
- RTL status tracking (IMPLEMENTED / PARTIAL / UNIMPLEMENTED)

### 5. Gap Analysis and Coverage Tracking
- UNIMPLEMENTED features automatically marked in generated testpoints
- Per-feature implementation status summary
- Summary statistics: total testpoints, V1/V2/V3 breakdown, gap count

## Validation

| **Example** | **Testpoints** | **Status** |
|------------|:-------------:|:----------:|
| I2C | 90 testpoints from 11 features | ✅ Verified |
| OT DMA | Feature-driven decomposition | ✅ Verified |



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
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Effort | Depth |
|--------|-------|
| lite | Basic feature decomposition (default templates only) |
| standard | Protocol-aware decomposition with register testpoints |
| intensive | Full decomposition with all protocol-specific testpoints |
| exhaustive | Complete decomposition + custom feature mapping + JSON plan |

## Upstream

- `plan-generator` — verification plan with RTL analysis
- `spec-analyzer` — parsed spec dictionary with features and registers

## Downstream

- `test-generator` — consumes testpoints to generate UVM test sequences
- `regmodel-gen` — cross-references register testpoints with RAL model
- `coverage-plan` — coverage goals derived from testpoint list
- `dashboard-gen` — test results match testpoint plan
