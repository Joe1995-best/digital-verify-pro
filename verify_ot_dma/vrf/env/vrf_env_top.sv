// vrf_env_top.sv — Verification environment top module (v3)
// Wires together: APB driver + assertions + checkers
// Host responder is now in the testbench (proven shift-register approach)

module vrf_env_top (
    input logic clk,
    input logic rst_n,

    // APB interface (to DUT)
    output logic       psel,
    output logic       penable,
    output logic       pwrite,
    output logic [15:0] paddr,
    output logic [31:0] pwdata,
    input  logic [31:0] prdata,
    input  logic        pready,
    input  logic        pslverr,

    // Host interface (monitor only — driven by TB)
    input  logic        host_gnt,
    input  logic [31:0] host_rdata,
    input  logic        host_rvalid,
    input  logic        host_err,
    input  logic        host_req,
    input  logic        host_we,
    input  logic [31:0] host_addr,
    input  logic [31:0] host_wdata,

    // DMA status (for assertions)
    input logic        dma_busy,
    input logic        dma_done,
    input logic        dma_error,
    input logic [2:0]  dma_state,
    input logic        dma_start,
    input logic        dma_enable,

    // Interrupts (from DUT)
    input logic        intr_done,
    input logic        intr_error
);

    // ── Initialization ──
    initial begin
        psel = 0; penable = 0; pwrite = 0; paddr = 0; pwdata = 0;
    end

    // ── Assertion instances ──
    vrf_assert_apb u_assert_apb (
        .clk, .rst_n,
        .psel, .penable, .pwrite, .paddr, .pwdata,
        .prdata, .pready, .pslverr
    );

    vrf_assert_fsm #(
        .N_STATES(8),
        .TIMEOUT_CYCLES(500)
    ) u_assert_fsm (
        .clk, .rst_n,
        .state_q(dma_state),
        .busy(dma_busy),
        .done(dma_done),
        .error(dma_error)
    );

    vrf_assert_dma #(
        .HOST_REQ_TIMEOUT(500)
    ) u_assert_dma (
        .clk, .rst_n,
        .start(dma_start),
        .enable(dma_enable),
        .busy(dma_busy),
        .done(dma_done),
        .error_flag(dma_error),
        .host_req, .host_we,
        .host_gnt, .host_rvalid,
        .intr_done, .intr_error
    );

    // ── APB driver tasks ──
    task apb_write(input [15:0] a, input [31:0] d);
        @(posedge clk); #1;
        psel = 1; penable = 0; pwrite = 1; paddr = a; pwdata = d;
        @(posedge clk); #1; penable = 1;
        @(posedge clk); #1; psel = 0; penable = 0;
    endtask

    task apb_read(input [15:0] a, output [31:0] d);
        @(posedge clk); #1;
        psel = 1; penable = 0; pwrite = 0; paddr = a;
        @(posedge clk); #1; penable = 1;
        @(posedge clk); #1; d = prdata; psel = 0; penable = 0;
    endtask

    // ── Report ──
    task report();
        $display("\n=== ENV REPORT ===");
        u_assert_apb.report();
        u_assert_fsm.report();
        u_assert_dma.report();
        $display("=== END ENV REPORT ===\n");
    endtask

endmodule
