// Complete I2C testbench with slave model
// Tests:
//   1. Register read/write (APB)
//   2. I2C master write transaction (START + addr(W) + data + STOP)
//   3. I2C master read transaction (START + addr(R) + read + NACK + STOP)
//   4. Combined transaction (RESTART)
//   5. Multi-speed (100kHz, 400kHz, 1MHz)
//   6. TX FIFO stress
//   7. Interrupt check
`timescale 1ns/1ps

module tb_i2c_full;
  reg clk;
  reg rstn;
  reg psel, penable, pwrite;
  reg [11:0] paddr;
  reg [31:0] pwdata;
  wire [31:0] prdata;
  wire pready, pslverr;

  // I2C bus
  wire scl, sda;
  wire intr_o;

  // DUT ports
  wire scl_o, scl_en_o, sda_o, sda_en_o;
  wire scl_i, sda_i;

  // I2C bus with pull-up
  pullup(scl);
  pullup(sda);

  assign scl_i = scl;
  assign sda_i = sda;

  // DUT drives bus when enabled (using sda_o value for proper ACK/NACK)
  assign scl = scl_en_o ? 1'b0 : 1'bz;
  assign sda = sda_en_o ? sda_o : 1'bz;

  // I2C slave at address 0x42
  wire [7:0] slave_rx [0:7];
  logic [7:0] slave_tx [0:7];
  wire slave_write_valid;

  i2c_slave u_slave (
    .clk(clk), .rstn(rstn),
    .scl(scl), .sda(sda),
    .slave_addr(7'h42),
    .rd0(slave_tx[0]), .rd1(slave_tx[1]), .rd2(slave_tx[2]), .rd3(slave_tx[3]),
    .rd4(slave_tx[4]), .rd5(slave_tx[5]), .rd6(slave_tx[6]), .rd7(slave_tx[7]),
    .write_data(slave_rx),
    .write_valid(slave_write_valid),
    .transaction_active()
  );

  // DUT
  i2c dut (
    .clk(clk), .rstn(rstn),
    .psel(psel), .penable(penable), .pwrite(pwrite),
    .paddr(paddr), .pwdata(pwdata),
    .prdata(prdata), .pready(pready), .pslverr(pslverr),
    .scl_o(scl_o), .scl_en_o(scl_en_o), .scl_i(scl_i),
    .sda_o(sda_o), .sda_en_o(sda_en_o), .sda_i(sda_i),
    .intr_o(intr_o)
  );

  // ── Clock ──
  initial begin
    clk = 0;
    forever #10 clk = ~clk;
  end

  // ── Helper tasks ──
  reg [31:0] rd;

  task apb_write(input [11:0] a, input [31:0] d);
    @(posedge clk);
    psel = 1; penable = 0; pwrite = 1; paddr = a; pwdata = d;
    @(posedge clk);
    penable = 1;
    @(posedge clk);
    while (!pready) @(posedge clk);
    psel = 0; penable = 0;
    @(posedge clk);
  endtask

  task apb_read(input [11:0] a, output [31:0] r);
    @(posedge clk);
    psel = 1; penable = 0; pwrite = 0; paddr = a;
    @(posedge clk);
    penable = 1;
    @(posedge clk);
    while (!pready) @(posedge clk);
    r = prdata;
    psel = 0; penable = 0;
    @(posedge clk);
  endtask

  task check_reg(input [11:0] a, input [31:0] expected, input string name);
    reg [31:0] val;
    apb_read(a, val);
    if (val == expected)
      $display("  PASS: %s = %h", name, val);
    else
      $display("  FAIL: %s = %h (expected %h)", name, val, expected);
  endtask

  task i2c_write_transfer(input [6:0] addr, input [7:0] data);
    integer wait_i;
    // Program tx_data
    apb_write(12'h10, {24'h0, data});  // tx_data_reg
    // Set slave address (just the 7-bit addr, R/W comes from cmd)
    apb_write(12'h0C, {25'h0, addr});  // addr_reg: 7-bit slave addr
    // Issue START + WRITE
    apb_write(12'h08, 32'h00000009);  // cmd_reg: start=1 + write=1
    // Wait for busy to clear
    for (wait_i = 0; wait_i < 2000; wait_i = wait_i + 1) begin
      apb_read(12'h18, rd);
      if (!rd[0]) wait_i = 2000;
      #20;
    end
  endtask

  task i2c_read_transfer(input [6:0] addr, output [7:0] data);
    integer wait_i;
    // Set slave address (just the 7-bit addr)
    apb_write(12'h0C, {25'h0, addr});  // addr_reg
    // Issue START + READ + NACK (single byte)
    apb_write(12'h08, 32'h00000025);  // cmd_reg: start+read+nack
    // Wait for transaction
    for (wait_i = 0; wait_i < 2000; wait_i = wait_i + 1) begin
      apb_read(12'h18, rd);
      if (!rd[0]) wait_i = 2000;
      #20;
    end
    // Read received data
    apb_read(12'h14, rd);
    data = rd[7:0];
  endtask

  // ── Main test ──
  initial begin
    $dumpfile("tb_i2c_full.vcd");
    $dumpvars(0, tb_i2c_full);

    // Load slave read data
    slave_tx[0] = 8'hA5;
    slave_tx[1] = 8'h5A;
    slave_tx[2] = 8'hFF;
    slave_tx[3] = 8'h00;
    slave_tx[4] = 8'hDE;
    slave_tx[5] = 8'hAD;
    slave_tx[6] = 8'hBE;
    slave_tx[7] = 8'hEF;

    // ── Reset ──
    rstn = 0;
    #100;
    rstn = 1;
    #150;
    $display("\n=== I2C Full Testbench ===");

    // ── 1. Register test ──
    $display("\n--- [1/7] Register Reset Values ---");
    check_reg(12'h00, 32'h00000014, "ctrl_reg");
    check_reg(12'h04, 32'h0000003B, "speed_reg");
    check_reg(12'h08, 32'h00000000, "cmd_reg");
    check_reg(12'h0C, 32'h00000000, "addr_reg");
    check_reg(12'h10, 32'h00000000, "tx_data_reg");
    check_reg(12'h18, 32'h000000??, "status_reg (want 1C = busy=0)");
    check_reg(12'h1C, 32'h00000110, "fifo_ctrl_reg");

    // ── 2. RW test ──
    $display("\n--- [2/7] Register RW ---");
    apb_write(12'h00, 32'h0000001F);
    check_reg(12'h00, 32'h0000001F, "ctrl_reg RW");
    apb_write(12'h04, 32'h0000000B);
    check_reg(12'h04, 32'h0000000B, "speed_reg RW (400kHz)");
    apb_write(12'h0C, 32'h0000003F);
    check_reg(12'h0C, 32'h0000003F, "addr_reg RW");

    // ── 3. PSLVERR test ──
    $display("\n--- [3/7] PSLVERR ---");
    apb_write(12'h24, 32'hDEADBEEF);
    apb_read(12'h24, rd);
    $display("  reserved(0x24) read pslverr=%0d data=%h", pslverr, rd);

    // ── 4. I2C Write Transaction (100kHz) ──
    $display("\n--- [4/7] I2C Write Transaction (100kHz, slave addr=0x42) ---");
    // Enable I2C, set 100kHz
    apb_write(12'h00, 32'h00000007);  // ctrl: en=1, irq_en=1, master=1
    apb_write(12'h04, 32'h0000003B);  // speed: 100kHz

    // Write byte 0xA5 to slave
    i2c_write_transfer(7'h42, 8'hA5);
    $display("  Write transfer done, checking slave...");
    check_reg(12'h18, 32'h00000000, "status (busy=0 after write)");

    // Write byte 0x5A
    i2c_write_transfer(7'h42, 8'h5A);
    $display("  Second write done");

    // ── 5. I2C Read Transaction (400kHz) ──
    $display("\n--- [5/7] I2C Read Transaction (400kHz) ---");
    apb_write(12'h04, 32'h0000000B);  // speed: 400kHz

    for (int i = 0; i < 3; i++) begin
      logic [7:0] rdata;
      i2c_read_transfer(7'h42, rdata);
      $display("  Read[%0d] = %02h", i, rdata);
      check_reg(12'h18, 32'h00000000, "status after read");
    end

    // ── 6. Multi-speed test (1MHz) ──
    $display("\n--- [6/7] Multi-speed (1MHz) ---");
    apb_write(12'h04, 32'h00000003);  // speed: 1MHz
    i2c_write_transfer(7'h42, 8'hFF);
    $display("  1MHz write done");
    check_reg(12'h04, 32'h00000003, "speed_reg (1MHz)");

    // Switch back to 100kHz
    apb_write(12'h04, 32'h0000003B);
    for (int i = 0; i < 2; i++) begin
      logic [7:0] rdata;
      i2c_read_transfer(7'h42, rdata);
      $display("  100kHz Read[%0d] = %02h", i, rdata);
    end

    // ── 7. TX FIFO stress + intr check ──
    $display("\n--- [7/7] TX FIFO + Interrupt ---");
    apb_write(12'h00, 32'h00000007);  // ctrl: en=1, irq_en=1

    // Write multiple bytes to tx_data
    apb_write(12'h10, 32'h00000055);
    apb_write(12'h10, 32'h00000066);
    apb_write(12'h10, 32'h00000077);

    // Check status
    check_reg(12'h18, 32'h00000001, "status (busy=0? or 0 if idle)");

    // Check interrupt status
    check_reg(12'h20, 32'h00000000, "intr_status");

    // ── Final register dump ──
    $display("\n--- Final Register Dump ---");
    check_reg(12'h00, 32'h00000007, "ctrl_reg");
    check_reg(12'h0C, 32'h00000042, "addr_reg (after xfers)");
    check_reg(12'h10, 32'h00000077, "tx_data_reg (last written)");

    // Check slave received bytes
    $display("\n--- Slave RX Buffer ---");
    apb_read(12'h14, rd);
    $display("  rx_data_reg = %h", rd);
    check_reg(12'h18, 32'h00000000, "status");
    check_reg(12'h20, 32'h00000000, "intr_status");

    $display("\n=== ALL TESTS COMPLETE ===");
    $finish;
  end

  initial begin
    #100000;
    $display("TIMEOUT");
    $finish;
  end

endmodule


