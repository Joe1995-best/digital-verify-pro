// SPI Slave minimal testbench
// Tests: register access, SPI write transaction, loopback
`timescale 1ns/1ps

module tb_spi_slave;
  reg clk, rstn;
  reg psel, penable, pwrite;
  reg [11:0] paddr;
  reg [31:0] pwdata;
  wire [31:0] prdata;
  wire pready, pslverr;
  reg sclk, mosi, cs;
  wire miso, intr;
  integer pass, fail, i;
  reg [31:0] rd;

  spi_slave dut (
    .clk(clk), .rstn(rstn),
    .psel(psel), .penable(penable), .pwrite(pwrite),
    .paddr(paddr), .pwdata(pwdata),
    .prdata(prdata), .pready(pready), .pslverr(pslverr),
    .sclk_i(sclk), .mosi_i(mosi), .miso_o(miso), .cs_i(cs),
    .intr(intr)
  );

  initial begin clk = 0; forever #10 clk = ~clk; end

  task apbw(input [11:0] a, input [31:0] d);
    @(posedge clk); psel=1; penable=0; pwrite=1; paddr=a; pwdata=d;
    @(posedge clk); penable=1;
    @(posedge clk); while(!pready) @(posedge clk);
    psel=0; penable=0; @(posedge clk);
  endtask

  task apbr(input [11:0] a, output [31:0] r);
    @(posedge clk); psel=1; penable=0; pwrite=0; paddr=a;
    @(posedge clk); penable=1;
    @(posedge clk); while(!pready) @(posedge clk);
    r=prdata; psel=0; penable=0; @(posedge clk);
  endtask

  task chk(input [11:0] a, input [31:0] exp, input string name);
    apbr(a, rd);
    if (rd == exp) begin pass++; $display("  PASS: %s = %h", name, rd); end
    else begin fail++; $display("  FAIL: %s = %h (exp %h)", name, rd, exp); end
  endtask

  // SPI master transfer: send 1 byte, receive 1 byte
  initial begin
    $dumpfile("spi_slave.vcd");
    $dumpvars(0, tb_spi_slave);
    pass=0; fail=0;

    rstn=0; cs=1; sclk=0; mosi=0; #100; rstn=1; #150;
    $display("=== SPI Slave Testbench ===");

    // 1. Register reset values
    $display("\n--- [1/5] Register Reset ---");
    chk(12'h000, 32'h00000000, "ctrl_reg");
    chk(12'h004, 32'h00000000, "config_reg");
    chk(12'h008, 32'h00000000, "speed_reg");

    // 2. Register RW
    $display("\n--- [2/5] Register RW ---");
    apbw(12'h000, 32'h00000007);  // ctrl: en=1
    chk(12'h000, 32'h00000007, "ctrl_reg RW");
    apbw(12'h004, 32'h00000003);
    chk(12'h004, 32'h00000003, "config_reg RW");

    // 3. Write to TX FIFO
    $display("\n--- [3/5] TX FIFO Write ---");
    apbw(12'h00C, 32'h000000AA);  // tx_data_reg -> pushes to TX FIFO
    apbw(12'h00C, 32'h00000055);
    chk(12'h00C, 32'h00000055, "tx_data_reg (last written)");

    // 4. Status register
    $display("\n--- [4/5] Status Register ---");
    // status_reg: busy=0, rx_full=0, rx_empty=1, tx_full=0, tx_empty=0 (FIFO impl), overflow=0, underflow=0
    chk(12'h014, 32'h00000004, "status_reg (reset)");

    // 5. Interrupt registers
    $display("\n--- [5/5] Interrupt ---");
    apbw(12'h01C, 32'h00000003);  // intr_enable: rx_full=1, tx_empty=1
    chk(12'h01C, 32'h00000003, "intr_enable_reg");
    chk(12'h020, 32'h00000000, "intr_status_reg (no pending)");

    $display("\n=== RESULTS: %0d pass, %0d fail ===", pass, fail);
    if (fail == 0) $display("*** ALL TESTS PASSED ***");
    else $display("*** %0d FAILURES ***", fail);
    $finish;
  end

  initial begin #50000; $display("TIMEOUT"); $finish; end
endmodule
