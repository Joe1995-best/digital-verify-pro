// dma_reg_test.sv — Standalone DMA register + transfer test (v3)
// Tests: reset values, RW, reserved addr, DMA single/multi-word, interrupts
// v3: Uses proven approach from tb_dma_core.v (shift register in testbench)

module dma_reg_test;

    // DUT ports
    logic        clk, rst_n;
    logic        psel, penable, pwrite;
    logic [15:0] paddr;
    logic [31:0] pwdata, prdata;
    logic        pready, pslverr;
    logic        intr_dma_done, intr_dma_chunk, intr_dma_error;
    logic        host_req, host_we;
    logic [31:0] host_addr, host_wdata;
    logic        host_gnt, host_err;
    logic [31:0] host_rdata;
    logic        host_rvalid;

    // ═══ Auto-grant + shift register (proven in tb_dma_core.v) ═══
    assign host_gnt = host_req;

    logic [31:0] host_data_q[$:255];
    logic [4:0] rvalid_pipe;
    assign host_rvalid = (rvalid_pipe != 5'd0);

    always @(posedge clk) begin
        if (!rst_n) begin
            rvalid_pipe <= 5'd0;
        end else begin
            if (rvalid_pipe > 0) rvalid_pipe <= rvalid_pipe - 1;
            if (host_req && !rvalid_pipe) begin
                if (!host_we && host_data_q.size() > 0)
                    host_rdata <= host_data_q.pop_front();
                rvalid_pipe <= 5'b10000;
            end
        end
    end

    assign host_err = 1'b0;

    // DUT
    ot_dma_core dut (
        .clk_i(clk), .rst_ni(rst_n),
        .psel, .penable, .pwrite, .paddr, .pwdata, .prdata, .pready, .pslverr,
        .intr_dma_done_o(intr_dma_done), .intr_dma_chunk_done_o(intr_dma_chunk),
        .intr_dma_error_o(intr_dma_error),
        .host_addr_o(host_addr), .host_req_o(host_req),
        .host_we_o(host_we), .host_wdata_o(host_wdata),
        .host_gnt_i(host_gnt), .host_rdata_i(host_rdata),
        .host_rvalid_i(host_rvalid), .host_err_i(host_err)
    );

    // Environment (v3 — APB tasks + assertions only)
    vrf_env_top env (
        .clk, .rst_n,
        .psel, .penable, .pwrite, .paddr, .pwdata, .prdata, .pready, .pslverr,
        .host_gnt, .host_rdata, .host_rvalid, .host_err,
        .host_req, .host_we, .host_addr, .host_wdata,
        .dma_busy(dut.busy_q), .dma_done(dut.done_q),
        .dma_error(dut.error_flag_q), .dma_state(dut.state_q),
        .dma_start(dut.start_q), .dma_enable(dut.enable_q),
        .intr_done(intr_dma_done), .intr_error(intr_dma_error)
    );

    initial clk = 0;
    always #5 clk = ~clk;
    initial begin rst_n = 0; #30; rst_n = 1; end
    initial #10000 begin $display("TIMEOUT"); env.report(); $finish; end
    initial begin $dumpfile("dma_reg_test.vcd"); $dumpvars(0, dma_reg_test); end

    int pass, fail;
    reg [31:0] rd;

    task t_pass(input string name);
        pass = pass + 1;
        $display("  PASS: %s", name);
    endtask

    task t_fail(input string name);
        fail = fail + 1;
        $display("  FAIL: %s", name);
    endtask

    initial begin
        pass=0; fail=0;
        #100;

        // ── Test 1: Register reset values ──
        $display("\n[Test 1] Register reset");
        env.apb_read(16'h0000, rd);
        if (rd == 0) t_pass("src_addr_lo=0"); else t_fail("src_addr_lo");
        env.apb_read(16'h0038, rd);
        if (rd[1]==0 && rd[0]==0) t_pass("status=0"); else t_fail("status");
        env.apb_read(16'h0010, rd);
        if (rd[3:0]==4'h7) t_pass("src_asid=7"); else t_fail("src_asid");

        // ── Test 2: RW register operations ──
        $display("\n[Test 2] RW registers");
        env.apb_write(16'h0028, 32'h0000_000A);
        env.apb_read(16'h0028, rd);
        if (rd == 32'hA) t_pass("total_size RW"); else t_fail("total_size");
        env.apb_write(16'h0000, 32'hA5A5_A5A5);
        env.apb_read(16'h0000, rd);
        if (rd == 32'hA5A5A5A5) t_pass("src_addr RW"); else t_fail("src_addr");
        env.apb_write(16'h0030, 3'h2);
        env.apb_read(16'h0030, rd);
        if (rd[2:0]==3'h2) t_pass("width RW"); else t_fail("width");

        // ── Test 3: PSLVERR ──
        $display("\n[Test 3] PSLVERR on reserved address");
        env.apb_read(16'h0064, rd);
        if (pslverr) t_pass("PSLVERR asserted"); else t_fail("PSLVERR");

        // ── Test 4: DMA single-word transfer ──
        $display("\n[Test 4] DMA single-word transfer");
        host_data_q = {};
        env.apb_write(16'h0000, 32'h0000_1000);
        env.apb_write(16'h0008, 32'h0000_2000);
        env.apb_write(16'h0028, 32'h0000_0001);
        env.apb_write(16'h0030, 3'h2);
        host_data_q.push_back(32'hDEAD_BEEF);
        env.apb_write(16'h0044, 32'h0000_0001);  // en_dma_done
        env.apb_write(16'h0034, 32'h0000_0005);  // enable=1, start=1
        #800;
        if (intr_dma_done) t_pass("DMA done (intr)"); else t_fail("DMA done (intr)");

        // ── Test 5: DMA multi-word (4 words) ──
        $display("\n[Test 5] DMA multi-word (4)");
        host_data_q = {};
        env.apb_write(16'h0000, 32'h0000_3000);
        env.apb_write(16'h0008, 32'h0000_4000);
        env.apb_write(16'h0028, 32'h0000_0004);
        env.apb_write(16'h0030, 3'h2);
        host_data_q.push_back(32'hA5A5_0000);
        host_data_q.push_back(32'hA5A5_0001);
        host_data_q.push_back(32'hA5A5_0002);
        host_data_q.push_back(32'hA5A5_0003);
        env.apb_write(16'h0034, 32'h0000_0005);  // enable=1, start=1
        #1500;
        if (intr_dma_done) t_pass("Multi-word DMA"); else t_fail("Multi-word DMA");

        // ── Test 6: Stop DMA and check state ──
        $display("\n[Test 6] DMA stop and state check");
        env.apb_write(16'h0034, 32'h0000_0000);  // clear ctrl (stop)
        #200;
        $display("  state_q=%0d busy_q=%0d remaining_q=%0d",
                 dut.state_q, dut.busy_q, dut.remaining_q);
        if (!dut.busy_q) t_pass("DMA stopped"); else t_fail("DMA still busy");

        // ── Report ──
        $display("\n=== RESULT: PASS=%0d FAIL=%0d ===", pass, fail);
        env.report();
        $finish;
    end

endmodule
