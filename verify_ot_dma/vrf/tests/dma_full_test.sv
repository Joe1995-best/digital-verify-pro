// dma_full_test.sv — Comprehensive DMA VRF test suite (v2)
// Covers: registers, DMA transfers, error, chunk, stop, incr, multi-xfer

module dma_full_test;

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

    // Auto-grant + shift register
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

    // Error injection: hold host_err high for 10 cycles after request
    bit  error_inject;
    logic [3:0] err_hold;
    logic       host_err_q;
    
    always @(posedge clk) begin
        if (!rst_n) begin err_hold <= 0; host_err_q <= 0; end
        else begin
            if (error_inject && host_req && !host_we && !err_hold) begin
                host_err_q <= 1;
                err_hold   <= 4'hF;  // hold for 15 cycles
            end else if (err_hold > 0) begin
                err_hold <= err_hold - 1;
                if (err_hold == 1) host_err_q <= 0;
            end
        end
    end
    assign host_err = host_err_q;

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

    // Environment
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
    initial #80000 begin $display("TIMEOUT"); env.report(); $finish; end
    initial begin $dumpfile("dma_full_test.vcd"); $dumpvars(0, dma_full_test); end

    int pass, fail;
    reg [31:0] rd;

    task t_pass(input string name);
        pass = pass + 1; $display("  PASS: %s", name);
    endtask
    task t_fail(input string name);
        fail = fail + 1; $display("  FAIL: %s", name);
    endtask

    task dma_start(input [31:0] src, dst, sz, input [2:0] wid, input int n_data);
        env.apb_write(16'h0000, src);
        env.apb_write(16'h0008, dst);
        env.apb_write(16'h0028, sz);
        env.apb_write(16'h0030, wid);
        for (int i = 0; i < n_data; i++)
            host_data_q.push_back((32'hA5A5_0000 + i));
        env.apb_write(16'h0044, 32'h0000_0007);
        env.apb_write(16'h0034, 32'h0000_0005);
    endtask

    task dma_wait_done(int timeout);
        repeat (timeout) @(posedge clk);
    endtask

    task dma_stop();
        env.apb_write(16'h0034, 32'h0000_0000);
        #200;
    endtask

    initial begin
        pass=0; fail=0; error_inject = 0;
        #100;

        $display("\n[Test 1] Register reset");
        env.apb_read(16'h0000, rd); if (rd == 0) t_pass("src_addr_lo=0"); else t_fail("src_addr_lo");
        env.apb_read(16'h0038, rd); if (rd[1]==0 && rd[0]==0) t_pass("status=0"); else t_fail("status");
        env.apb_read(16'h0010, rd); if (rd[3:0]==4'h7) t_pass("src_asid=7"); else t_fail("src_asid");

        $display("\n[Test 2] RW registers");
        env.apb_write(16'h0028, 32'h0000_000A); env.apb_read(16'h0028, rd);
        if (rd == 32'hA) t_pass("total_size RW"); else t_fail("total_size");
        env.apb_write(16'h0030, 3'h2); env.apb_read(16'h0030, rd);
        if (rd[2:0]==3'h2) t_pass("width RW"); else t_fail("width");
        env.apb_write(16'h0010, 32'h0000_0000); env.apb_read(16'h0010, rd);
        if (rd[3:0]==4'h0) t_pass("asid RW"); else t_fail("asid");
        env.apb_write(16'h0010, 32'h0000_0077);
        // Incr config RW: src_incr=0x045, dst_incr=0x123, both enabled
        // Write layout: [27:16]=dst_incr, [15:4]=src_incr, [1]=dst_en, [0]=src_en
        env.apb_write(16'h004C, 32'h0123_0453);
        env.apb_read(16'h004C, rd);
        if (rd[0] && rd[1] && (rd[27:16]==12'h123) && (rd[15:4]==12'h045))
            t_pass("incr RW"); else t_fail("incr");
        // Chunk size RW
        env.apb_write(16'h002C, 32'h0000_0003); env.apb_read(16'h002C, rd);
        if (rd == 3) t_pass("chunk_size RW"); else t_fail("chunk_size");
        // Intr enable RW
        env.apb_write(16'h0044, 32'h0000_0007); env.apb_read(16'h0044, rd);
        if (rd == 32'h0000_0007) t_pass("intr_en RW"); else t_fail("intr_en");

        $display("\n[Test 3] PSLVERR");
        env.apb_read(16'h0064, rd); if (pslverr) t_pass("PSLVERR"); else t_fail("PSLVERR");

        $display("\n[Test 4] Single-word DMA");
        host_data_q = {};
        dma_start(32'h0000_1000, 32'h0000_2000, 1, 3'h2, 1);
        dma_wait_done(200);
        if (intr_dma_done) t_pass("done"); else t_fail("done");

        $display("\n[Test 5] Multi-word DMA (4)");
        dma_stop(); host_data_q = {};
        dma_start(32'h0000_3000, 32'h0000_4000, 4, 3'h2, 4);
        dma_wait_done(400);
        if (intr_dma_done) t_pass("4-word done"); else t_fail("4-word done");

        $display("\n[Test 6] Transfer width = byte");
        dma_stop(); host_data_q = {};
        dma_start(32'h0000_5000, 32'h0000_6000, 2, 3'h0, 2);
        dma_wait_done(400);
        if (intr_dma_done) t_pass("byte done"); else t_fail("byte done");

        $display("\n[Test 7] Transfer width = half-word");
        dma_stop(); host_data_q = {};
        dma_start(32'h0000_7000, 32'h0000_8000, 3, 3'h1, 3);
        dma_wait_done(400);
        if (intr_dma_done) t_pass("half-word done"); else t_fail("half-word done");

        $display("\n[Test 8] Chunk interrupt (chunk_size=3, total=6)");
        dma_stop(); host_data_q = {};
        env.apb_write(16'h0000, 32'h0000_9000);
        env.apb_write(16'h0008, 32'h0000_A000);
        env.apb_write(16'h0028, 32'h0000_0006);
        env.apb_write(16'h002C, 32'h0000_0003);  // chunk_size=3
        env.apb_write(16'h0030, 3'h2);
        for (int i = 0; i < 6; i++) host_data_q.push_back((32'hBEEF_0000 + i));
        env.apb_write(16'h0044, 32'h0000_0007);
        env.apb_write(16'h0034, 32'h0000_0005);
        dma_wait_done(600);
        if (intr_dma_done)  t_pass("chunk: done"); else t_fail("chunk: done");
        if (intr_dma_chunk) t_pass("chunk: intr"); else t_fail("chunk: intr");

        $display("\n[Test 9] Error injection");
        dma_stop(); host_data_q = {};
        env.apb_write(16'h0040, 32'h0000_0007);
        env.apb_write(16'h0000, 32'h0000_B000);
        env.apb_write(16'h0008, 32'h0000_C000);
        env.apb_write(16'h0028, 32'h0000_0001);
        env.apb_write(16'h0030, 3'h2);
        host_data_q.push_back(32'hCAFE_CAFE);
        env.apb_write(16'h0044, 32'h0000_0007);
        error_inject = 1;
        env.apb_write(16'h0034, 32'h0000_0005);
        dma_wait_done(400);
        error_inject = 0;
        if (intr_dma_error) t_pass("error: intr"); else t_fail("error: intr");
        env.apb_read(16'h003C, rd);
        if (rd == 4'h2) t_pass("error: code=2"); else t_fail("error: code");

        $display("\n[Test 10] DMA stop with stop_q=1 (aborts mid-transfer)");
        dma_stop(); host_data_q = {};
        env.apb_write(16'h0000, 32'h0000_D000);
        env.apb_write(16'h0008, 32'h0000_E000);
        env.apb_write(16'h0028, 32'h0000_000A);
        env.apb_write(16'h0030, 3'h2);
        for (int i = 0; i < 10; i++) host_data_q.push_back((32'hDAAA_0000 + i));
        env.apb_write(16'h0044, 32'h0000_0007);
        env.apb_write(16'h0034, 32'h0000_0005);
        #200;
        env.apb_write(16'h0034, 32'h0000_0002);  // stop_q=1 (bit 1), start=0, enable=0
        #500;
        if (!dut.busy_q) t_pass("stopped by stop_q"); else t_fail("still busy");

        $display("\n[Test 11] Incr config + multi-xfer");
        dma_stop(); host_data_q = {};
        env.apb_write(16'h0000, 32'h0000_F000);
        env.apb_write(16'h0008, 32'h0000_0100);
        env.apb_write(16'h0028, 32'h0000_0002);
        env.apb_write(16'h0030, 3'h2);
        // Enable src increment by 16, dst increment by 32
        env.apb_write(16'h004C, 32'h0020_0010);  // dst_incr=0x20, src_incr=0x10, en=1
        for (int i = 0; i < 2; i++) host_data_q.push_back((32'hA5A5_0000 + i));
        env.apb_write(16'h0044, 32'h0000_0007);
        env.apb_write(16'h0034, 32'h0000_0005);
        dma_wait_done(400);
        if (intr_dma_done) t_pass("incr: done"); else t_fail("incr: done");

        $display("\n[Test 12] Multi-config transfers");
        dma_stop(); host_data_q = {};
        dma_start(32'h0000_F100, 32'h0000_0200, 2, 3'h2, 2);
        dma_wait_done(400);
        if (intr_dma_done) t_pass("xfer1"); else t_fail("xfer1");
        dma_stop(); host_data_q = {};
        dma_start(32'h0000_F200, 32'h0000_0300, 1, 3'h1, 1);
        dma_wait_done(400);
        if (intr_dma_done) t_pass("xfer2"); else t_fail("xfer2");

        $display("\n=== RESULT: PASS=%0d FAIL=%0d ===", pass, fail);
        env.report();
        $finish;
    end

endmodule
