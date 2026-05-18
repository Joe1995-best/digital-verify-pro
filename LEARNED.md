# 从参考项目学到的优化方案

从 OpenTitan、cocotb、VUnit 等工业/开源 IC 验证项目提取的可以借鉴到 pipeline 中的方案。

---

## 1. OpenTitan (lowRISC) — 寄存器生成

**Repo**: github.com/lowRISC/opentitan  
**工具**: `util/reggen/reggen.py`

### 学到的东西

#### 1.1 HJSON → 多输出管道

OpenTitan 的 register spec 格式是 HJSON（带注释的 JSON），`reggen.py` 读一次配置输出多个东西：

```
gpio.hjson
    │
    ▼
reggen.py
    ├── gpio_reg_top.sv        ← RTL: 寄存器堆
    ├── gpio_reg_top.gen.json  ← 元数据
    ├── gpio.h                 ← C header (SW 驱动)
    ├── gpio_ral_pkg.sv        ← UVM RAL 模型
    └── doc/_registers.rst     ← 文档
```

**可以借鉴到我们 pipeline 的地方**：

| 对比 | OpenTitan | 我们 |
|------|-----------|------|
| 输入格式 | HJSON (结构化) | YAML (类似) |
| RTL 输出 | 模板驱动 (Mako) | python 字符串拼接 |
| UVM RAL | ✅ 自动生成 | ❌ 没有 |
| C header | ✅ 自动生成 | ❌ 没有 |
| 文档 | ✅ .rst 自动生成 | ✅ .md 已生成 |
| 一致性检查 | ✅ 强制 reset/access 一致性 | ❌ 没有 |

**建议采纳**：
- 加入 **UVM RAL 模型生成**（run_ral_gen.py），从 register 描述生成 `ral_block` 和 `ral_pkg`
- 加入 **C header 生成**（run_sw_header_gen.py），输出寄存器地址宏供驱动开发用
- 加入 **一致性检查**：reset 值必须匹配 field 宽度，access 类型必须合法

#### 1.2 OpenTitan 的 hwaccess 标记

OpenTitan 每个 register field 都有 `hwaccess` 标记：

```hjson
{ name: "INTR_STATE", desc: "Interrupt State", ...,
  fields: [
    { bits: "0", name: "gpio", desc: "..." ,
      hwaccess: "hrw",          // HW read/write（硬件可以读写）
      hwqe: "true"              // HW 写触发（硬件写即生效）
    }
  ]
}
```

**可借鉴**：在 spec 的 field 中加 `hwaccess` 标记（已加的 `access` 是 SW view），再加 `hwaccess` 给 RTL 生成用。

---

## 2. OpenTitan DV — Verification Framework

**结构**: `hw/dv/`

### 学到的东西

#### 2.1 统一的 DV 目录布局

OpenTitan 每个 IP 的验证目录是一致的：

```
hw/dv/<ip>/
├── env/                ← UVM environment
│   ├── <ip>_env.sv
│   ├── <ip>_env_cfg.sv
│   ├── <ip>_scoreboard.sv
│   └── seq_lib/
│       ├── <ip>_base_seq.sv
│       └── <ip>_common_vseq.sv
├── tests/
│   └── <ip>_test.sv
├── sim/
│   ├── Makefile        ← 统一编译脚本
│   └── <ip>.core       ← FuseSoC 核心定义
├── sv/
│   └── <ip>_assert.sv  ← SVA + bind
└── README.md
```

**可借鉴**：我们的目录已经很接近了。差距：
- 缺 `env_cfg.sv`（环境配置对象）— 应该加
- 缺 `vseq` 概念（virtual sequencer 统筹多 agent）— 应该加

#### 2.2 CSR Excl 文件

OpenTitan 为每个 IP 生成 `.csr_excl` 文件，标记哪些寄存器在验证中不检查（比如 WO 寄存器读返回 undefined）。用在仿真时排除不必要的 CSR 测试。

**可借鉴**：生成 `csr_excl.json`，标记 RO/WO 寄存器，供自动化的 CSR 测试跳过。

---

## 3. cocotb — Python 验证框架

**Repo**: github.com/cocotb/cocotb  
**理念**: 用 Python 协程代替 UVM 做验证

### 学到的东西

#### 3.1 Trigger 驱动

cocotb 用 `await RisingEdge(clk)` 而不是 UVM 的 clocking block：

```python
@cocotb.test()
async def test_write(dut):
    dut.psel.value = 1
    dut.pwrite.value = 1
    dut.paddr.value = 0x00
    dut.pwdata.value = 0xAA
    await RisingEdge(dut.pclk)
    dut.penable.value = 1
    await RisingEdge(dut.pclk)
    await RisingEdge(dut.pclk)
    assert dut.prdata.value == 0xAA
```

**可借鉴**：我们的 BFM 目前只有 SystemVerilog 的版本。可以生成一个 **Python cocotb testbench** 作为替代验证方案，让用户选择用 UVM 还是 cocotb。

#### 3.2 自动测试发现

cocotb 自动发现所有 `@cocotb.test()` 装饰的函数，不需要手动注册到回归列表。

**可借鉴**：我们的 test-generator 应该也生成一个 `test_list.txt` 或 `test_manifest.json`，列出所有可运行的测试和需要的 BFM 配置。

#### 3.3 Scoreboard 设计模式

cocotb 推荐使用 Python 的 `asyncio.Queue` 做 scoreboard。

**可借鉴**：我们的 scoreboard 模板应该加 **predictor + checker** 分离模式：

```
Monitor → predictor(transaction) → expected_queue
Monitor → actual(transaction)    → compare(expected, actual)
```

这样比目前的简单 push/pop 队列更通用。

---

## 4. VUnit — 结构化测试框架

**Repo**: github.com/VUnit/vunit  

### 学到的东西

#### 4.1 Pre/Post Run 钩子

VUnit 有 `pre_run()` 和 `post_run()` 方法：

```python
vu = VUnit.from_argv()
lib = vu.add_library("work")
lib.add_source_files("*.sv")
lib.set_compile_option("rivierapro.vlog_flags", ["-sv2k12"])
# pre_run: 生成仿真前需要的文件
# post_run: 收集覆盖率
vu.set_sim_option("disable_ieee_warnings", True)
vu.main()
```

**可借鉴**：我们的 `run_env_builder.py` 应该在生成环境的最后输出一个 `sim/run.py`（类似 VUnit 的入口），让用户一键仿真
：
```python
# sim/run.py — 自动生成
import subprocess
subprocess.run(["make", "-C", "sim"])
```

---

## 5. FuseSoC / Edalize — EDA 工具抽象

**Repo**: github.com/olofk/fusesoc

### 学到的东西

#### 5.1 文件列表自动管理

FuseSoC 用 `.core` 文件描述 IP 依赖：

```tcl
name: work:ip:pl061_gpio:0.1
filesets:
  rtl:
    files:
      - rtl/rtl/pl061_gpio.sv
      - rtl/rtl/pl061_gpio_regs.sv
      - rtl/rtl/pl061_gpio_irq.sv
    file_type: systemVerilogSource
  dv:
    depend:
      - lowrisc:dv:uvm_lib
    files:
      - dv/env/*.sv
      - dv/tests/*.sv
    file_type: systemVerilogSource
targets:
  default: &default
    filesets: [rtl, dv]
    tools: [verilator]
```

**可借鉴**：我们的 env-builder 应该额外生成一个 `ip.core` 文件，这样用户可以直接用 FuseSoC 编译和仿真。

---

## 6. Google's OpenHW / CORE-V — 断言库

**Repo**: github.com/openhwgroup/core-v-verif

### 学到的东西

#### 6.1 CV32E40P 断言包

CORE-V 项目有一个 SystemVerilog 断言库，覆盖 RISC-V 指令行为。每个断言都有：
- 标准的 `assert_name` 命名（`cv32e40p_*_assert`）
- 统一的 severity (`$error` / `$warning`)
- Formal-ready 写法（没有 `##[0:$]` 这种不可综合的延时）

**可借鉴**：我们的 assertion-gen 应该输出 formal-ready 的断言：
- 避免 `##[1:$]` 这种 unbounded delay（会用穷举空间爆炸）
- 使用 `s_eventually` / `s_until` 替代
- 所有断言加上 `expect` 版本供 test 中调用

#### 6.2 UVM 寄存器测试序列库

CORE-V 使用 `uvm_reg` 内置的 `uvm_reg_hw_reset_seq`、`uvm_reg_access_seq` 等。

**可借鉴**：我们的 test-generator 应该利用 UVM RAL 的内置序列，而不是手动写 APB 调用：

```systemverilog
// 当前: rw.randomize() with { write==1; addr==32'h400; data==32'h0F; };
// 推荐: uvm_reg_hw_reset_seq::type_id::create("reset_seq").start(env.reg_seqr);
```

---

## 7. DVCon 论文 — 相关研究

| 论文 | 年份 | 核心观点 | 可借鉴 |
|------|------|---------|--------|
| **"Automatic UVM Generation from IP-XACT"** — Siemens EDA | 2021 | IP-XACT → UVM env + RAL + test | 先加 IP-XACT 解析 |
| **"LLM-Assisted Verification"** — NVIDIA @ DVCon | 2024 | LLM 生成覆盖率收敛后的补充 test | 我们的 pipeline 就是 LLM 驱动 |
| **"Automated Formal Property Generation from Spec"** — Intel | 2020 | Spec → SVA + formal covers | 增加 `cover property`（已做） |
| **"Python-based UVM: Hybrid Verification"** — AMD/Xilinx | 2023 | UVM + Python BFM 混合验证 | 我们的 BFM + APB driver 已是混合模式 |
| **"Coverage-Driven Test Generation"** — Cadence | 2022 | 覆盖率反馈→定向生成 new test | 我们的 coverage-plan 可以做闭环 |

---

## 优先级建议

### 立刻可做的

| 改进 | 工作量 | 参考 | 收益 |
|------|--------|------|------|
| 生成 UVM RAL 模型 | ~200行 | OpenTitan reggen | 中（使能 UVM 内置寄存器序列） |
| 生成 `csr_excl.json` | ~50行 | OpenTitan | 低（加速 CSR 测试） |
| 输出 FuseSoC `.core` | ~30行 | FuseSoC | 中（EDA 工具无关） |
| 预编译 Makefile `all` | ~10行 | VUnit | 低（一键仿真） |
| `pre_run.sh` 脚本 | ~20行 | VUnit | 中 |

### 下一步可做的

| 改进 | 工作量 | 参考 | 收益 |
|------|--------|------|------|
| cocotb Python TB 生成 | ~500行 | cocotb | 高（Python 验证替代 UVM） |
| Formal-ready 断言 | ~100行 | CORE-V | 中 |
| IP-XACT 输入 | ~300行 | IEEE 1685 | 高 |
| 模板引擎循环支持（per-field） | ~200行 | Mako/Jinja2 | 高 |
