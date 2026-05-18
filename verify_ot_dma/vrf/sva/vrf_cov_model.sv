// vrf_cov_model.sv — Coverage model (independent module, no covergroup)
// Tracks: register access, FSM states, transfer config, error codes, interrupts
// Replaces inline always blocks with a standalone instantiable module

module vrf_cov_model (
    input logic clk,
    input logic rst_n,

    // APB interface
    input logic psel,
    input logic penable,
    input logic pwrite,
    input logic [15:0] paddr,

    // DMA FSM
    input logic [2:0] state_q,
    input logic busy,
    input logic active,
    input logic done,
    input logic error_flag,
    input logic [3:0] error_code,

    // DMA config
    input logic [31:0] total_data_size,
    input logic [2:0] transfer_width,
    input logic enable,
    input logic start,
    input logic stop,

    // Host interface
    input logic host_req,
    input logic host_we,
    input logic host_rvalid,
    input logic host_err,

    // Interrupts
    input logic intr_done,
    input logic intr_chunk,
    input logic intr_error
);

    // ── Coverage bins (procedural, iverilog-compatible) ──

    // Register access coverage
    int reg_access_cnt[14];
    bit [15:0] reg_addrs[0:13];
    initial begin
        reg_addrs[0] = 16'h0000; reg_addrs[1] = 16'h0004; reg_addrs[2] = 16'h0008;
        reg_addrs[3] = 16'h000C; reg_addrs[4] = 16'h0010; reg_addrs[5] = 16'h0028;
        reg_addrs[6] = 16'h002C; reg_addrs[7] = 16'h0030; reg_addrs[8] = 16'h0034;
        reg_addrs[9] = 16'h0038; reg_addrs[10] = 16'h003C; reg_addrs[11] = 16'h0040;
        reg_addrs[12] = 16'h0044; reg_addrs[13] = 16'h004C;
    end

    always @(posedge clk) begin
        if (rst_n && psel && penable) begin
            for (int i = 0; i < 14; i++) begin
                if (paddr == reg_addrs[i]) begin
                    reg_access_cnt[i] = reg_access_cnt[i] + 1;
                end
            end
        end
    end

    // FSM state coverage
    int fsm_state_cnt[8];

    always @(posedge clk) begin
        if (rst_n) begin
            if (state_q <= 7) begin
                fsm_state_cnt[state_q] = fsm_state_cnt[state_q] + 1;
            end
        end
    end

    // Transfer config coverage (cross coverage)
    int xfer_size_bins[4];  // 1, 2-4, 5-8, 9+
    int xfer_width_bins[3]; // byte, half, word
    int xfer_size_x_width[12];  // flat: size(4) x width(3)

    int cov_si, cov_wi;
    always @(posedge clk) begin
        if (rst_n && start && enable) begin
            if (total_data_size == 1)        xfer_size_bins[0]++;
            else if (total_data_size <= 4)   xfer_size_bins[1]++;
            else if (total_data_size <= 8)   xfer_size_bins[2]++;
            else                             xfer_size_bins[3]++;
            if (transfer_width <= 3)         xfer_width_bins[transfer_width]++;
            cov_si = (total_data_size==1)?0:(total_data_size<=4)?1:(total_data_size<=8)?2:3;
            cov_wi = (transfer_width<=2)?transfer_width:0;
            if (cov_si < 4 && cov_wi < 3)    xfer_size_x_width[cov_si * 3 + cov_wi]++;
        end
    end

    // Error code coverage
    int err_code_cnt[16];

    always @(posedge clk) begin
        if (rst_n && error_flag) begin
            if (error_code <= 15) err_code_cnt[error_code]++;
        end
    end

    // Host transaction coverage
    int host_read_cnt, host_write_cnt, host_err_cnt;

    always @(posedge clk) begin
        if (rst_n) begin
            if (host_req && !host_we)  host_read_cnt++;
            if (host_req && host_we)   host_write_cnt++;
            if (host_err)             host_err_cnt++;
        end
    end

    // Interrupt coverage
    int intr_done_cnt, intr_chunk_cnt, intr_error_cnt;

    always @(posedge clk) begin
        if (rst_n) begin
            if (intr_done)   intr_done_cnt++;
            if (intr_chunk)  intr_chunk_cnt++;
            if (intr_error)  intr_error_cnt++;
        end
    end

    // ── Coverage report ──
    function void report();
        int rh, fh, eh;
        $display("\n=== COVERAGE MODEL ===");
        rh = 0; for (int i = 0; i < 14; i++) if (reg_access_cnt[i] > 0) rh++;
        $display("  Registers accessed: %0d/14", rh);

        fh = 0; for (int i = 0; i < 8; i++) if (fsm_state_cnt[i] > 0) fh++;
        $display("  FSM states visited: %0d/8", fh);

        $display("  Transfer sizes: 1=%0d 2-4=%0d 5-8=%0d 9+=%0d",
                 xfer_size_bins[0], xfer_size_bins[1], xfer_size_bins[2], xfer_size_bins[3]);
        $display("  Transfer widths: byte=%0d half=%0d word=%0d",
                 xfer_width_bins[0], xfer_width_bins[1], xfer_width_bins[2]);

        eh = 0; for (int i = 0; i < 16; i++) if (err_code_cnt[i] > 0) eh++;
        if (eh > 0) $display("  Error codes hit: %0d", eh);

        $display("  Host: %0d reads, %0d writes, %0d errors",
                 host_read_cnt, host_write_cnt, host_err_cnt);
        $display("  Interrupts: done=%0d chunk=%0d error=%0d",
                 intr_done_cnt, intr_chunk_cnt, intr_error_cnt);
        $display("=== END COVERAGE REPORT ===\n");
    endfunction

endmodule
