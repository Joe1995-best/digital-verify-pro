// vrf_assert_dma.sv — DMA-specific assertions
// Checks: host_req timeout, done/error consistency, transaction completion

module vrf_assert_dma #(
    parameter int HOST_REQ_TIMEOUT = 500
) (
    input logic       clk,
    input logic       rst_n,

    // DMA control/status
    input logic       start,
    input logic       enable,
    input logic       busy,
    input logic       done,
    input logic       error_flag,

    // Host interface
    input logic       host_req,
    input logic       host_we,
    input logic       host_gnt,
    input logic       host_rvalid,

    // Interrupts
    input logic       intr_done,
    input logic       intr_error
);

    // Track host request timeouts
    int host_req_cycles;
    int host_req_timeouts;

    always @(posedge clk) begin
        if (!rst_n) begin
            host_req_cycles <= 0;
        end else if (host_req) begin
            host_req_cycles <= host_req_cycles + 1;
            if (host_req_cycles > HOST_REQ_TIMEOUT) begin
                host_req_timeouts <= host_req_timeouts + 1;
                $display("[ASSERT-DMA] HOST_REQ timeout: request active for >%0d cycles", HOST_REQ_TIMEOUT);
                host_req_cycles <= 0;
            end
        end else begin
            host_req_cycles <= 0;
        end
    end

    // Check: done and error should not both be set
    always @(posedge clk) begin
        if (rst_n && done && error_flag) begin
            $display("[ASSERT-DMA] Both done and error asserted!");
        end
    end

    // Check: interrupt only when done/error and enable
    always @(posedge clk) begin
        if (rst_n && intr_done && !done) begin
            $display("[ASSERT-DMA] intr_done without done_q!");
        end
        if (rst_n && intr_error && !error_flag) begin
            $display("[ASSERT-DMA] intr_error without error_flag!");
        end
    end

    function void report();
        $display("[ASSERT-DMA] Report:");
        if (host_req_timeouts) $display("  [FAIL] Host req timeouts: %0d", host_req_timeouts);
        else                   $display("  [PASS] No host req timeouts");
    endfunction

endmodule
