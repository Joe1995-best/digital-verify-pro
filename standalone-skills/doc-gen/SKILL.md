---
name: doc-gen
version: 1.0.0
quality_score: 77.4
description: >
  Generate verification documentation: verification close report and documentation
  from all verification artifacts. Protocol-agnostic documentation generation that
  counts and catalogs all generated verification environment files.
---

# doc-gen v1.0.0

**Documentation Agent** — Verification close documentation generation.

## Quick Start

```bash
cd standalone-skills/doc-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述，用于提取模块名和规格概要 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/`，用于扫描已有验证产物 |
| `--env-dir` | 目录 | 否 | env-builder 输出 | 验证环境目录，用于统计文件数量和类型 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `docs/verification-close-report.md` | Markdown | 完整验证签收报告：模块概要、接口/寄存器/测试统计、文件清单、验证结论 |
## Capabilities

### 1. Verification Close Report
- Module and spec summary
- Interface, register, and test scenario counts
- Generated SV file inventory (interfaces, agents, sequences, assertions, scoreboards, coverage)
- Test scenario descriptions

### 2. Environment Inventory
- Report counts of all generated verification components
- Breakdown by category (IF, agent, sequence, assertion, scoreboard, coverage)
- Key file listing (testbench, environment, package, Makefile)

### 3. Post-Generation Validation
- Validate report generation completeness
- Check output directory structure

## Validation

| **Example** | **Report** | **Status** |
|------------|:---------:|:----------:|
| I2C | Full close report, 42 SV files | ✅ Verified |
| OT DMA | 22-test close report | ✅ Verified |
| PCIe EP | 64-file inventory | ✅ Verified |

## Effort

| Effort | Documentation depth |
|--------|---------------------|
| lite | Basic file inventory only |
| standard | Full close report with test summary |
| intensive | Report + coverage analysis + bug list |
| exhaustive | Complete sign-off package |

## Dependencies

- **Python**: >= 3.10
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Upstream

All verification generation tools:
- `env-builder` — environment component counts
- `test-generator` — sequence counts
- `assertion-gen` — assertion counts
- `scoreboard-gen` — scoreboard counts
- `coverage-plan` — coverage counts
- `sim-runner` — simulation results
- `waveform-analyzer` — coverage metrics

## Downstream

- Final verification sign-off documentation
