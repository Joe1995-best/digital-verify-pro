// tb_dma_core.v — DMA testbench with posedge-sync FSM + 5-cycle rvalid pipeline
`timescale 1ns / 1ps

module tb_dma_core;

    reg         clk_i, rst_ni;
    reg         psel, penable, pwrite;
    reg  [15:0] paddr;
    reg  [31:0] pwdata;
    wire [31:0] prdata;
    wire        pready, pslverr;
    wire        intr_dma_done_o, intr_dma_chunk_done_o, intr_dma_error_o;
    wire [31:0] host_addr_o, host_wdata_o;
    wire        host_req_o, host_we_o;

    wire host_gnt_i;
    assign host_gnt_i = host_req_o;

    reg [31:0] host_rdata_i;
    wire       host_rvalid_w;  // combinatorial rvalid (connected to DUT port directly)
    reg        host_err_i;

    // ═══ 5-cycle shift register for rvalid timing ═══
    // rvalid is COMBINATORIAL assign: DUT combo sees it instantly.
    // Shift register controls duration: 5 cycles after host_req rising edge.
    reg [31:0] host_data_q[$:15];
    reg [4:0] rvalid_pipe;
    assign host_rvalid_w = (rvalid_pipe != 5'd0) ? 1'b1 : 1'b0;

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            rvalid_pipe <= 0;
        end else begin
            // Shift: 1 moves through the pipe, creating a 5-cycle rvalid window
            if (rvalid_pipe > 0) rvalid_pipe <= rvalid_pipe - 1;
            // Load on rising host_req: pop data, start 5-cycle rvalid
            if (host_req_o && !rvalid_pipe[4]) begin
                if (!host_we_o && host_data_q.size() > 0)
                    host_rdata_i <= host_data_q.pop_front();
                rvalid_pipe <= 5'b10000;  // 5-bit, sets bit4 = non-zero = rvalid=1
            end
        end
    end

    ot_dma_core dut (
        .clk_i(clk_i), .rst_ni(rst_ni),
        .psel(psel), .penable(penable), .pwrite(pwrite),
        .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pready(pready), .pslverr(pslverr),
        .intr_dma_done_o(intr_dma_done_o),
        .intr_dma_chunk_done_o(intr_dma_chunk_done_o),
        .intr_dma_error_o(intr_dma_error_o),
        .host_addr_o(host_addr_o), .host_req_o(host_req_o),
        .host_we_o(host_we_o), .host_wdata_o(host_wdata_o),
        .host_gnt_i(host_gnt_i), .host_rdata_i(host_rdata_i),
        .host_rvalid_i(host_rvalid_w),  // use combinatorial signal!
        .host_err_i(host_err_i)
    );
    initial clk_i = 0;
    always #5 clk_i = ~clk_i;
    initial begin $dumpfile("dma_core.vcd"); $dumpvars(0, tb_dma_core); end

    integer pass_count, fail_count;
    reg [31:0] rd;

    task t_ok; input [255:0] n; begin pass_count++; $display("  PASS: %s", n); end endtask
    task t_fail; input [255:0] n; begin fail_count++; $display("  FAIL: %s", n); end endtask

    task apb_wr; input [15:0] a; input [31:0] d;
        @(posedge clk_i); #1; psel=1; penable=0; pwrite=1; paddr=a; pwdata=d;
        @(posedge clk_i); #1; penable=1;
        @(posedge clk_i); #1; psel=0; penable=0;
    endtask

    task apb_rd; input [15:0] a; output [31:0] d;
        @(posedge clk_i); #1; psel=1; penable=0; pwrite=0; paddr=a;
        @(posedge clk_i); #1; penable=1;
        @(posedge clk_i); #1; d=prdata; psel=0; penable=0;
    endtask

    initial begin
        pass_count=0; fail_count=0; host_data_q = {}; rvalid_pipe = 0;
        psel=0; penable=0; pwrite=0; paddr=0; pwdata=0;
        host_rdata_i=0; host_err_i=0;

        rst_ni = 1; #2; rst_ni = 0; #30; rst_ni = 1; #100;

        $display("=== DMA Verification ===");

        // Test 1-3: same as before
        $display("[Test 1] Register reset");
        apb_rd(16'h0000, rd); if (rd==0) t_ok("src_addr_lo=0"); else t_fail("src_addr_lo");
        apb_rd(16'h0038, rd); if (rd[1:0]==0) t_ok("status=0"); else t_fail("status");
        apb_rd(16'h0010, rd); if (rd[3:0]==4'h7) t_ok("asid=7"); else t_fail("asid");

        $display("[Test 2] RW registers");
        apb_wr(16'h0028, 32'h000A);
        apb_rd(16'h0028, rd); if (rd==32'hA) t_ok("total_size"); else t_fail("total_size");
        apb_wr(16'h0000, 32'hA5A5_A5A5);
        apb_rd(16'h0000, rd); if (rd==32'hA5A5A5A5) t_ok("src_addr"); else t_fail("src_addr");
        apb_wr(16'h0030, 3'h2);
        apb_rd(16'h0030, rd); if (rd[2:0]==3'h2) t_ok("width"); else t_fail("width");

        $display("[Test 3] PSLVERR");
        apb_rd(16'h0064, rd); if (pslverr) t_ok("PSLVERR"); else t_fail("PSLVERR");

        // Test 4: DMA single-word
        $display("[Test 4] DMA single-word");
        apb_wr(16'h0000, 32'h0000_1000);
        apb_wr(16'h0008, 32'h0000_2000);
        apb_wr(16'h0028, 32'h0000_0001);
        apb_wr(16'h0030, 3'h2);
        host_data_q.push_back(32'hDEAD_BEEF);
        apb_wr(16'h0034, 32'h0000_0005);

        #500;
        apb_rd(16'h0038, rd);
        $display("  Status=%08h done=%b err=%b busy=%b state=%d rem=%0d",
                 rd, rd[4], rd[3], rd[1], dut.state_q, dut.remaining_q);
        if (rd[4]) t_ok("DMA done"); else t_fail("DMA done");

        // Test 5: Multi-word DMA
        $display("[Test 5] DMA multi-word (4)");
        apb_wr(16'h0000, 32'h0000_3000);
        apb_wr(16'h0008, 32'h0000_4000);
        apb_wr(16'h0028, 32'h0000_0004);
        apb_wr(16'h0030, 3'h2);
        host_data_q = {};
        host_data_q.push_back(32'hA5A5_0000);
        host_data_q.push_back(32'hA5A5_0001);
        host_data_q.push_back(32'hA5A5_0002);
        host_data_q.push_back(32'hA5A5_0003);
        apb_wr(16'h0034, 32'h0000_0005);
        #1000;
        apb_rd(16'h0038, rd);
        $display("  Status=%08h done=%b state=%d", rd, rd[4], dut.state_q);
        if (rd[4]) t_ok("Multi-word DMA"); else t_fail("Multi-word DMA");

        // Test 6: Interrupt
        $display("[Test 6] Interrupt");
        apb_wr(16'h0044, 32'h0000_0001);
        apb_wr(16'h0000, 32'h0000_5000);
        apb_wr(16'h0008, 32'h0000_6000);
        apb_wr(16'h0028, 32'h0000_0001);
        apb_wr(16'h0030, 3'h2);
        host_data_q.push_back(32'hCAFE);
        apb_wr(16'h0034, 32'h0000_0005);
        #500;
        if (intr_dma_done_o) t_ok("intr_done"); else t_fail("intr_done");
        apb_rd(16'h0040, rd);
        if (rd[0]) t_ok("intr status"); else t_fail("intr status");

        $display("\n=== RESULT: PASS=%0d FAIL=%0d ===", pass_count, fail_count);
        $finish;
    end
    initial #10000 begin $display("TIMEOUT"); $finish; end
endmodule
