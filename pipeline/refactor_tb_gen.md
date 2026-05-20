# tb_gen 重构设计 v2

> 更新于 2026-05-20

## 设计哲学：管道固定，填充可变

```
                          ┌─────────────┐
                          │   填内容的人   │
                          │  (AI 或 人)   │
                          └──────┬──────┘
                                 │
spec.yml ──→ 中间文件 ──→ 模板 ──→ 生成 RTL / TB / case
  (输入)     (可审可改)   (骨架)   (输出)
```

**流程本身就是管道**，不绑定具体的填充来源。每一层的数据可以来自 AI 生成，也可以来自人手写，管道不管来源，只管消费。

### 分层职责

| 层 | 谁做 | 能否替换 |
|---|------|---------|
| **流程编排**（pro_verify.py --pipeline） | 固定脚本 | ❌ 不改 |
| **中间文件生成**（spec → ip_spec.yml） | AI 或人写 spec.yml，脚本解析 | ✅ 内容可换 |
| **中间文件审查**（port_map.yml 等） | 人审，可手动改 | ✅ 必须给人改 |
| **case 内容填充**（PLUSARGS / 模板 data） | AI 生成 or 手写 | ✅ 按需选 |
| **build 配置**（build_iverilog.py） | AI 或人写 | ✅ 按需选 |
| **手动 case**（cases/manual/） | 人写 | ✅ 人控 |
| **回归清单**（regression_list.py） | tb_gen 自动 + 人手追加 | ✅ 混合 |

### AI 和人的协作关系

```
AI → 写 spec.yml + 生成 test_plan.yml → 人审 → 改 → 跑流水线
                      ↑                   ↓
                  调整 prompt          提交仿真看结果
```

- AI 负责批量生成（spec 解读、feature 分解、case 填充）
- 人负责审查和决策（中间文件要不要改、回归优先级怎么排、手动 case 要不要加）
- 管道不关心数据来源，只关心中间文件格式对不对

### 顶层 Owner

维护这条管道的角色称为**顶层 Owner**。职责：

1. **管流程**：`pro_verify.py --pipeline` 的编排不动，入参填什么由 Owner 决定
2. **管中间文件**：`port_map.yml`/`reg_map.yml`/`test_plan.yml` 在生成后由 Owner 审查，有问题就改
3. **管回归清单**：`regression_list.py` 的 manual_cases 由 Owner 维护，auto_cases 由 tb_gen 维护
4. **管填充来源**：Owner 决定这一轮的数据来自 AI 生成还是手写，管道不改

顶层 Owner 可以是验证工程师，也可以是 AI agent。谁站这个位置谁就负责管道完整性和产出质量。

### IP Owner

填写具体内容的人称为 **IP Owner**。职责：

1. **写 spec.yml**：描述 IP 的接口、寄存器、feature 清单
2. **填 port_map.yml**：DUT 端口名到 TB 信号的映射关系
3. **定义 feature**：列出这个 IP 所有需要验证的功能点
4. **补充手动 case**：对自动生成的回归清单不满意时，在 `cases/manual/` 下追加

IP Owner 和顶层 Owner 可以是同一个人，也可以不是：
- 小项目：验证工程师一人兼两角
- 大项目：顶层 Owner 管流程和审查，多个 IP Owner 各填各的 IP 数据

---

## 流水线全景

```
                    spec.yml（唯一数据源，人类编写）
                        │
                        ▼
              ┌──────────────────┐
              │   spec-analyzer   │  Phase 1: 解析
              └────────┬─────────┘
                       │
                       ▼
              ╔══════════════════════╗
              ║  IP 规范中间表        ║  ◄─── 第一道评审节点
              ║  ip_spec.yml         ║       人审：协议识别对不对？
              ║  (接口/寄存器/feature)║       寄存器地址对吗？
              ╚══════════════════════╝       feature 全不全？
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
   ╔════════════╗ ╔══════════╗ ╔═══════════════╗
   ║ 接口端口表  ║ ║ 寄存器表  ║ ║ 测试点分解表   ║  ◄─── 第二道评审节点
   ║ port_map   ║ ║ reg_map  ║ ║ test_plan    ║       每张表独立可审
   ║ .yml       ║ ║ .yml     ║ ║ .yml          ║       可手动修改后再生成
   ╚═══════╦════╝ ╚═════╦════╝ ╚═══════╦═══════╝
           │             │             │
           ▼             ▼             ▼
   ┌───────────┐  ┌───────────┐  ┌───────────┐
   │ env-      │  │ rtl-gen   │  │ tb_gen    │
   │ builder   │  │ (设计RTL)  │  │ (测试用例) │
   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
         │              │              │
         ▼              ▼              ▼
   ╔══════════════════════════════════════════╗
   ║  回归清单 regression_list.yml             ║  ◄─── 第三道评审节点
   ║  自动生成 + 手动追加的 test 全在这里       ║       人审：回归覆盖全吗？
   ║  ─ feature_a_test                         ║       要不要加几个手动 test？
   ║  ─ feature_b_test                         ║       优先级对不对？
   ║  ─ manual_custom_test  ← 手动加的        ║
   ╚══════════════════════════════════════════╝
```

---

## 中间文件定义

### 文件 1：`ip_spec.yml`（spec-analyzer 产出）

```yaml
# IP 规范中间表
module_name: i2c_controller
version: 1.0

interfaces:
  - name: host_if
    protocol: apb_slave
    direction: slave
    signals:
      - {name: paddr,  width: 12, direction: input}
      - {name: pwrite, width: 1,  direction: input}
      - {name: pwdata, width: 32, direction: input}
      - {name: prdata, width: 32, direction: output}
  - name: i2c_bus
    protocol: i2c
    direction: master
    signals:
      - {name: scl, width: 1, direction: inout}
      - {name: sda, width: 1, direction: inout}

registers:
  - name: ctrl
    address: 0x00
    description: Control register
    fields:
      - {name: enable,    bits: [0],   access: rw, reset: 1}
      - {name: speed_sel, bits: [2:1], access: rw, reset: 0}
  - name: status
    address: 0x04
    fields:
      - {name: busy,  bits: [0], access: ro, reset: 0}
      - {name: done,  bits: [1], access: ro, reset: 0}

features:
  - name: reg_rw
    description: 寄存器读写访问验证
    category: register
  - name: i2c_write
    description: I2C master write 传输
    category: protocol
  - name: i2c_read
    description: I2C master read 传输
    category: protocol
  - name: i2c_arbitration
    description: 多主仲裁
    category: protocol
```

---

### 文件 2：`port_map.yml`（env-builder / rtl-gen 共用）

```yaml
# 端口连接映射表
module: i2c_controller

connections:
  - port: host_if
    protocol: apb_slave
    direction: slave
    dut_prefix: ""
    signals:
      paddr:  {connect: paddr_i, width: 12}
      pwrite: {connect: pwrite_i}
      pwdata: {connect: pwdata_i}
      prdata: {connect: prdata_o}
      psel:   {connect: psel_i}
      penable:{connect: penable_i}
      pready: {connect: pready_o}

  - port: i2c_bus
    protocol: i2c
    direction: master
    signals:
      scl: {connect: scl_io, bidir: true, pull: true}
      sda: {connect: sda_io, bidir: true, pull: true}

  - port: clk_rst
    signals:
      clk: {connect: clk_i, freq: 50MHz}
      rst: {connect: rst_ni, polarity: active_low}
```

用途：
- **env-builder** 读它 → 生成 interface wrapper + DUT 例化
- **rtl-gen** 读它 → 确保生成 RTL 的端口名对上
- 两份输出从同一张表出发，端口名不可能不一致

---

### 文件 3：`reg_map.yml`（rtl-gen + env-builder 共用）

```yaml
# 寄存器映射表 (从 ip_spec.yml 展开)
module: i2c_controller
base_address: 0x4000_0000

registers:
  - name: ctrl
    offset: 0x00
    size: 32
    fields:
      - {name: enable,    bit: 0,   access: rw, reset: 1}
      - {name: speed_sel, bits: [2:1], access: rw, reset: 0}
      - {name: reserved,  bits: [31:3], access: ro, reset: 0}

  - name: status
    offset: 0x04
    size: 32
    fields:
      - {name: busy,  bit: 0, access: ro, reset: 0}
      - {name: done,  bit: 1, access: ro, reset: 0}

  - name: tx_data
    offset: 0x08
    size: 32
    fields:
      - {name: data, bits: [31:0], access: wo, reset: x}

  - name: rx_data
    offset: 0x0C
    size: 32
    fields:
      - {name: data, bits: [31:0], access: ro, reset: 0}
```

用途：RTL 生成寄存器堆 + UVM RAL 模型 + CSR 测试共用同一份数据。

---

### 文件 4：`test_plan.yml`（feature-decomposer 产出）

```yaml
# 验证计划 / 测试点分解表
module: i2c_controller

testpoints:
  - id: REG_RW_001
    feature: reg_rw
    description: CTRL 寄存器 enable 域写 1 读回 1
    stage: v1_smoke
    stimulus: "APB write 0x00=1 → APB read 0x00 → expect[0]=1"
    base_seq: apb_rw_seq

  - id: REG_RW_002
    feature: reg_rw
    description: CTRL 寄存器 speed_sel 域 RMW
    stage: v1_smoke

  - id: I2C_WRITE_001
    feature: i2c_write
    description: 单字节 write，standard speed
    stage: v2_stress
    base_seq: i2c_base_seq

  - id: I2C_WRITE_016
    feature: i2c_write
    description: 16 字节连续 write，standard speed
    stage: v2_stress

  - id: I2C_ARB_001
    feature: i2c_arbitration
    description: 双主竞争总线，优先级仲裁
    stage: v3_signoff
```

用途：tb_gen 的唯一输入。每个 testpoint 生成一条 UVM sequence，继承 `base_seq`。

---

### 文件 5：`regression_list.yml`（自动生成 + 手动追加）

```yaml
# 回归测试清单
module: i2c_controller

auto_tests:
  - {name: ctrl_rw,         id: REG_RW_001, base_seq: apb_rw_seq,     priority: p0}
  - {name: speed_sel_rmw,   id: REG_RW_002, base_seq: apb_rw_seq,     priority: p0}
  - {name: i2c_write_1byte, id: I2C_WRITE_001, base_seq: i2c_base_seq,   priority: p0}
  - {name: i2c_write_16,    id: I2C_WRITE_016, base_seq: i2c_base_seq,   priority: p1}
  - {name: i2c_arbitration, id: I2C_ARB_001, base_seq: i2c_base_seq,   priority: p2}

# 手动追加的 test（不依赖 feature-decomposer）
manual_tests:
  - {name: long_stress_10k,     file: custom/long_stress_test.sv,    priority: p2}
  - {name: sw_fw_compat,        file: custom/sw_fw_compat_test.sv,   priority: p1}
  - {name: power_cycle,         file: custom/power_cycle_test.sv,    priority: p2, disabled: true}
```

要点：
- `auto_tests` 从 `test_plan.yml` 自动生成，每次重新跑 tb_gen 时刷新
- `manual_tests` 人手写，tb_gen 不覆盖，只追加
- 支持 `disabled: true` 暂时跳过某个 test
- regression runner 读这个文件决定跑什么

---

## 评审介入点

| 阶段 | 中间文件 | 人审什么 | 审完怎么改 |
|------|---------|---------|-----------|
| Phase 1 → Phase 2 | `ip_spec.yml` | 协议识别准吗？寄存器地址对吗？feature 全不全？ | 直接改 yml，`--resume` 续跑 |
| Phase 2 → Phase 3 | `port_map.yml` | DUT 端口名对上吗？信号方向对吗？ | 改 yml，env-builder / rtl-gen 重新生成 |
| Phase 2 → Phase 3 | `test_plan.yml` | 测试点覆盖全吗？遗漏 edge case 吗？ | 改 yml，tb_gen 重新生成 |
| Phase 3 → regression | `regression_list.yml` | 回归优先级合理吗？要加手动 test 吗？ | 加 `manual_tests` 段，不改自动部分 |

---

## 文件产出对照

| 中间文件 | 谁生成 | 谁消费 | 可手动修改 |
|---------|--------|--------|:---------:|
| `ip_spec.yml` | spec-analyzer | 全部下游 | ✅ |
| `port_map.yml` | spec-analyzer | env-builder, rtl-gen | ✅ |
| `reg_map.yml` | spec-analyzer | rtl-gen, regmodel-gen | ✅ |
| `test_plan.yml` | feature-decomposer | tb_gen | ✅ |
| `regression_list.yml` | tb_gen | sim-runner, regression-manager | ✅ (manual_tests 段) |

## 可见性与手动操作

### regression_list.yml 是唯一的回归清单入口
- 放在项目根目录的 `verify/` 或 `regression/` 下，用户随时打开看
- 不需要翻仿真日志或数据库才能知道跑哪些 case
- `git diff regression_list.yml` 就能看到回归清单的变化

### 手动加减 case 的方法

```yaml
# regression_list.yml
module: i2c_controller

auto_tests:
  - {name: ctrl_rw,       id: REG_RW_001, base_seq: apb_rw_seq,   priority: p0}
  - {name: i2c_write_1,   id: I2C_WRITE_001, base_seq: i2c_base_seq, priority: p0}

# 手动加：直接写进去，不依赖 feature-decomposer
manual_tests:
  - {name: long_stress_10k, file: custom/long_stress_test.sv, priority: p2}
  - {name: sw_fw_compat,    file: custom/sw_fw_compat_test.sv, priority: p1}

# 临时跳过：改 disabled 就行，不用删
  - {name: power_cycle,     file: custom/power_cycle_test.sv, priority: p2, disabled: true}
```

### tb_gen 每次运行时的行为
1. 读现有 `regression_list.yml`（如果存在）
2. 刷新 `auto_tests` 段（覆盖，从 test_plan.yml 重新生成）
3. 保留 `manual_tests` 段（不覆盖）
4. 写回 `regression_list.yml`

### regression-manager / sim-runner 读什么
- 只读 `regression_list.yml` 的 `auto_tests + manual_tests`
- `disabled: true` 的 test 跳过
- 按 `priority` 排序：p0 每次必跑，p1 回归跑，p2 全量跑

**无任何二进制或 JSON 中间文件**，全是 YAML，人能直接读、直接改、直接 git diff。

---

## 涉及的 skill 改动

| Skill | 改动 |
|-------|------|
| `spec-analyzer` | 产出从散装数据改为输出 3 个标准中间文件 |
| `feature-decomposer` | 输出 `test_plan.yml`，格式对齐 |
| `env-builder` | 从 port_map.yml 读，输出 UVM 骨架 |
| `test-generator` | 重写为 tb_gen，从 test_plan.yml 读，输出 N 条 sequence + regression_list.yml |
| `rtl-gen` | 从 port_map.yml + reg_map.yml 读（已有，对齐格式即可） |
| `regmodel-gen` | 从 reg_map.yml 读（已有，对齐格式） |

---

## Build / Run 彻底分离

### 流程

```
                    build ──────────────────────┐
                    (编译一次，不跑)                │
                         │                       │
                    simv  ← 所有 test 共用         │
                         │                       │
                    ┌────┴────┐                   │
                    ▼         ▼                   ▼
              run_single    run_batch        regression.yml
              (一键单case)   (回归跑全部)    (决定跑哪些)
```

### build（单独脚本）
- 编译 RTL + UVM env → 产出 simv
- 编译一次，后续多个 test 共用同一个 simv
- 不需要每次跑 test 都重新编译
- 输出：`build/simv` + `build/compile.log`

```bash
python build.py --spec i2c_spec.yml --tool iverilog
# 产出 build/simv
```

### run（单独脚本）
- 不编译，只执行已有的 simv
- 通过 UVM plusarg `+UVM_TESTNAME=xxx` 切换 test
- 支持单 case / 多 case / 全量回归三种模式
- 只关心 simv 存在不存在，不关心它怎么编译出来的

```bash
# 单 case
python run.py --simv build/simv --test ctrl_rw

# 多 case
python run.py --simv build/simv --tests ctrl_rw,i2c_write_1,i2c_read_1

# 全量回归（读 regression_list.yml）
python run.py --simv build/simv --regression regression_list.yml

# 按 priority 分级跑
python run.py --simv build/simv --regression regression_list.yml --min-priority p1
```

### 和已有的 tb-compiler / sim-runner 关系
- `tb-compiler` 已经是 build 角色：编译不运行 ✅
- `sim-runner` 已经是 run 角色：运行不编译 ✅
- 需要补充的：
  - `regression_list.yml` 作为入参
  - `--tests` 多 case 逗号分隔
  - `--min-priority` 按优先级过滤
  - build/run 之间通过 `build/simv` 路径契约连接，不共享内存状态

---

## case 和 build 各自独立成 Python 文件

case 描述文件和 build 文件各自独立成 .py 文件，脚本解析后执行。用户自行增删，不用改 YAML 配置。

### 目录结构

`
verify/
├── build_iverilog.py    ← build 配置：编译命令、源文件列表
├── build_vcs.py
├── build_questa.py
│
├── cases/
│   ├── ctrl_rw.py       ← 单条 case 定义
│   ├── i2c_write.py
│   ├── i2c_read.py
│   ├── i2c_arb.py
│   └── manual/           ← 手动加的 case（tb_gen 不覆盖）
│       ├── long_stress.py
│       └── power_cycle.py
│
├── regression_list.py   ← tb_gen 生成 + 用户手动追加
└── run_sim.py           ← 统一入口，读 case 文件提交仿真
`

### build 文件示例（uild_iverilog.py）

`python
"""iverilog 编译配置：可独立运行，也被 run_sim.py 调用"""
SIMULATOR = "iverilog"
OUTPUT    = "build/simv"
SOURCES   = ["rtl/rtl/*.sv", "rtl/verification/env/*.sv"]
INCDIRS    = ["rtl/rtl", "rtl/verification/env"]
DEFINES    = {"CLK_PERIOD": "20"}
COMPILE_CMD = "iverilog -g2012 -o {output} {incflags} {defines} {sources}"
`

### case 文件示例（cases/ctrl_rw.py）

`python
"""CTRL 寄存器读写测试"""
NAME        = "ctrl_rw"
BASE_SEQ    = "apb_rw_seq"
PRIORITY    = "p0"          # p0:必跑 | p1:回归 | p2:全量
STAGE       = "v1_smoke"
DESCRIPTION = "CTRL 寄存器 enable 域写 1 读回 1"
PLUSARGS    = ["+UVM_TESTNAME=ctrl_rw_test", "+CTRL_ENABLE_INIT=1"]
FEATURE_ID  = "REG_RW_001"
`

### regression_list.py（tb_gen 生成 + 用户追加）

`python
"""回归清单：列出本轮要跑的 case"""
# --- 自动生成部分（tb_gen 覆盖刷新）---
auto_cases = ["cases.ctrl_rw", "cases.i2c_write", "cases.i2c_read"]
# --- 手动追加部分（tb_gen 不覆盖）---
manual_cases = ["cases.manual.long_stress", "cases.manual.power_cycle"]
ALL_CASES = auto_cases + manual_cases
`

### run_sim.py 行为

`python
# 1. 读 build 文件 → 编译
from verify.build_iverilog import SOURCES, COMPILE_CMD
# 2. 读 regression_list.py → 加载所有 case
import importlib
for mod_path in regression_list.ALL_CASES:
    mod = importlib.import_module(mod_path)
    # 用 mod.PLUSARGS 提交 +UVM_TESTNAME=xxx 仿真
`

### 用户操作场景

| 想做什么 | 怎么做 |
|---------|--------|
| 加一个新 case | cases/ 下新建 .py，填 NAME / BASE_SEQ / PLUSARGS |
| 加到回归 | 
egression_list.py 的 manual_cases 加一行 |
| 临时跳过 | 注释掉那一行 |
| 换编译工具 | 
un_sim.py --build build_vcs |
| 只跑单个 | python run_sim.py --build build_vcs --case ctrl_rw |
| 只编译不跑 | python build_iverilog.py（独立可执行） |
| 看所有 case | ls cases/*.py |

### 好处
- Python 文件就是 case 定义，import 就行，不解析 YAML
- 增删 case = 增删 .py 文件
- build 独立可执行，也能被 run_sim.py 调用
- 模块路径 cases.ctrl_rw，IDE 能自动补全

---

## 回归结果记录与日志追溯

每轮回归的 PASS/FAIL 状态、日志路径、耗时等信息要结构化记录，支持回溯和对比。

### 目录结构

`
verify/
└── runs/
    ├── run_20260520_093000/        ← 每轮回归一个独立目录，按时间戳命名
    │   ├── regression_list.json    ← 本轮实际跑的 case 列表（含 disabled 过滤后）
    │   ├── results.json            ← 结构化结果：逐 case 的 pass/fail/log/耗时
    │   ├── summary.json            ← 本轮概要：total/passed/failed/覆盖率/耗时
    │   ├── logs/
    │   │   ├── ctrl_rw_s1.log      ← 单 case 单 seed 的完整仿真日志
    │   │   ├── ctrl_rw_s2.log
    │   │   ├── i2c_write_s1.log
    │   │   └── ...
    │   └── vcd/                    ← 可选的波形 dump
    │       └── ctrl_rw.vcd
    │
    ├── run_20260519_170000/
    │   ├── results.json
    │   ├── summary.json
    │   └── logs/...
    │
    └── latest -> run_20260520_093000/    ← 软链指向最新一轮
`

### results.json 格式

`json
{
  "run_id": "run_20260520_093000",
  "timestamp": "2026-05-20T09:30:00+08:00",
  "build": "build_iverilog",
  "simv": "build/simv",
  "cases": [
    {
      "name": "ctrl_rw",
      "status": "PASS",
      "priority": "p0",
      "seed": 1,
      "log": "verify/runs/run_20260520_093000/logs/ctrl_rw_s1.log",
      "elapsed_s": 1.23,
      "uvm_errors": 0,
      "uvm_fatals": 0
    },
    {
      "name": "i2c_write",
      "status": "FAIL",
      "priority": "p0",
      "seed": 1,
      "log": "verify/runs/run_20260520_093000/logs/i2c_write_s1.log",
      "elapsed_s": 2.45,
      "uvm_errors": 2,
      "uvm_fatals": 1,
      "fail_reason": "I2C addr NACK not detected"
    }
  ],
  "summary": {
    "total": 8,
    "passed": 7,
    "failed": 1,
    "skipped": 0,
    "pass_rate": 87.5,
    "total_elapsed_s": 15.2,
    "coverage": {
      "toggle": 89.5,
      "functional": 82.0
    }
  }
}
`

### 日志文件命名约定

`
格式: {case_name}_s{seed}.log
示例: ctrl_rw_s1.log, i2c_write_s1.log, i2c_write_s2.log
`

每条日志的第一段是结构化元信息：

`
# UVM 仿真日志
# case:      ctrl_rw
# seed:      1
# build:     build_iverilog
# simv:      build/simv
# started:   2026-05-20T09:31:00
# completed: 2026-05-20T09:31:03
# result:    PASS
────────────────────────────────────────
[UVM_INFO] ctrl_rw_test.sv:42: starting test
...
`

### 结果对比

`ash
# 比较两轮回归的结果差异
python compare_runs.py \
    --run-a verify/runs/run_20260519_170000 \
    --run-b verify/runs/run_20260520_093000

# 输出：新增 PASS / 新增 FAIL / 回归 FAIL（上次PASS这次FAIL）/ 修复 PASS
`

| 类别 | 含义 |
|------|------|
| 新增 PASS | 上次没跑，这次 PASS |
| 新增 FAIL | 上次没跑，这次 FAIL |
| 回归 FAIL | 上次 PASS，这次 FAIL（**需立即关注**） |
| 修复 PASS | 上次 FAIL，这次 PASS |
| 无变化 | 结果一致 |

### regression-manager 的职责

- 读 
uns/ 目录下的历史结果
- 提供 --compare 对比功能
- 输出趋势数据给 dashboard-gen
- 不关心 case 怎么跑的，只关心结果

### 用户操作场景

| 想做什么 | 怎么做 |
|---------|--------|
| 看最新一轮结果 | cat verify/runs/latest/summary.json |
| 看某个 case 的日志 | 从 results.json 的 log 路径直接打开 |
| 对比两轮 | python compare_runs.py --run-a runs/run_0520 --run-b runs/run_0519 |
| 看回归趋势 | dashboard-gen 读多个 summary.json 出趋势图 |
