# Verification Sign-Off Checklist

参考 OpenTitan IP 验证签收流程，结合 digital-verify-pro 框架定制。

---

## Phase 1: Spec Completeness Review (DSR)

### 1.1 Interface Completeness

- [ ] **APB 接口**: psel, penable, pwrite, paddr, pwdata, prdata, pready, pslverr — 全部声明
- [ ] **时钟/复位**: clk, rst_n 正确连接
- [ ] **中断输出**: 所有 intr_*_o 信号声明并描述触发条件
- [ ] **Host/DMA 接口**: addr_o, req_o, we_o, wdata_o, gnt_i, rdata_i, rvalid_i, err_i — 全部声明
- [ ] **地址位宽**: paddr 位宽在顶层和寄存器模块一致
- [ ] **数据位宽**: 所有数据总线 32-bit，与 spec 一致

### 1.2 寄存器完整性

- [ ] **寄存器列表**: spec 中声明的所有寄存器都在 RTL 中实现
- [ ] **地址偏移**: 每个寄存器偏移地址与 spec 一致（无重叠、无空隙）
- [ ] **字段定义**: 每个寄存器的 field（位域）声明了 access type（RW/RO/W1C/WO）
- [ ] **复位值**: 所有寄存器复位值与 spec 一致
- [ ] **保留位**: 保留字段设为 RO/0，读回 0，写忽略
- [ ] **PSLVERR**: 保留地址范围（>= 0x50）返回 PSLVERR

### 1.3 FSM 完整性

- [ ] **状态枚举**: 所有状态已命名并枚举
- [ ] **状态跳转**: spec 中描述的所有状态跳转在 RTL 中实现
- [ ] **默认/兜底**: default case 定义了状态保持行为（无 latch）
- [ ] **复位状态**: 复位后回到 IDLE/INIT

---

## Phase 2: Feature Extraction & Testplan Mapping (TPR)

### 2.1 功能点提取

每个功能点需标注: `[功能ID] [描述] [Spec章节] [测试覆盖状态]`

| ID | 功能点 | Spec来源 | 测试覆盖 | 状态 |
|----|--------|----------|----------|:----:|
| F1 | 寄存器复位值 | `registers[].reset` | reg_test | ✅ |
| F2 | 寄存器 RW 操作 | `registers[].fields[].access == "rw"` | reg_test | ✅ |
| F3 | 保留地址 PSLVERR | `reserved_ranges` | reg_test | ✅ |
| F4 | DMA 单字传输 | `fsm.dma` | single_word_test | ✅ |
| F5 | DMA 多字传输 | `fsm.dma` | multi_word_test | ✅ |
| F6 | DMA 传输宽度 | `transfer_width` | byte/half_word/word | ✅ |
| F7 | 块中断 (chunk) | `chunk_data_size` | chunk_test | ✅ |
| F8 | 错误注入 | `host_err_i` | error_test | ✅ |
| F9 | DMA 停机 | `stop_q` | stop_test | ✅ |
| F10 | 地址增量 | `incr_config` | incr_test | ✅ |
| ... | ... | ... | ... | |

### 2.2 Feature-to-Test Matrix

```
                 | reg  | single| multi | byte |half|chunk|error|stop|incr|multi|
-----------------|------|-------|-------|------|----|-----|-----|----|----|-----|
寄存器复位值      |  ✅  |       |       |      |    |     |     |    |    |     |
RW 操作          |  ✅  |       |       |      |    |     |     |    |    |     |
保留地址 PSLVERR  |  ✅  |       |       |      |    |     |     |    |    |     |
单字传输         |      |   ✅  |       |      |    |     |     |    |    |     |
多字传输         |      |       |   ✅  |      |    |     |     |    |    |     |
字节宽度传输      |      |       |       |  ✅  |    |     |     |    |    |     |
半字宽度传输      |      |       |       |      | ✅ |     |     |    |    |     |
块中断          |      |       |       |      |    |  ✅  |     |    |    |     |
错误检测          |      |       |       |      |    |     |  ✅  |    |    |     |
DMA 停机         |      |       |       |      |    |     |     | ✅  |    |     |
增量配置         |      |       |       |      |    |     |     |    | ✅  |     |
多配置传输        |      |       |       |      |    |     |     |    |    |  ✅ |
```

- [ ] **所有功能点至少被一个测试覆盖**
- [ ] **所有功能点被测试的 observability 点确认**（assertion / scoreboard / direct check）
- [ ] **边界/异常功能点有独立测试**（错误注入、保留地址、max-size 传输）

### 2.3 约束随机测试计划

适用于 VRF (Verification Random Framework) 或 UVM 的约束随机验证。

#### 2.3.1 随机变量

| 变量 | 分布 | 约束 | 覆盖目标 |
|------|:----:|------|:--------:|
| `data_size` | uniform[1, 256] | <= max_fifo_depth × 2 | 边界值 1, max, max+1 |
| `transfer_width` | weighted[byte=25%, half=25%, word=50%] | 3-bit encoding | 所有 3 种宽度 |
| `src_addr_lo` | uniform[0, 2^32-1] | 无 | 翻转换位 |
| `dst_addr_lo` | uniform[0, 2^32-1] | `!= src_addr` | 地址变化 |
| `err_inject` | 5% probability | `host_err_i` 脉冲宽度 1 cycle | error 路径全覆盖 |
| `stop_seq` | 10% mid-transfer | 在 active=1 时触发 | stop_q 功能 |

- [ ] **所有随机变量有约束**: 不产生非法事务（地址越界、长度溢出）
- [ ] **随机种子可复现**: `+ntb_random_seed=<N>` 指定种子
- [ ] **种子单调性**: 不同种子不产生死锁或超时
- [ ] **覆盖率驱动**: 收集到的缺口自动调整随机分布（反馈回路）

#### 2.3.2 随机测试类型

| 测试 | 描述 | 覆盖缺口 |
|------|------|----------|
| `random_smoke` | 随机寄存器配置 + 随机 DMA 传输 | 基本功能 |
| `random_stress` | 1000+ 随机事务，背靠背无间隔 | 深度覆盖 |
| `random_error` | 随机注入 host_err、pslverr | 错误路径 |
| `random_width_mix` | 交替 byte/half/word 传输 | 宽度切换 |
| `random_gap_targeted` | 基于 coverage gaps.json 的靶向随机测试 | 缺口收敛 |

- [ ] **random_smoke 每次回归必跑**: 5 种子
- [ ] **random_stress 每周回归**: 100 种子
- [ ] **覆盖率缺口 ≥10% 时触发 random_gap_targeted**

---

## Phase 3: RTL Generation Review (RTL-GEN)

### 3.1 生成代码标准

- [ ] **无 `unique case`** — 改为 `case`（iverilog 11 兼容）
- [ ] **无 `inside` 操作符** — 展开为 `||` 表达式
- [ ] **无 `always_comb` 读取 always_ff 变量** — 统一 always_ff blocking 赋值
- [ ] **error_flag 持久化** — `error_flag_q <= error_flag_q` 保持，不每周期清 0
- [ ] **中断 auto-set** — `dma_done_intr_q <= 1'b1` 在完成时自动置位
- [ ] **W1C 中断清除** — APB 写 INTR_STATE 清除

### 3.2 功能正确性

- [ ] **FSM 状态数与 spec 一致**
- [ ] **中断输出门控**: `intr_o = intr_q & en_q`
- [ ] **状态寄存器读回**: `DMA_STATUS.busy/active/done/error` 映射正确
- [ ] **寄存器位域映射**: 读回位域位置与 spec 一致
- [ ] **W1C 清除确认**: 写 INTR_STATE 的位对应清除正确的中断状态寄存器

### 3.3 覆盖友好设计

- [ ] **error_flag 不清零:** 设置为时不自动清零（除非复位或 SW 写入）
- [ ] **中断状态 auto-set:** FSM 动作中自动置位
- [ ] **done 持久化:** DMA 完成后 done 位保持，不被循环覆盖
- [ ] **计数器:** word_cnt 在 chunk 边界复位

---

## Phase 4: Simulation Results Review (SIM)

### 4.1 功能测试

- [ ] **所有测试 PASS**, `FAIL=0`
- [ ] **测试覆盖边界条件:**
  - [ ] 单字传输（最小）
  - [ ] 多字传输（中等）
  - [ ] 大传输（> 最大 FIFO 深度）
  - [ ] 字节/半字/字宽度
  - [ ] 错误响应
  - [ ] 中途停机
- [ ] **没有意外 TIMEOUT**

### 4.2 Assertion 检查

- [ ] **APB 协议断言**: 无 psel 时无 penable，地址在访问中不变
  - 结果: _________
- [ ] **FSM 断言**: 状态未 stall，无非法状态值
  - 结果: _________
- [ ] **DMA 断言**: host_req 未超时，done 和 error 不同时置位
  - 结果: _________

### 4.3 回归环境

- [ ] **回归流水线可重复**: `run_dma_convergence.py` 一键运行
- [ ] **回归时间 < 2min**

---

## Phase 5: Coverage Closure (CCR)

### 5.1 Toggle Coverage

| 指标 | 目标 | 当前 |
|------|:----:|:----:|
| Toggle Coverage | > 90% | ___% |
| 全翻转信号比例 | > 80% | ___% |
| Toggle Intensity | > 90% | ___% |

- [ ] **所有`*_q`寄存器至少翻转一次**
- [ ] **FSM 状态机所有状态被访问**
- [ ] **Interrupt 路径全覆盖**（done/chunk/error 从置位到输出）

### 5.2 未覆盖信号分析

每个 stuck 信号需标注:

| 信号名 | 原因 | 是否需要修复 | 追踪 |
|--------|------|:-----------:|:----:|
| error_code_q[3:0] | 只有全 0 和 2 | 低优先级 | ISSUE-001 |
| src_addr_hi_q | 32-bit 地址不用 hi | 无需修复 | WONTFIX |
| ... | ... | ... | ... |

- [ ] **所有 stuck 信号已分析原因**
- [ ] **RTL 功能未实现导致的 gap** 有追踪记录
- [ ] **测试不充分导致的 gap** 有新增测试计划

### 5.3 收敛标准

- [ ] **toggle 覆盖度 > 90%** 或 **已收敛**（剩余 gap 全是 RTL 未实现功能）
- [ ] **收敛曲线已平**: 最近 3 次迭代覆盖率提升 < 1%
- [ ] **收敛报告已生成**: `convergence_report.md`

---

## Phase 6: Sign-Off (SO)

### 6.1 签收标准

- [ ] **所有功能点已测试** (Phase 2)
- [ ] **覆盖度已收敛** (Phase 5)
- [ ] **回归 100% PASS** (Phase 4)
- [ ] **Spec 与 RTL 一致** (Phase 1 + 3)
- [ ] **断言 0 失败** (Phase 4)
- [ ] **所有 gap 已分析** (Phase 5)

### 6.2 签收记录

| 项目 | 状态 |
|------|:----:|
| IP 名称 | |
| Spec 版本 | |
| RTL 版本 | |
| 验证工程师 | |
| 设计工程师 | |
| 签收日期 | 2026-05-14 |

### 6.3 已知 Issue 追踪

| ID | 描述 | 影响 | 优先级 | 状态 |
|----|------|:----:|:------:|:----:|
|  |  | | | |

---

## 各阶段 Check 方法

### DSR — Spec Review
```bash
# 对比 spec 寄存器列表与 RTL 信号
python tools/check_regs_vs_rtl.py --spec spec.yml --rtl rtl/
```

### TPR — Feature-to-Test Mapping
```bash
# 自动提取 spec 功能点并检查测试覆盖
python pipeline/check_feature_coverage.py --spec spec.yml --tests tests/
```

### CCR — Coverage Analysis
```bash
# 一键运行收敛流水线
python run_dma_convergence.py
```


### 5.4 Review-Checklist 联动

review skill 发现的每个 CRITICAL/HIGH 问题关联到 Checklist Phase:

| Review 规则 | 关联 Phase | 动作 |
|:-----------|:----------:|------|
| FIFO_RD_STUCK | Phase 4 (SIM) | 修复后重新仿真 |
| FIFO_PORT_UNCONNECTED | Phase 3 (RTL-GEN) | 连接端口后重跑 |
| HW_PORT_ZOMBIE | Phase 3 (RTL-GEN) | 移除僵尸输入 |
| DUAL_ASSIGN_OVERRIDE | Phase 1 (DSR) + Phase 3 | 合并赋值 |
| W1C_ON_WIRE | Phase 5 (CCR) | 评估中断覆盖影响 |
| NO_TOGGLE_GAP | Phase 5 (CCR) | 加入 gap 追踪 |

`ash
# Review 后自动更新 Checklist
python tools/review_to_checklist.py \
  --review output/review_report.json \
  --checklist checklists/verification_checklist.md \
  --update
`


---

## Appendix: OpenTitan Alignment

See checklists/opentitan_alignment.md for the full OpenTitan alignment supplement.

### Cross-Reference Table

| Phase | OpenTitan Practice | Doc Ref |
|:-----|:-------------------|:--------|
| Phase 1 (DSR) | CSR spec completeness | OT-S1 |
| Phase 2 (TPR) | Feature-to-test mapping + per-feature coverage | OT-S5 |
| Phase 2 (TPR) | Fault injection test plan | OT-S6 |
| Phase 2 (TPR) | DV Plan document | OT-S9 |
| Phase 3 (RTL-GEN) | UVM RAL single-source consistency | OT-S4 |
| Phase 3 (RTL-GEN) | Verilator lint | OT-S3 |
| Phase 4 (SIM) | Multi-seed regression | OT-S2 |
| Phase 4 (SIM) | CSR auto-test generation | OT-S1 |
| Phase 5 (CCR) | Code coverage merge across runs | OT-S8 |
| Phase 5 (CCR) | X-propagation formal analysis | OT-S7 |
| Phase 6 (SO) | Signed-off release tag | OT-S10 |
