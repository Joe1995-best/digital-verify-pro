# digital-verify-pro 全面审查 + 改进方案

> 综合 full-IP 覆盖率结果、STANDARDS.md 对标、LEARNED.md 参考项目分析

---

## 一、现状诊断

### 覆盖率健康卡

| IP | Toggle | Stuck | 测试数 | 状态 |
|---|---|:---:|---:|:----:|
| OT DMA (手写) | 93.8% | 0 | 22/22 | ✅ 收敛 |
| I2C (生成RTL) | 96.3% | 0 | 寄存器级 | ⚠️ 只有reg bank |
| ALU4 | 90.9% | 0 | 简单 | ✅ 够用 |
| Dual Port Stack | 80.0% | **5** | 基础 | ❌ 需要补 |

### 覆盖率不能掩盖的问题

高 toggle % ≠ 好验证。核心架构问题：

1. **I2C 96.3% 但 RTL 没有 I2C 协议逻辑** — RTL 生成器只产生了寄存器库，没有 I2C FSM/bit-bang 引擎。覆盖率漂亮但没有测到真正该测的东西
2. **Dual Port Stack 80.0% + 5 stuck** — 双口栈的高位数据线和 cmd 通道活动不足，说明测试场景覆盖不够
3. **无 functional coverage 闭环** — 只有 toggle analysis，没有功能覆盖率驱动的测试迭代
4. **无统一回归** — 每个 IP 各自为战，OT DMA 用 VRF，I2C 用自定义 TB，没有自动化回归流程

---

## 二、对标 OpenTitan 的核心差距

### 差距 1：寄存器描述 — 缺 hwaccess 和跨域一致性

OpenTitan 的 HJSON register 描述每个 field 有 `hwaccess`（HW 侧的读写权限）：

```hjson
// OpenTitan 方式
{ bits: "0", name: "i2c_en",
  access: "rw",        // SW view
  hwaccess: "hrw",     // HW view — HRW/HRO/HWO
  hwqe: "true"         // HW write-queue enable
}
```

而我们只有 `access: "rw"`（SW view），缺少 HW view。这直接导致 RTL 生成器不知道该给哪个信号赋值：

| 你在 spec 写的 | 目前只做了 | 缺了什么 |
|---|---|---:|
| `i2c_en: rw` | SW 可以读写 | HW 应该读这个值来使能 I2C |
| `start: wo` | SW 写触发 | HW 应该通过写这个 bit 发起 START |
| `rx_data: ro` | SW 只读 | HW 应该写入数据 |

**建议**：
- spec field 加 `hwaccess` 标记（hrw/hro/hwo）
- field 加 `hwqe`（hw write-enable）和 `swacc`（sw 是否可读回）
- 根据 hwaccess 信息驱动 RTL 生成：hrw=生成赋值的 line，hro=hw 只读的 memory 元素，etc.

### 差距 2：UVM 环境 — 缺 check_phase / do_print / 顶层 env_cfg

对比 IEEE 1800.2-2020：

| 要求 | OpenTitan | 我们 | 修复 |
|---|---|---|---|
| `check_phase` 报告 | ✅ | ❌ | env-builder生成reporting logic |
| `do_print`/`do_compare` | ✅ | ❌ | 模板修改 |
| `env_cfg.sv` | ✅ | ❌ | 每个 IP 生成 env_cfg |
| virtual sequencer | ✅ | ❌ | 多个 agent 需要统筹 |
| sequence library | ✅ | ❌ | 回归时自动注册 |

### 差距 3：RTL 生成 — I2C FSM 缺失

RTL 生成器（`run_rtl_gen.py`）目前是 "standard mode" — 只产生 reg bank + 简单数据 path，没有协议 FSM。

对比 OpenTitan 的 `top_gen.py`，它从 HJSON 的 `interrupts`、`alert_list`、`wakeups` 这些硬件属性生成完整的中断控制器、alert handler、wakeup 逻辑。

**问题根源**：spec 里没有 FSM 定义，RTL 生成器不知道要生成什么状态机。

**建议**：
- spec YAML 增加 `fsm` 节（参考 ot_dma_spec.yml 的现有格式）
- 扩展 `fsm_templates.py` 使其支持多种协议模板
- 对 I2C：增加 `bit_bang` 模式（SCL/SDA 时序生成）

### 差距 4：覆盖率 — 无 functional coverage + 无闭环

当前 coverage pipeline:
```
仿真 → VCD → toggle analysis → report
```

OpenTitan / 行业标准的 coverage 闭环:
```
仿真 → VCD + functional covergroup → toggle + func coverage → gaps → 定向生成新 test → 重跑
```

**我们缺的闭环环节**：
1. ❌ 没有 functional coverpoints 在 RTL/sim 中实例化
2. ❌ 覆盖缺口没有自动驱动 test generator 生成定向测试
3. ❌ toggle gaps 缺少分级过滤（哪些是 RTL 设计限制不可避免的？）

### 差距 5：回归自动化 — 无统一入口

OpenTitan 用 Makefile + FuseSoC，所有 IP 统一入口：
```bash
# OpenTitan
$REPO_TOP/util/dvsim/dvsim.py hw/ip/gpio/dv/gpio_sim_cfg.hjson
```

我们目前：手动 cd 到各目录，手动挑 run_*.py 跑。

**建议**：
- `pro_verify.py` 增加 `--regression` 子命令，列出所有 spec 并批量跑
- 输出 JSON 格式的回归结果
- 自动生成 `coverage_convergence_report.md` 合并报告

---

## 三、对标 analog-agents 的核心差距

从 5/13 的 analog-agents 研究来看，核心借鉴点：

### 差距 6：缺 effort level 概念

analog-agents 用 `effort` 控制验证深度：

| Effort | 含义 | 我们的对应物 |
|--------|------|-------------|
| L1 | 编译 + 语法检查 | `--check-only` ✅ |
| L2 | 基础回归 | 手动, 无统一入口 ❌ |
| L3 | 全功能覆盖 | 无协议级覆盖 ❌ |
| L4 | 最坏 case + corner | 无 ❌ |

**建议**：
- `pro_verify.py --effort L2 --pipeline i2c_spec.yml`：快速回归
- `pro_verify.py --effort L4 --pipeline i2c_spec.yml`：全覆盖 + 形式验证

### 差距 7：缺 structured wiki / knowledge base

analog-agents 有完善的 wiki（patterns/lessons/protocols），我们虽然有 `wiki/` 目录，但内容稀少，而且"问题-对策"的结构没有建立。

**建议**：
- 覆盖率缺口自动生成 "known issue" 条目
- 每次验证跑完自动追加 lessons learned 到 wiki
- 将 STANDARDS.md 拆成 wiki 中的 actionable 条目

---

## 四、从覆盖率数据看具体改进

### 1. OT DMA (93.8%) — 提升空间有限

| 缺口 | 原因 | 建议 |
|---|---|---|
| src/dst_addr_hi_q | 32bit地址只用低16位 | 加高位地址测试 |
| error_code_q/en_error_q | 只触发了一次error | 加多种error注入 |
| stop_q/incr_en_q | 只有2bit翻转 | 加多配置组合 |

**建议**：新增 3-4 个测试：高位地址、多级 error、stop + incr 组合。

### 2. I2C (96.3%) — 假覆盖率

| 信号 | 问题 |
|---|---|
| rx_data_reg_q / intr_status_reg_q | RO 寄存器读一次就够, toggle 不可能满 |
| status_reg_q | 复位 0x36，没变化 — 因为 I2C FSM 不存在 |
| gpio_* / raw_irq / irq_clear | RTL 生成器遗留的死信号 |

**真正的覆盖率应该是**：当 I2C FSM 集成后，status 在 idle/start/transmit/stop 各状态间变化，覆盖 status_reg 的 busy/tx_full/rx_full/arb_lost bits。

### 3. Dual Port Stack (80.0%) — 最需要补

5 个 stuck 信号 + 13 个 DUT gap，说明测试场景过于简单。

**建议**：
- 加双口同时读写测试（现在可能只测了单口读写）
- 加 cmd/data 的随机组合测试
- 加 depth 压力测试（满 depth push/pop）

---

## 五、分级改进计划

### 🟢 P0（立刻，< 100 行改动）

| 改进 | 做什么 | 文件 | 预计时间 |
|---|---|---|---|
| spec 加 hwaccess | field 加 `hwaccess: "hrw"` + `swacc: "rw"` | `template_engine.py` | 30min |
| 生成 env_cfg.sv | 空 env_cfg 模板，打包 env 需要的 config | `run_env_builder.py` + 模板 | 30min |
| 加 `check_phase` | 在 env 的 check_phase 打印报告 | 环境模板 | 15min |
| 生成回归 manifest | `--list-tests` 输出所有可用测试的 JSON 清单 | `pro_verify.py` | 15min |
| 统一回归子命令 | `pro_verify.py --regression` | `pro_verify.py` | 1h |
| dual_port_stack 加强 | 加 3-5 个新的组合测试 | `verify_pro_dual_port_stack/` | 30min |

### 🟡 P1（重要，1-3 天）

| 改进 | 做什么 | 参考 | 预计时间 |
|---|---|---|---|
| I2C FSM 生成 | spec 增加 fsm 节，扩展 fsm_templates.py 产生 I2C 协议引擎 | `fsm_templates.py` | 1-2天 |
| 覆盖率闭环 | CoverageEngine 的 gap 列表→定向测试生成→run_test_generator.py | coverage_engine + test generator | 1天 |
| 功能覆盖点实例化 | 在生成的 env 中实例化 functional covergroup | 环境模板 + coverage template | 半天 |
| IP-XACT 输入解析 | 解析 IEEE 1685 XML → 内部 spec_data 格式 | 新文件 `ipxact_parser.py` | 1天 |

### 🔴 P2（长期，3-7 天）

| 改进 | 做什么 | 参考 | 预计时间 |
|---|---|---|---|
| cocotb TB 生成 | 为每个 IP 生成 python cocotb testbench | cocotb | 3天 |
| formal-ready 断言 | 所有 SVA 加上 $assert/$cover + formal 兼容写法 | CORE-V | 2天 |
| FuseSoC .core 输出 | 每个 IP 输出 `.core` 文件 | FuseSoC | 半天 |
| 分层 effort 模式 | L1-L4 effort levels | analog-agents | 1天 |
| wiki 自动更新 | 每次验证跑完 append lessons | 新脚本 | 半天 |

---

## 六、总结

### 当前真正该做的事情 TOP 3

1. **🔴 I2C FSM** — 覆盖率 96.3% 是假象，RTL 没有 I2C 协议引擎就是废的。花最多的时间在这里
2. **🔴 覆盖率闭环** — 跑覆盖率却没有反馈到测试生成，等于在黑暗中飞行
3. **🟡 Dual Port Stack 补测** — 5 个 stuck signal 不正常，直接表明测试覆盖面不足

### 与 OpenTitan 的定位差异

| 维度 | OpenTitan | digital-verify-pro |
|---|---|---|
| 目标 | 工业级芯片 sign-off | 快速原型 + 验证框架 |
| 生成范围 | RTL + UVM env + DV 全部 | RTL + UVM env + 基础覆盖 |
| 输入 | HJSON (强制一致性) | YAML (灵活但松) |
| FSM 生成 | 手写（自动仅限 CSR） | **可以自动** — 这是我们的差异化优势 |
| 覆盖率 | UVM covergroups + toggle + formal | toggle only |

**差异化方向**：我们最适合做的是 **FSM 自动生成 + 覆盖率闭环**，这两个是 OpenTitan 不做/做不到的。

---

*生成时间: 2026-05-15*
*基于: coverage_all_ips.json, STANDARDS.md, LEARNED.md, PRO_SKILL.md*
