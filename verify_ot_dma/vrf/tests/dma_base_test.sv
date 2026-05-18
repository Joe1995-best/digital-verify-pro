// dma_base_test.sv — Base test sequence for DMA verification
// Includes env + runs register + DMA transfer tests
// Tests in `tests/` extend this with specific test sequences.

module dma_base_test;

    // ── DUT signals ──
    logic        clk, rst_n;
    logic        psel, penable, pwrite;
    logic [15:0] paddr;
    logic [31:0] pwdata, prdata;
    logic        pready, pslverr;
    logic        intr_dma_done, intr_dma_chunk_done, intr_dma_error;
    logic        host_req, host_we;
    logic [31:0] host_addr, host_wdata;
    logic        host_gnt, host_err;
    logic [31:0] host_rdata;
    logic        host_rvalid;

    // DUT
    ot_dma_core dut (
        .clk_i(clk), .rst_ni(rst_n),
        .psel, .penable, .pwrite, .paddr, .pwdata, .prdata, .pready, .pslverr,
        .intr_dma_done_o(intr_dma_done),
        .intr_dma_chunk_done_o(intr_dma_chunk_done),
        .intr_dma_error_o(intr_dma_error),
        .host_addr_o(host_addr), .host_req_o(host_req),
        .host_we_o(host_we), .host_wdata_o(host_wdata),
        .host_gnt_i(host_gnt), .host_rdata_i(host_rdata),
        .host_rvalid_i(host_rvalid), .host_err_i(host_err)
    );

    // ═══ ENVIRONMENT ═══
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

    // Clock
    initial begin clk = 0; forever #5 clk = ~clk; end

    // Reset
    initial begin rst_n = 0; #30; rst_n = 1; end

    initial #10000 begin $display("[TIMEOUT]"); $finish; end

    // ═══ Common test logic ═══
    int pass_count, fail_count;

    task t_pass(input string name);
        pass_count = pass_count + 1;
        $display("  PASS: %s", name);
    endtask

    task t_fail(input string name);
        fail_count = fail_count + 1;
        $display("  FAIL: %s", name);
    endtask

    // Run the test — override in sub-tests
    virtual task run_test();
        $display("[BASE] No test defined — override run_test()");
    endtask

    // Main
    initial begin
        $dumpfile("dma_test.vcd"); $dumpvars(0, dma_base_test);
        pass_count = 0; fail_count = 0;

        // Init env signals
        host_gnt = 0; host_rdata = 0; host_rvalid = 0; host_err = 0;

        #100;  // Wait for reset

        $display("=== BASE TEST Starting ===");
        run_test();
        $display("=== BASE TEST Done: PASS=%0d FAIL=%0d ===\n", pass_count, fail_count);

        env.report();
        $finish;
    end

endmodule
