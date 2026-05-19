# RTL Review Checklist (Supplement)

---

## S7: CDC/RDC — 时钟域交叉 / 复位域交叉

### S7.1 CDC 基础

- [ ] **跨时钟域信号识别**: 每个从 clk_A 到 clk_B 的信号已标注
  ```verilog
  // CDC: clk_i -> clk_j
  // 使用 2-flop synchronizer
  ```
- [ ] **单 bit 同步器**: 慢到快/快到慢的单 bit 用 2-flop 同步器
  ```verilog
  always_ff @(posedge clk_dst or negedge rstn) begin
    if (!rstn) begin sync1 <= 1'b0; sync2 <= 1'b0; end
    else begin sync1 <= src_sig; sync2 <= sync1; end
  end
  assign dst_sig = sync2;
  ```
- [ ] **多 bit 同步器**: 多位信号跨时钟域用 FIFO 或 handshake 协议
  - 不能简单用 2-flop（每 bit 同步延迟不同 → 数据损坏）
  - 使用 `simple_fifo` 或 `async_fifo`，两时钟之间通过空/满信号同步
- [ ] **脉冲同步检测**: 快时钟到慢时钟的脉冲需展宽后再同步
  ```verilog
  // 脉冲展宽：快域脉冲 → 慢域电平
  always_ff @(posedge clk_fast) pulse_ff <= pulse_in | (pulse_ff & ~sync_ack);
  // 慢域同步 + 边沿检测恢复脉冲
  always_ff @(posedge clk_slow) sync <= pulse_ff_sync2;  // 2-flop
  assign pulse_out = sync & ~sync_d1;
  ```
- [ ] **FIFO 空满跨时钟**: async_fifo 的 `empty`/`full` 用 gray code 指针 + 2-flop 同步
  - 二进制指针跨时钟不可接受（多 bit 同时翻转风险）

### S7.2 CDC 验证

- [ ] **CDC 断言存在**: 每个同步器输出口有断言检测 metastability 不会导致功能错误
  ```verilog
  // CDC_DATA_OK: 同步后的数据与源域一致（仅对 FIFO/handshake）
  ```
- [ ] **所有 CDC 路径形式验证或动态仿真**: sby 用 `--cdc` 模式验证同步器正确性
- [ ] **X-prop 检查**: 仿真开启 `+vcs+initreg+random` 或等价选项验证 CDC 对 X 的容忍

### S7.3 复位域交叉

- [ ] **异步复位同步释放**: 每个异步复位有同步释放电路
  ```verilog
  always_ff @(posedge clk or negedege rstn) begin
    if (!rstn) begin rst_sync1 <= 1'b0; rst_sync2 <= 1'b0; end
    else begin rst_sync1 <= 1'b1; rst_sync2 <= rst_sync1; end
  end
  assign rst_synced = rst_sync2;  // de-asserted synchronously
  ```
- [ ] **多复位域交互**: 不同复位域之间的逻辑不能直接连接（需同步器）
- [ ] **复位树深度**: 复位信号的 fanout 在可接受范围内（>1000 flops 需插 buffer）

### S7.4 CDC 设计错误模式

| 模式 | 现象 | 检查方法 |
|------|------|----------|
| 没同步直接连线 | X 传播、功能随机失败 | grep 跨域信号 |
| 多 bit 用 2-flop | 数据损坏 | 审查多 bit 同步器 |
| 脉冲丢失 | 中断丢失 | 检查快<->慢路径 |
| FIFO 空满错误 | FIFO under/overflow | 验证 gray code + sync |
| 异步复位无效 | 复位不完全 | 检查同步释放电路 |

---

## S8: 形式验证检查清单

适用于 `formal_check_gen.py` + SymbiYosys (sby) 的形式验证流程。

### S8.1 Property 完整性

- [ ] **所有接口协议属性**: APB 读/写时序、握手机制形式化
  ```verilog
  // 例: APB 写 — penable 只在 psel 之后置位
  always @(posedge clk) 
    if ($past(psel) && $past(penable)) assert(pready || $past(pready));
  ```
- [ ] **寄存器读写属性**: 每个 RW 寄存器写读一致性、RO 寄存器写不改变值
- [ ] **FSM reachability**: 每个状态可到达（从 reset 到所有状态的路径存在）
- [ ] **无死锁**: FSM 不会卡在非 IDLE 状态无限期（每个状态有退出条件）
- [ ] **中断属性**: 每个中断源能触发出 intr_o，且 W1C 能清除

### S8.2 sby 配置检查

- [ ] **证明深度合理**: `depth` 参数 >= FSM 状态数 × 2（确保 reachability 证明完整）
- [ ] **BMC vs unbounded**: 关键属性用 `prove`（unbounded），次要用 `bmc -k <depth>`
- [ ] **假设合理**: `assume` 没有过度约束（不把 bug 假设掉）
- [ ] **Cover 属性**: 每个新的 FSM 状态有 cover 语句验证可达性

### S8.3 形式验证流程

```
1. formal_check_gen → assert.sv + config.sby
2. sby -f config.sby        → PASS/FAIL
3. 分析 FAIL: 
   ├─ 假失败 → 修正 assume/assert
   └─ 真 bug → 修复 RTL
4. sby -f config.sby --cover → 覆盖率报告
5. 签收: 所有 prove PASS + 所有 cover hit
```

### S8.4 形式验证签收标准

| 指标 | 目标 | 说明 |
|------|:----:|------|
| prove PASS | 100% | 所有 unbounded proof 通过 |
| bmc PASS | 100% | 深度内 bounded model check 通过 |
| cover hit | 100% | 每个 cover 属性被触发 |
| 证明时间 | < 30min | 单 sby 运行时间 |
| 引擎 | sby 默认 | 可接受 `abc`/`superprove`/`btor` 任意引擎 |

---

## S9: Review → Checklist 联动

review skill 的输出自动生成 checklist 追踪条目。

### S9.1 Review 发现分类

| Review 严重性 | Checklist 影响 | 动作 |
|:-------------:|:--------------:|------|
| 🔴 CRITICAL | Phase 4 (SIM) Blocker | 修复 RTL 后重新仿真 |
| 🟡 HIGH | Phase 5 (CCR) 影响 | 评估是否影响覆盖度收敛 |
| 🟢 MEDIUM | Phase 2 (TPR) 追踪 | 是否需要增加测试 |
| ℹ️ INFO | Phase 6 (SO) 记录 | 记录为已知 issue |

### S9.2 自动化集成

```bash
# 1. 跑 review
python run.py --dir output_i2c/rtl/rtl/ --output review_report.json --json

# 2. review → bug-list.md
python tools/review_to_checklist.py \
  --review review_report.json \
  --output bug-list.md \
  --checklist verification_checklist.md
```

### S9.3 Bug List 模板 (bug-list.md)

每个 Review CRITICAL 发现自动生成为：

| ID | 类型 | 规则 | 描述 | 文件 | 行 | Checklist Phase | 修复状态 |
|----|:----:|:----:|------|:----:|:--:|:--------------:|:--------:|
| BUG-001 | RTL | FIFO_RD_STUCK | RX FIFO rd_en=0，数据写入但不读 | i2c.sv | 109 | SIM (Phase 4) | ✅ 已修复 |
| BUG-002 | RTL | HW_PORT_ZOMBIE | hw_rx_data_i 未连接覆盖 rx_data_reg | i2c_regs.sv | 82 | RTL-GEN (Ph3) | ✅ 已修复 |
| BUG-003 | ARCH | W1C_ON_WIRE | intr_status 是 wire，W1C 无效 | i2c_regs.sv | 104 | CCR (Phase 5) | ⏳ 待修复 |

### S9.4 闭环流程

```
Review → CRITICAL发现 → 修复RTL → 重新仿真 → Review验证修复 → Checklist更新
  🔴                              ✅                              ✅
```

- [ ] 每次 review 触发后更新 `bug-list.md`
- [ ] 每个 CRITICAL 有对应修复 commit
- [ ] 签收前所有 CRITICAL 已关闭（或明确标记 WONTFIX）
- [ ] 签收前所有 HIGH 已评估（CCR 影响 > 5% 必须修复）
