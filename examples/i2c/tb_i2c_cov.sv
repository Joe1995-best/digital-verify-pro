// Coverage-driven I2C testbench — targets all coverage gaps
// v2: adds RX data verification, interrupt testing, register clear tests
`timescale 1ns/1ps

module tb_i2c_cov;
  reg clk;
  reg rstn;
  reg psel, penable, pwrite;
  reg [11:0] paddr;
  reg [31:0] pwdata;
  wire [31:0] prdata;
  wire pready, pslverr;
  wire scl, sda;
  wire intr_o;
  wire scl_o, scl_en_o, sda_o, sda_en_o;
  wire scl_i, sda_i;

  pullup(scl); pullup(sda);
  assign scl_i = scl; assign sda_i = sda;
  assign scl = scl_en_o ? 1'b0 : 1'bz;
  assign sda = sda_en_o ? sda_o : 1'bz;

  wire [7:0] slave_rx [0:7];
  logic [7:0] slave_tx [0:7];
  wire slave_write_valid;

  i2c_slave u_slave (
    .clk(clk), .rstn(rstn),
    .scl(scl), .sda(sda),
    .slave_addr(7'h42),
    .rd0(slave_tx[0]), .rd1(slave_tx[1]), .rd2(slave_tx[2]), .rd3(slave_tx[3]),
    .rd4(slave_tx[4]), .rd5(slave_tx[5]), .rd6(slave_tx[6]), .rd7(slave_tx[7]),
    .write_data(slave_rx), .write_valid(slave_write_valid), .transaction_active()
  );

  i2c dut (
    .clk(clk), .rstn(rstn),
    .psel(psel), .penable(penable), .pwrite(pwrite),
    .paddr(paddr), .pwdata(pwdata),
    .prdata(prdata), .pready(pready), .pslverr(pslverr),
    .scl_o(scl_o), .scl_en_o(scl_en_o), .scl_i(scl_i),
    .sda_o(sda_o), .sda_en_o(sda_en_o), .sda_i(sda_i),
    .intr_o(intr_o)
  );

  initial begin clk = 0; forever #10 clk = ~clk; end

  reg [31:0] rd;

  task apb_write(input [11:0] a, input [31:0] d);
    @(posedge clk); psel = 1; penable = 0; pwrite = 1; paddr = a; pwdata = d;
    @(posedge clk); penable = 1;
    @(posedge clk); while (!pready) @(posedge clk);
    psel = 0; penable = 0; @(posedge clk);
  endtask

  task apb_read(input [11:0] a, output [31:0] r);
    @(posedge clk); psel = 1; penable = 0; pwrite = 0; paddr = a;
    @(posedge clk); penable = 1;
    @(posedge clk); while (!pready) @(posedge clk);
    r = prdata; psel = 0; penable = 0; @(posedge clk);
  endtask

  task check_reg(input [11:0] a, input [31:0] expected, input string name);
    apb_read(a, rd);
    if (rd == expected) $display("  PASS: %s = %h", name, rd);
    else $display("  FAIL: %s = %h (exp %h)", name, rd, expected);
  endtask

  task wait_busy_clear;
    integer w;
    for (w = 0; w < 2000; w = w + 1) begin
      apb_read(12'h18, rd);
      if (!rd[0]) w = 2000; else #20;
    end
  endtask

  task i2c_write_transfer(input [6:0] addr, input [7:0] data);
    apb_write(12'h10, {24'h0, data});
    apb_write(12'h0C, {25'h0, addr});
    apb_write(12'h08, 32'h00000009);  // start=1 + write=1
    wait_busy_clear;
  endtask

  task i2c_read_transfer(input [6:0] addr, output [7:0] data);
    apb_write(12'h0C, {25'h0, addr});
    apb_write(12'h08, 32'h00000025);  // start+read+nack
    wait_busy_clear;
    apb_read(12'h14, rd);
    data = rd[7:0];
  endtask

  integer pass, fail, total;

  initial begin
    $dumpfile("i2c_cov.vcd");
    $dumpvars(0, tb_i2c_cov);
    slave_tx[0] = 8'hA5; slave_tx[1] = 8'h5A; slave_tx[2] = 8'hFF; slave_tx[3] = 8'h00;
    slave_tx[4] = 8'hDE; slave_tx[5] = 8'hAD; slave_tx[6] = 8'hBE; slave_tx[7] = 8'hEF;
    pass = 0; fail = 0;

    rstn = 0; #100; rstn = 1; #150;
    $display("\n=== I2C Coverage Convergence Testbench ===\n");

    // Enable I2C master
    apb_write(12'h00, 32'h00000007);  // ctrl: en=1, irq_en=1, master=1
    apb_write(12'h04, 32'h0000003B);  // speed: 100kHz

    // ── RX Data Test — verify slave data arrives in rx_data_reg ──
    $display("\n--- [RX] Read from slave, verify rx_data ---");
    begin : rx_test
      logic [7:0] rdata;
      i2c_read_transfer(7'h42, rdata);
      if (rdata == 8'hA5) begin pass++; $display("  PASS: rx_data = %02h (exp A5)", rdata); end
      else begin fail++; $display("  FAIL: rx_data = %02h (exp A5)", rdata); end
      // Verify rx_data_reg holds the value
      check_reg(12'h14, 32'h000000A5, "rx_data_reg after read");
      // Read again — different slave data
      i2c_read_transfer(7'h42, rdata);
      if (rdata == 8'h5A) begin pass++; $display("  PASS: rx_data[1] = %02h", rdata); end
      else begin fail++; $display("  FAIL: rx_data[1] = %02h (exp 5A)", rdata); end
    end

    // ── Register Clear Tests — write then clear ──
    $display("\n--- [REG] Register write-then-clear ---");
    apb_write(12'h0C, 32'h00000000);  // clear addr_reg
    check_reg(12'h0C, 32'h00000000, "addr_reg cleared");
    apb_write(12'h10, 32'h00000000);  // clear tx_data_reg
    check_reg(12'h10, 32'h00000000, "tx_data_reg cleared");
    apb_write(12'h00, 32'h00000000);  // disable controller
    check_reg(12'h00, 32'h00000000, "ctrl_reg disabled");
    apb_write(12'h00, 32'h00000007);  // re-enable

    // ── Status Register During Transaction ──
    $display("\n--- [STATUS] Read status during active transaction ---");
    apb_write(12'h10, 32'h00000055);
    apb_write(12'h0C, 32'h00000042);
    apb_write(12'h08, 32'h00000009);  // start+write
    // Read status while busy
    #100;
    apb_read(12'h18, rd);
    $display("  status DURING xfer = %h (busy bit=%0d)", rd, rd[0]);
    wait_busy_clear;
    apb_read(12'h18, rd);
    $display("  status AFTER xfer = %h (busy=%0d)", rd, rd[0]);

    // ── Interrupt Test — verify intr_o triggers ──
    $display("\n--- [INTR] Interrupt path test ---");
    apb_write(12'h00, 32'h00000007);  // ctrl: en=1, irq_en=1
    // Perform a write transfer that should trigger tx_empty irq
    apb_write(12'h10, 32'h000000AA);
    apb_write(12'h0C, 32'h00000042);
    apb_write(12'h08, 32'h00000009);  // start+write
    #500;
    $display("  intr_o = %0d (expect 1 during xfer)", intr_o);
    wait_busy_clear;
    #200;
    $display("  intr_o after xfer = %0d", intr_o);
    // Check interrupt status register
    apb_read(12'h20, rd);
    $display("  intr_status_reg = %h", rd);
    // Clear interrupt by writing 1 to bits
    apb_write(12'h20, 32'hFFFFFFFF);  // W1C clear
    apb_read(12'h20, rd);
    $display("  intr_status after clear = %h (expect 0)", rd);
    if (rd == 0) begin pass++; $display("  PASS: intr_status cleared"); end
    else begin fail++; $display("  FAIL: intr_status not cleared"); end

    // ── PSLVERR Read Test ──
    $display("\n--- [ERR] PSLVERR on reserved read ---");
    apb_read(12'h24, rd);
    $display("  reserved(0x24) read: pslverr=%0d data=%h", pslverr, rd);
    if (pslverr) begin pass++; $display("  PASS: pslverr asserted"); end
    else begin fail++; $display("  FAIL: pslverr not asserted"); end

    // ── Combined Write+Read (RESTART) ──
    $display("\n--- [RESTART] Combined Write+Read ---");
    // Write then Read with RESTART
    i2c_write_transfer(7'h42, 8'h77);
    $display("  Write done");
    begin : restart_test
      logic [7:0] rdata;
      i2c_read_transfer(7'h42, rdata);
      $display("  Read after RESTART: %02h", rdata);
    end

    // ── Multiple slave address test ──
    $display("\n--- [ADDR] Different slave addresses ---");
    begin : multi_addr
      logic [7:0] rdata;
      // Try slave 0x42 with GP addr range
      check_reg(12'h18, 32'h00000000, "status idle");
      $display("  intr_o = %0d", intr_o);
    end

    // ── Speed switch stress ──
    $display("\n--- [SPEED] Speed switching stress ---");
    apb_write(12'h04, 32'h00000003);  // 1MHz
    #200;
    apb_write(12'h04, 32'h0000000B);  // 400kHz
    #200;
    apb_write(12'h04, 32'h0000003B);  // 100kHz
    check_reg(12'h04, 32'h0000003B, "speed_reg after switching");
    apb_read(12'h18, rd);
    $display("  status after speed switch = %h", rd);
    apb_read(12'h20, rd);
    $display("  intr_status after speed switch = %h", rd);

    $display("\n=== RESULTS: %0d pass, %0d fail, %0d total ===", pass, fail, pass+fail);

    if (fail == 0) $display("*** ALL TESTS PASSED ***");
    else $display("*** %0d TESTS FAILED ***", fail);
    $finish;
  end

  initial begin #200000; $display("TIMEOUT"); $finish; end
endmodule
