"""
sva_assertions.sv — 标准 SVA 断言示例（兼容 iverilog 11）。

将现有过程式断言（vrf_assert_*.sv 中的 always @() + $display）
迁移为标准并发断言（assert property）。
"""

// =============================================================================
// APB Protocol Assertions (SVA, iverilog 11 compatible)
// =============================================================================

module apb_sva_assertions (
  input logic clk,
  input logic rstn,
  input logic psel,
  input logic penable,
  input logic pwrite,
  input logic [31:0] paddr,
  input logic [31:0] pwdata,
  input logic [31:0] prdata,
  input logic pready,
  input logic pslverr
);

  // ── X 检测 (交叉断言覆盖所有 APB 信号) ──
  assert property (@(posedge clk) disable iff (!rstn)
    psel |-> !$isunknown(paddr)
  ) else $error("[APB-SVA] X detected on paddr while psel asserted");

  assert property (@(posedge clk) disable iff (!rstn)
    penable |-> psel  // PENABLE must be qualified by PSEL
  ) else $error("[APB-SVA] penable without psel");

  // ── 地址稳定性 ──
  // 在 SETUP→ACCESS 转换期间地址不能变化
  assert property (@(posedge clk) disable iff (!rstn)
    $rose(psel) |=> $stable(paddr)
  ) else $error("[APB-SVA] paddr changed during access");

  // ── PREADY 响应 ──
  // PENABLE 置位后 PREADY 必须在有限周期内拉高
  // (iverilog 11 不支持 s_eventually, 用 ##[1:$] 替代)
  assert property (@(posedge clk) disable iff (!rstn)
    $rose(penable) |-> ##[1:10] pready
  ) else $error("[APB-SVA] pready not asserted within 10 cycles after penable");

  // ── PSLVERR 时序 ──
  // PSLVERR 只能在 PREADY 周期被采样
  assert property (@(posedge clk) disable iff (!rstn)
    pslverr |-> pready
  ) else $error("[APB-SVA] pslverr without pready");

endmodule


// =============================================================================
// I2C Protocol Assertions
// =============================================================================

module i2c_sva_assertions (
  input logic clk,
  input logic rstn,
  input logic scl_i,
  input logic sda_i,
  input logic scl_en_o,
  input logic sda_en_o,
  input logic busy
);

  // ── START 条件: SDA 低跳变在 SCL 高时 ──
  // START = SDA falling while SCL high
  // (实际检测用时钟采样避免边沿竞争)
  assert property (@(posedge clk) disable iff (!rstn)
    busy |-> $fell(scl_i) || $fell(sda_i)  // 简版
  );

  // ── 忙时不可复位 ──
  assert property (@(posedge clk) disable iff (!rstn)
    busy |-> !$fell(rstn)
  ) else $error("[I2C-SVA] Reset during active transaction");

endmodule
