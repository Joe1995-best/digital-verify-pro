---
name: fsm-templates
version: 1.0.0
quality_score: 78.4
description: >
  FSM controller templates from spec YAML. Generates synthesizable FSM RTL
  with unified always_ff pattern, interrupt auto-management, and error handling.
  Supports DMA 8-state and simple 3-state controllers following dma.sv v4
  verified patterns.
---

# fsm-templates v1.0.0

FSM controller template generator for digital IC verification. Produces
synthesizable SystemVerilog FSM controllers with unified always_ff blocks,
interrupt auto-set with W1C clear, error_flag persistence, and coverage-friendly
patterns. Follows dma.sv v4 verified design style.

## Quick Start

```bash
cd standalone-skills/fsm-templates
python run.py --help
```

## Inputs

| 参数 | 类型 | 必填 | 来源 | 说明 |
|------|------|:----:|------|------|
| `--spec` | YAML 文件 | 是 | 用户提供 | IP 规格描述，需含 `fsm` 段定义状态机配置 |
| `--out` | 目录 | 否 | CLI 参数 | 输出目录，默认 `output/` |
| `fsm.name` | 字符串 | 是 | spec YAML `fsm` 段 | FSM 模块名 |
| `fsm.type` | 字符串 | 是 | spec YAML `fsm` 段 | FSM 类型：`dma` (8状态) 或 `simple` (3状态) |
| `fsm.host_width` | 整数 | 否 | spec YAML `fsm` 段 | 主机总线地址宽度，默认 `32` |
| `fsm.status_regs` | 列表 | 否 | spec YAML `fsm` 段 | 状态信号配置列表 |
| `fsm.interrupts` | 列表 | 否 | spec YAML `fsm` 段 | 中断信号配置：名称、触发条件、W1C 使能 |
| `fsm.error_configs` | 列表 | 否 | spec YAML `fsm` 段 | 错误条件配置：错误码、触发条件、持久化行为 |
## Outputs

| 输出文件 | 格式 | 说明 |
|---------|:----:|------|
| `dma_fsm.sv` | SystemVerilog | 可综合 FSM RTL：统一 `always_ff` 模式、中断自管理、error_flag 持久化、iverilog 11 兼容 |
## Capabilities

### 1. DMA 8-State FSM Generation
- Full DMA read/write pipeline: Idle → Read → SendRead → WaitRead → Write → SendWrite → WaitWrite → Done
- Host bus interface with request/grant protocol
- Address increment and chunk counter support
- Remaining data count tracking with auto-complete detection

### 2. Simple 3-State FSM Generation
- Lightweight controller: Idle → Active → Done
- Minimal state machine for simple control flows
- Reduced port count for lower complexity designs

### 3. Interrupt Auto-Management
- Auto-set interrupt status registers on done/chunk/error events
- W1C (Write-1-to-Clear) support via APB interface
- Interrupt enable masking with AND-gated outputs
- Persistent interrupt state across clears

### 4. Error Handling and Coverage Compliance
- Error_flag persistence (NOT cleared every cycle — avoids coverage warnings)
- Error_code tracking with configurable error conditions
- No `inside` operator, no `unique case`, no `always_comb` reading FF vars
- Coverage-friendly RTL patterns (dma.sv v4 verified)

### 5. Spec-Driven Configuration
- Fully parameterized from spec YAML FSM section
- Automatic `fold_inside` conversion for iverilog 11 compatibility
- Port list auto-generated from status/interrupt/error configs

## Validation

| **Example** | **FSM Type** | **Status** |
|------------|:----------:|:----------:|
| OT DMA v4 | 8-state DMA FSM | ✅ Verified |
| Simple ctrl | 3-state controller | ✅ Verified |
| Error coverage | error_flag persistence verified | ✅ Verified |

## Dependencies

- **Python**: >= 3.10
- **Runtime**: none (pure Python standard library)
- **OS**: Windows / Linux / macOS

## Effort

| Effort | Depth |
|--------|-------|
| lite | Simple 3-state FSM only |
| standard | DMA 8-state FSM with default parameters |
| intensive | Full DMA FSM with custom status/interrupt/error configs |
| exhaustive | Complete FSM with combo outputs + custom host width |

## Upstream

- `spec-analyzer` — parsed spec dict with FSM configuration
- Design specification (YAML)

## Downstream

- `tb-compiler` — compiles generated FSM RTL
- `sim-runner` — simulates FSM behavior
- `dashboard-gen` — shows FSM coverage from dashboard
