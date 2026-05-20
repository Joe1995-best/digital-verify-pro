---
name: formal-check
version: 1.0.0
quality_score: 78.4
description: >
  Formal property verification engine. Reads spec YAML, generates SVA assertions
  for registers, FSM, and interfaces, produces SymbiYosys .sby config, optionally
  runs sby, and writes formal_report.md summary.
---

# formal-check v1.0.0

**Formal Verification Agent** — Generate and run formal properties.

## Quick Start

```bash
cd standalone-skills/formal-check
python run.py --spec ../../i2c_spec.yml
python run.py --spec ../../spi_slave_spec.yml --no-run
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述，含寄存器定义、FSM 配置、接口时序 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `--no-run` | 标志 | 否 | CLI 参数 | 跳过 SymbiYosys 执行，仅生成断言和 .sby 配置 |
| `--bmc-depth` | 整数 | 否 | CLI 参数 | BMC 展开深度，默认 `20` |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `formal/assert_reg.sv` | SystemVerilog | 寄存器形式断言：读/写行为、域访问权限、地址范围假设 |
| `formal/assert_fsm.sv` | SystemVerilog | FSM 形式断言：状态可达性、转移合法性、one-hot 编码检查 |
| `formal/assert_iface.sv` | SystemVerilog | 接口协议形式断言：握手时序、数据完整 |
| `formal/{module}.sby` | YAML | SymbiYosys 配置文件：时钟/复位假设、BMC 深度、引擎选择 |
| `formal_report.md` | Markdown | 形式验证摘要报告：PASS/FAIL 按类别汇总、覆盖度量统计 |
## Capabilities

### 1. Register Property Generation
- Generate SVA assertions for register read/write behavior
- Assert field-level access permissions (RW, RO, WO, W1C, RW1C)
- Generate assume properties for valid address ranges
- Check reserved bit stability

### 2. FSM Property Generation
- State reachability assertions
- Transition legality checks
- One-hot encoding verification
- Deadlock/livelock detection properties

### 3. Interface Protocol Properties
- Protocol timing assertions (setup/hold, handshake sequences)
- Data integrity covers across bus transactions
- Arbitration fairness guarantees

### 4. SymbiYosys Integration
- Generate complete .sby configuration files
- Specify clock/reset assumptions
- Configure BMC depth and k-induction parameters
- Optional sby execution with result parsing

### 5. Formal Report Generation
- Pass/fail summary per property category
- Coverage metrics (proven properties vs bounded)
- Warning for unreachable cover statements

## Validation

| **Example** | **Properties** | **Status** |
|------------|:-------------:|:----------:|
| Dual Port Stack | Full formal proof | ✅ Verified |
| OT DMA | Register + FSM properties | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: `pyyaml`, `jinja2`
- **Internal**: `lib/template_engine.py`, `lib/validators.py`, `lib/formal_check_gen.py`
- **Optional**: SymbiYosys (sby) for formal execution
- **OS**: Windows / Linux / macOS

## Effort

| Level | Properties | Coverage |
|-------|-----------|----------|
| lite | Core register assertions | Basic address checking |
| standard | Registers + FSM properties | State reachability |
| intensive | Full property suite | Exhaustive formal coverage |
| exhaustive | All properties + custom | Full formal sign-off |

## Upstream

Design specification (YAML)

## Downstream

- `coverage-plan` — consumes formal coverage results
- `doc-gen` — includes formal report in verification close document
