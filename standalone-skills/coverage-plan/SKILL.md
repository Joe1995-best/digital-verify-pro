---
name: coverage-plan
version: 1.0.0
quality_score: 78.9
description: >
  Generate functional coverage groups from verification plan. Creates covergroup
  definitions for interfaces, registers, internal states, and cross coverage.
  Protocol-agnostic coverage generation from spec YAML.
---

# coverage-plan v1.0.0

**Verification Architect Phase 1** — Coverage definition.

## Quick Start

```bash
cd standalone-skills/coverage-plan
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 / spec-analyzer 输出 | IP 规格描述，含接口列表和寄存器映射 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--plan` | YAML 文件 | 否 | spec-analyzer 输出 | 验证计划文件，用于提取覆盖目标 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `rtl/verification/env/coverage/cov_groups.sv` | SystemVerilog | 总 covergroup 定义：所有覆盖点的顶级组织和声明 |
| `rtl/verification/env/coverage/cov_iface.sv` | SystemVerilog | 接口协议覆盖：事务类型 bin、地址范围、数据值分布 |
| `rtl/verification/env/coverage/cov_reg.sv` | SystemVerilog | 寄存器覆盖：地址可达性、域级值覆盖、读/写操作覆盖 |
| `rtl/verification/env/coverage/cov_cross.sv` | SystemVerilog | 交叉覆盖：interface x register、协议状态 x 数据完整性 |
| `coverage_plan.md` | Markdown | 覆盖计划说明文档：覆盖点列表、覆盖目标百分比 |
## Capabilities

### 1. Interface Coverage
- Transaction type coverage bins
- Address range coverage
- Data value coverage

### 2. Register Coverage
- All register address access coverage
- Field-level value coverage
- Read/write operation coverage

### 3. Cross Coverage
- Interface × Register cross coverage
- Protocol state × data cross coverage

### 4. Post-Generation Validation
- Coverage group structural validation
- Coverage model completeness check

## Validation

| **Example** | **Covergroups** | **Status** |
|------------|:--------------:|:----------:|
| I2C | Interface + register + cross coverage | ✅ Verified |
| OT DMA | FSM state + register + toggle | ✅ Verified |
| PCIe EP | 64-file env, full coverage plan | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Level | Coverpoints | Cross coverage |
|-------|-------------|----------------|
| lite | Interface only | None |
| standard | Interface + registers | Basic cross |
| intensive | Full coverage plan | Full cross coverage |
| exhaustive | All + corner cases | Complete closure plan |

## Upstream

- `spec-analyzer` — consumes interface list + register map + test scenarios
- `formal-check` — optionally consumes formal coverage results

## Downstream

- `sim-runner` — coverage collected during simulation
- `waveform-analyzer` — coverage metrics extracted post-sim
