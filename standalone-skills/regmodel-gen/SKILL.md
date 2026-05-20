---
name: regmodel-gen
version: 1.0.0
quality_score: 78.4
description: >
  Generate UVM Register Abstraction Layer (RAL) model from spec register map.
  Creates IEEE 1800.2 compliant uvm_reg_block, registers, and fields with
  full access methods and address decoding.
---

# regmodel-gen v1.0.0

**Verifier Agent** — UVM register model generation.

## Quick Start

```bash
cd standalone-skills/regmodel-gen
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../i2c_spec.yml --out verification_output
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 / spec-analyzer 输出 | IP 规格描述，含完整寄存器映射定义 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--ral-prefix` | 字符串 | 否 | CLI 参数 | RAL 模型类名前缀，默认使用模块名 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `rtl/verification/env/ral/{module}_ral_block.sv` | SystemVerilog | IEEE 1800.2 标准 UVM RAL 模型：reg_block + 寄存器类 + 域定义 + 地址译码 |
| `rtl/verification/env/ral/{module}_ral_pkg.sv` | SystemVerilog | UVM 包：import 所有 RAL 组件，供验证环境集成 |
| `rtl/verification/env/ral/reg/{reg_name}_reg.sv` | SystemVerilog | 每寄存器一个 UVM reg 类：含各域的 access 策略、volatile 属性、前后门访问方法 |
## Capabilities

### 1. Register Model Generation
- IEEE 1800.2 compliant RAL model
- Reg_block with hierarchical register organization
- Register fields with access policy (RW, RO, WO, W1C, RW1C)
- Address map with correct address decoding

### 2. Field Access Method Generation
- Read/write methods per access type
- Volatile and non-volatile field handling
- Hardware vs software access differentiation

### 3. Package Structure
- Complete UVM package with all necessary imports
- Compilable with UVM 1.2 and 1800.2

## Validation

| **Example** | **Registers** | **Fields** | **Status** |
|------------|:-----------:|:--------:|:----------:|
| I2C | Full RAL block + pkg | All fields | ✅ Verified |
| OT DMA | 16+ registers | 100+ fields | ✅ Verified |
| PCIe EP | 28 registers | 113 fields | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`
- **Internal**: `lib/template_engine.py`
- **OS**: Windows / Linux / macOS
- **EDA**: iverilog, Verilator, VCS, Questa (generated output compatible)

## Effort

| Level | Registers | Fields |
|-------|-----------|--------|
| lite | Core address map only | Basic fields |
| standard | All registers | Full field definitions |
| intensive | Full model + aliases | All access types |
| exhaustive | Complete RAL + verification | Every register corner |

## Upstream

- `spec-analyzer` — consumes register map
- Design specification (YAML)

## Downstream

- `tb-compiler` — consumes RAL model for compilation
- `test-generator` — uses RAL for register sequences
- `scoreboard-gen` — uses RAL for expected value checking
