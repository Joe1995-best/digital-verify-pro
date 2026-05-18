---
name: digital-verify-pro
description: |
  专业级数字芯片验证框架，双模式并行：手写 RTL + VRF 仿真验证 / spec-YAML → RTL 自动生成 + 仿真验证。
  覆盖度驱动收敛，RTL 审查清单 + 验证签收清单自动化。
  纯 SystemVerilog + iverilog 兼容，不需要商业 EDA 工具。

  Use when: user mentions 芯片验证, RTL, SystemVerilog, verification, coverage,
  testbench, simulation, register model, CSR, FSM, DMA, coverage convergence
---

# Digital Verify Pro

专业级数字芯片验证系统。双模式、覆盖度收敛、checklist 驱动签收。

---

## 为什么需要这个

大多数 AI 验证把芯片验证当软件测试做："写个 testbench，编译，检查输出"。这漏了芯片验证真正难的地方：

- **寄存器级正确性**：每个寄存器有复位值、位宽、访问类型（RW/RO/W1C）。错一个驱动软件就跑不起来。
- **覆盖度收敛**：跑一个测试不够。要知道哪些信号翻转了、哪些寄存器测到了、验证是不是收敛了。
- **协议时序**：APB 握手、host 接口 gnt/rvalid 时序 — 每个协议有自己的微妙要求。
- **仿真器兼容性**：iverilog 11 vs Questa vs VCS 的 SV 支持层级不同。验证系统必须全部兼容。
- **FSM 时序**：next-state 和 action 的 NBA 调度顺序错了，整个 FSM 不工作。

digital-verify-pro 不遗漏任何一点。

---

## 双验证模式

```
                          ot_dma_spec.yml
                                │
                     ┌──────────┴──────────┐
                     ▼                     ▼
             ┌─────────────┐       ┌──────────────┐
             │  Mode 1:     │       │  Mode 2:      │
             │  手写 RTL    │       │  Spec 生成 RTL │
             └──────┬──────┘       └──────┬────────┘
                    │                     │
                    ▼                     ▼
             ┌─────────────┐       ┌──────────────┐
             │ dma.sv v4   │       │ run_rtl_gen.py│
             │ (增强 FSM)  │       │ fsm_templates │
             └──────┬──────┘       └──────┬────────┘
                    │                     │
          ┌─────────┴─────────┐  ┌───────┴────────┐
          ▼                   ▼  ▼                ▼
   ┌────────────┐    ┌────────────────┐    ┌────────────┐
   │ VRF 测试套件│    │ 断言模块       │    │ VRF 基础测试│
   │ 22 tests   │    │ APB/FSM/DMA   │    │ 14 tests   │
   └──────┬─────┘    └───────┬────────┘    └──────┬─────┘
          │                  │                    │
          └──────────────────┴────────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ CoverageEngine   │
                    │ (VCDParser +     │
                    │  toggle analysis)│
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ convergence_report│
                    │ + checklist audit │
                    └──────────────────┘
```

### Mode 1: 手写 RTL + VRF 全验证

适用于已有 RTL 的设计，配合 VRF（Verification Random Framework）框架验证。

```
流程:
1. dma.sv v4 (手写增强版)
2. VRF testbench (22 tests: 寄存器/DMA/chunk/error/stop/incr)
3. 断言模块 (APB协议/FSM stall/DMA timeout)
4. iverilog 编译 + 仿真
5. CoverageEngine VCD 解析 + toggle 分析
6. 收敛报告 + checklist 审计

结果: 22/22 PASS, 93.8% toggle, 0 stuck
```

### Mode 2: Spec → RTL 自动生成 + 验证

适用于从 spec YAML 自动生成完整 RTL，再运行仿真。

```
流程:
1. ot_dma_spec.yml (20 registers, 48 fields, FSM config)
2. run_rtl_gen.py:
   ├─ fsm_templates.py → ot_dma_dma_fsm.sv (8-state FSM)
   ├─ reg bank         → ot_dma_regs.sv (Register bank)
   └─ top module       → ot_dma.sv (Wiring)
3. VRF testbench (14 tests)
4. iverilog 编译 + 仿真
5. 覆盖度分析

结果: 14/14 PASS, 87.9% toggle, 0 stuck
```

---

## 核心技术

### VRF (Verification Random Framework)

非 UVM 纯 SV 验证框架，专为 iverilog 11 设计：

```verilog
// 核心结构：统一 always_ff — next-state + actions + error handling
always_ff @(posedge clk_i or negedge rst_ni) begin
  // 1. 计算下一状态（blocking =，立即生效）
  // 2. 状态更新（NBA <=）
  // 3. 动作触发（基于当前 state_q）
end
```

**FSM 设计原则：**
| 原则 | 说明 |
|------|------|
| 统一 always_ff | next-state + actions 一个块，避免跨块竞态 |
| state_q 触发动作 | `case(state_q)` 而非 `case(state_d)` |
| blocking + NBA 分离 | next-state 用 `=`，更新和动作用 `<=` |
| error_flag 持久化 | 不复位（除非复位或 SW 清除） |
| 中断 auto-set | done/error/chunk 完成时自动置位 |

**断言模块（纯过程式，iverilog 兼容）：**
| 模块 | 检查内容 |
|------|---------|
| `vrf_assert_apb.sv` | X 检测、penable 时序、地址稳定性 |
| `vrf_assert_fsm.sv` | 状态 stall 检测（超时 N 周期无变化） |
| `vrf_assert_dma.sv` | host_req 超时、done+error 互斥检查 |

### RTL 自动生成 (fsm_templates.py)

从 spec YAML 生成可综合 FSM 控制器：
- 8-state DMA read/write pipeline
- 统一 always_ff 模式
- 无 `inside` / `unique case` / `always_comb` 读 ff 变量
- error_flag 持久化、中断 auto-set、W1C 清除
- iverilog 11 兼容

### CoverageEngine (VCDParser)

纯 Python VCD 解析 + toggle 分析：
- 全信号逐 bit toggle 分析
- 分级活动度（NONE/LOW/MEDIUM/HIGH/VERY_HIGH）
- 覆盖缺口检测 + 严重性排序
- 0 stuck 信号报告

---

## 测试套件

### Mode 1: 手写 RTL (22 tests)

| # | 测试 | 覆盖功能 |
|---|------|---------|
| 1-3 | 寄存器复位/RW/PSLVERR | CSR 正确性 |
| 4-5 | 单字/多字 DMA | 基本传输 |
| 6-7 | byte/half-word 宽度 | 传输宽度 |
| 8 | Chunk 中断 (size=3) | 块中断 |
| 9 | 错误注入 | host_err 检测 |
| 10 | DMA 停机 | stop_q 控制 |
| 11-12 | Incr/多配置传输 | 增量地址 + 多配置 |

### Mode 2: 生成 RTL (14 tests)

| # | 测试 | 覆盖功能 |
|---|------|---------|
| 1-3 | 寄存器复位/RW/PSLVERR | CSR 正确性 |
| 4-7 | 单字/4字/byte/half-word | 基本 + 宽度 |
| 8 | Chunk 中断 | 块中断 |

---

## 覆盖度收敛

### 流水线 (run_dma_convergence.py)

```
仿真 (22/22) → 覆盖度分析 → RTL-GEN 编译检查 → Checklist 审计 → 收敛报告
```

### 覆盖度数据

| 迭代 | 手写 RTL | 生成 RTL | 说明 |
|------|:--------:|:--------:|------|
| 基线 | 55.6% | - | FSM bug: case(state_d) |
| FSM 修复 | 88.7% | - | case(state_q) fix |
| VRF 全测试 | 87.5% | - | 加测试降了？因为信号更多了 |
| RTL v4 + VCD bug fix | **93.8%** | **87.9%** | VCDParser int(base=16→2) fix |
| Stuck signals | **0** | **0** | 全部解释 |

---

## Checklist 体系

### 验证签收清单 (`checklists/verification_checklist.md`)

| Phase | 名称 | 内容 |
|-------|------|------|
| DSR | Spec 完整性审查 | 接口/寄存器/FSM 状态 |
| TPR | 功能点→测试映射 | Feature-to-Test Matrix |
| RTL-GEN | 生成代码审查 | unique case/inside/error persist |
| SIM | 仿真结果审查 | 测试 PASS/Assertion/回归 |
| CCR | 覆盖度收敛 | Toggle/Stuck 信号分析 |
| SO | 签收 | 所有条件满足 |

### RTL Review 清单 (`checklists/rtl_review_checklist.md`)

| Section | 内容 | 条款 |
|---------|------|:----:|
| S1 | 可综合风格 | always_ff 规范、无 latch |
| S2 | iverilog 11 兼容 | 无 inside/unique/covergroup |
| S3 | 覆盖友好设计 | error 持久、intr auto-set |
| S4 | 寄存器规范 | 位宽 32bit、地址解码 |
| S5 | FSM 设计规范 | state_q-based actions |
| S6 | 生成 RTL 检查 | 端口匹配、地址宽度 |

---

## 项目结构

```
digital-verify-pro/
├── run_dma_convergence.py    ← 收敛流水线（一键）
├── run_e2e.py               ← 双模式对比流水线
├── PRO_SKILL.md              ← 本文件
├── ot_dma_spec.yml           ← DMA 完整 spec
│
├── verify_ot_dma/            ← Mode 1: 手写 RTL 验证
│   ├── dma.sv                ← v4 增强版 FSM
│   ├── vrf/
│   │   ├── env/              ← VRF 环境（APB driver + 断言）
│   │   ├── sva/              ← 过程式断言模块
│   │   └── tests/            ← 测试用例
│   └── convergence_report.md ← 收敛报告
│
├── output_ot_dma/            ← Mode 2: 生成 RTL
│   ├── rtl/rtl/
│   │   ├── ot_dma_dma_fsm.sv ← FSM 控制器
│   │   ├── ot_dma.sv         ← 顶层模块
│   │   └── ot_dma_regs.sv    ← 寄存器库
│   ├── vrf/tests/            ← 生成 RTL 测试
│   └── ...
│
├── pipeline/
│   ├── run_rtl_gen.py        ← RTL 生成器
│   ├── fsm_templates.py      ← FSM 模板引擎
│   └── template_engine.py    ← spec 解析
│
├── engines/
│   └── coverage_engine.py    ← VCD 解析 + toggle 分析
│
├── checklists/
│   ├── verification_checklist.md ← 6-phase 签收清单
│   └── rtl_review_checklist.md   ← RTL 代码审查
│
├── tools/
│   └── checklist_audit.py     ← 自动审计工具
│
├── config/                   ← 配置文件
├── examples/                 ← spec 示例
├── references/               ← 参考文档
└── wiki/                     ← 知识库
```

---

## 快速开始

```bash
# Mode 1: 手写 RTL 验证
cd digital-verify-pro
python run_dma_convergence.py

# Mode 2: Spec → RTL 生成 + 验证
python pipeline/run_rtl_gen.py --spec ot_dma_spec.yml --out output_ot_dma
iverilog -g2012 -s ot_dma -o /dev/null output_ot_dma/rtl/rtl/*.sv

# 双模式对比
python run_e2e.py

# 单独跑 VRF 测试
cd verify_ot_dma
iverilog -g2012 -s dma_full_test -o sim dma.sv vrf/env/*.sv vrf/sva/*.sv vrf/tests/dma_full_test.sv
vvp sim
```

---

## RTL 设计规范

### always_ff 模式（所有新 RTL 必须遵守）

```verilog
// ✅ 正确模式
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    // 复位所有寄存器
  end else begin
    // 1. 计算 next-state (blocking)
    state_d = state_q;
    case (state_q) ... endcase

    // 2. 状态更新 (NBA)
    state_q <= state_d;

    // 3. 动作 (NBA, 基于当前 state_q)
    case (state_q) ... endcase
  end
end
```

```verilog
// ❌ 错误模式
always_ff @(posedge clk) begin
  state_q <= state_d;
  case (state_d) ...    // ← 用 state_d 触发动作，初始化永远不执行
end

always_comb begin
  state_d = f(state_q); // ← iverilog 中 always_comb 延迟一周期
end

assign state_d = f(state_q); // ← 只对 state_q 敏感，忽略 start_q 变化
```

### 覆盖友好模式

```verilog
// ✅ 正确: error 持久化
error_flag_q <= error_flag_q;  // 保持

// ❌ 错误: error 每周期清零
error_flag_q <= 1'b0;

// ✅ 正确: intr auto-set
dma_done_intr_q <= 1'b1;

// ✅ 正确: state_q 触发动作
case (state_q)
  DmaIdle: if (start_q && enable_q) remaining_q <= total_data_size_q;
```

---

## 验证过的 IP

| IP | 手写 RTL | 生成 RTL | 覆盖度 | 状态 |
|----|:--------:|:--------:|:------:|:----:|
| **OT DMA (v4)** | 22/22 ✅ | 14/14 ✅ | 93.8% / 87.9% | **已验证** |
| I2C Controller | 遗留 | 需要 | - | ⏳ |
| GPIO PL061 | 遗留 | 需要 | - | ⏳ |
| PCIe EP | 遗留 | 需要 | - | ⏳ |

---

## 参考文献

- `references/testbench-patterns.md` — VRF testbench 模板
- `checklists/verification_checklist.md` — 6-phase 签收清单
- `checklists/rtl_review_checklist.md` — RTL 代码审查清单
- `wiki/anti-patterns.md` — 常见验证错误
- `wiki/lessons/` — 每轮验证的经验教训
- `STANDARDS.md` — 与 OpenTitan/UVMA 的对标分析
