# RTL Review Checklist [COMMON]

基于验证经验归纳的 RTL 代码审查清单，确保可综合、可仿真、覆盖友好。

`[COMMON]` = 通用检查项，适用于所有 IP 模块。
`[MODULE: xxx]` = 仅特定模块（如 dma/i2c/spi）适用的检查项或示例。

---

## S1: 可综合风格 [COMMON]

### S1.1 always_ff 规范

- [ ] **统一 `always_ff`**: FSM next-state + actions 在同一个 `always_ff` 块内
  - next-state 用 blocking `=` 立即计算
  - state 更新用 NBA `<=`
  - actions 用 NBA `<=` 基于当前 `state_q`
  ```verilog
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      // reset
    end else begin
      // 1. Compute next state (blocking)
      state_d = state_q;
      case (state_q) ... endcase
      
      // 2. Apply state update (NBA)
      state_q <= state_d;
      
      // 3. Actions (NBA, based on current state_q)
      case (state_q) ... endcase
    end
  end
  ```

- [ ] **无 `always_comb` 读取 always_ff 输出变量**: iverilog 11 中 `always_comb` 读 `logic` 变量可能通过 NBA 延迟一周期
- [ ] **无 `assign` 函数调用组合逻辑**（如果函数读取注册变量）：`assign state_d = f(state_q)` 只对 `state_q` 变化敏感，不响应函数体内其他变量
- [ ] **无 latch**: 每个 `always_comb` 或组合 `always @*` 在所有 code path 都赋值

### S1.2 时序收敛

- [ ] **FSM 不会自锁**: 每个状态要么无条件退出，要么有超时/异常路径
- [ ] **一站信号的 `ready` 不可组合回路**: `ready` 用 `assign = 1'b1` 或在 `always_ff` 内用 NBA
- [ ] **无组合反馈**: `assign a = b; assign b = a;` 类环形依赖

---

## S2: iverilog 11 兼容 [COMMON]

### S2.1 语法子集

- [ ] **无 `inside` 操作符**: `state inside {A, B}` → `(state == A) || (state == B)`
- [ ] **无 `unique case` / `priority case`**: 直接使用 `case`（iverilog 忽略 unique，仅 warning）
- [ ] **无 `always_comb`**: 如必须使用组合逻辑，用 `always @(*)`（但这要注意上面的时序问题；最佳方案是统一 always_ff）
- [ ] **无 `covergroup`**: iverilog 不支持
- [ ] **无 checker / 接口断言**: `assert #0(...)` 等并发断言不支持。用模块内过程断言替代
- [ ] **无 `let` 声明**: 尽量不用，或用 `function` 替代

### S2.2 调度安全

- [ ] **同一变量在 `always_ff` 内只有最后一个 NBA 生效**: 多层 `<=` 赋值时确认顺序
- [ ] **避免跨模块组合依赖**: 模块间的输入/输出在 iverilog 的 delta-cycle 中有不确定顺序
- [ ] **`#1` 阻塞延迟慎重使用**: `always_ff` 内不用 `#1`（除了 testbench 排错）

---

## S3: 覆盖友好设计 [COMMON]

### S3.1 错误/状态信号持久化 [COMMON]

> 以下示例使用 DMA 信号命名，但规则适用于所有 FSM 类 IP。

- [ ] **`error_flag` 不清零**: `error_flag_q <= error_flag_q` 保持，`error_flag_q <= 1'b0` 只在复位时
  ```verilog
  // BAD  — 每周期清零
  error_flag_q <= 1'b0;
  
  // GOOD — 持久化
  error_flag_q <= error_flag_q;
  ```
- [ ] **中断状态 auto-set**: `dma_done_intr_q <= 1'b1` 在完成动作中自动置位
- [ ] **中断状态 W1C clear**: 由 APB 写 INTR_STATE 清除
- [ ] **`done_q` 持久化**: DMA 完成后 `done_q` 保持，不被循环重跑覆盖
- [ ] **`error_code_q` 持久化**: 记录最后一次错误类型，不复位（除非复位或 SW 写入）

### S3.2 信号可观测性

- [ ] **所有 `*_q` 寄存器可通过 APB 读回**（或通过顶层观察端口）
- [ ] **FSM `state_q` 可观察**: 连接到状态寄存器或测试端口
- [ ] **中断路径完整**: intr_reg → enable → output，每个节点可单独观测
- [ ] **busy/active 状态信号**: 暴露给顶层用于覆盖率分析

### S3.3 覆盖驱动

- [ ] **转移宽度编码可遍历**: 用 `transfer_width_q` 3-bit 而不是 1-bit 编码
  - 确保 byte/half-word/word 三种宽度在测试中至少各用一次
- [ ] **中断使能可开关**: `en_dma_done_q` / `en_chunk_q` / `en_error_q` 独立控制
- [ ] **chunk size 可配置**: 边界的值能触发 chunk 中断
- [ ] **stop_q 功能独立**: 不是 start 的逆运算，而是独立的停机控制

---

## S4: 寄存器 RTL 规范 [COMMON]

### S4.1 位域正确性

- [ ] **位宽匹配**: 读回字段的位置与 spec 一致（逐 bit 核查）
- [ ] **拼接无越界**: `{4'h0, dst_incr_val_q, 12'h0, src_incr_val_q, ...}` 总位数 = 32，勿多勿少
  ```verilog
  // BAD — 拼接 34 位给 32 位寄存器
  {4'h0, dst_incr_val_q, 4'h0, src_incr_val_q, en_1, en_2} 
  // 4+12+4+12+1+1 = 34 > 32!
  
  // GOOD — 准确 32 位
  {4'h0, dst_incr_val_q, src_incr_val_q, 2'b0, en_1, en_2}
  // 4+12+12+2+1+1 = 32
  ```
- [ ] **保留位读回 0**: 未使用的 bit 在 always_comb 中设 `prdata = '0;`

### S4.2 地址解码

- [ ] **PSLVERR**: 保留地址范围（offset >= 0x50）返回 PSLVERR
  ```verilog
  assign pslverr = (reg_active && paddr >= 16'h0050) ? 1'b1 : 1'b0;
  ```
- [ ] **paddr 位宽一致**: 顶层和寄存器模块的 paddr 宽度匹配
- [ ] **W1C 寄存器**: INTR_STATE 写入清除对应的 intr_*_q
  ```verilog
  if (reg_write && reg_addr == 16'h0040) begin
    if (pwdata[0]) dma_done_intr_q  <= 1'b0;
    if (pwdata[1]) dma_chunk_intr_q <= 1'b0;
    if (pwdata[2]) dma_error_intr_q <= 1'b0;
  end
  ```

---

## S5: FSM 设计规范 [COMMON]

### S5.1 状态编码

- [ ] **枚举类型明确定义位宽**: `typedef enum logic [2:0] { ... }`
- [ ] **所有状态命名**: 使用有意义的名称（DmaIdle，DmaRead, ...）而非数字
- [ ] **default case**: 兜底回到 IDLE

### S5.2 状态跳转

- [ ] **无条件跳转显式化**: `DmaRead → DmaSendRead` 即使没有条件也要写 `state_d = DmaSendRead`
- [ ] **条件分支全覆盖**: 每个 if-else 都有 else 或初始化兜底
  ```verilog
  DmaIdle: if (start_q && enable_q)  state_d = DmaRead;
           else                       state_d = DmaIdle;  // 显式兜底
  ```
- [ ] **等待状态有超时**: DmaWaitRead/DmaWaitWrite 如果始终等不到响应应有超时路径
  - 或者通过 assertion 检查

### S5.3 动作与状态分离

- [ ] **next-state 和 action 用不同赋值类型**: state_d = blocking, register NBA
- [ ] **动作基于 `state_q` 而非 `state_d`**: `case (state_q)` 确保当前状态的动作在转换前执行
- [ ] **中断置位在 action 中**: `dma_done_intr_q <= 1'b1` 在 DmaWrite action 里，而非 next-state 中

---

## S6: 自动生成 RTL 附加检查 [COMMON]

适用于 `run_rtl_gen.py` 生成的 RTL 代码：

- [ ] **FSM 与 regs 模块端口匹配**: `en_dma_done_q` 等中断使能信号在 FSM 输入或顶层处理
- [ ] **中断输出门控在模块内**: `assign intr_o = intr_q & en_q` 不要在模块外拼接
- [ ] **寄存器模块 addr_width**: 与顶层模块一致（来自 spec 的 `apb.addr_width`）
- [ ] **复位值列表**: generated code vs spec `reset` 字段 — 逐寄存器核查
- [ ] **中断 mapping**: intr_o 信号名与 spec 定义的 `interrupts[].output` 一致
- [ ] **paddr 字面值**: 比较 `paddr == 12'h040` 等用正确的宽度（匹配 addr_width）
- [ ] **生成器模板参数化**: 不硬编码 N=3（中断数），从 config 中读取

---

## RTL Review 逐行标注示例 [MODULE: dma]

```verilog
// RTL 审查标注示例: dma.sv — DMA FSM

// [S1.1] ✅ 统一 always_ff: next-state + actions
always_ff @(posedge clk_i or negedge rst_ni) begin
  ...
  // [S5.3] ✅ state_d blocking = initial + case override
  state_d = state_q;
  case (state_q)
    DmaIdle: if (start_q && enable_q) state_d = DmaRead;
             else                      state_d = DmaIdle;  // [S5.2] ✅ 显式兜底
  
  // [S1.1] ✅ state update NBA
  state_q <= state_d;
  
  // [S5.3] ✅ actions 基于 state_q
  case (state_q)
    DmaRead: begin
      if (host_rvalid_i && !host_err_i)
        read_buffer_q <= host_rdata_i;  // [S2.1] ✅ 无 inside
      else if (host_err_i) begin
        error_flag_q <= 1'b1;   // [S3.1] ✅ error persist（不每周期清）
        dma_error_intr_q <= 1'b1;  // [S3.1] ✅ intr auto-set
      end
    end
```

---

## RTL Review 流程 [COMMON]

```
1. 代码结构审查     → S1 （可综合风格）
2. 仿真兼容审查     → S2 （iverilog 兼容）
3. 覆盖设计审查     → S3 （覆盖友好）
4. 寄存器正确性审查  → S4 （位域、解码）
5. FSM 完整性审查   → S5 （状态、跳转、动作）
6. 生成代码审查     → S6 （spec 生成器）
```

审查完成后在文件头标注：
```
// Reviewed: 2026-05-14
// Rev:      v4
// Checklist: S1✅ S2✅ S3✅ S4✅ S5✅ S6⏳(spec-gen only)
```
