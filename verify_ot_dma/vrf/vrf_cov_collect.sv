// vrf_cov_collect.sv — Functional coverage collector
// Register access coverage, DMA transfer coverage, FSM state coverage

interface cov_collect (
    input logic        clk,
    input logic        rst_n,

    // APB interface (for tracking register access)
    input logic        psel,
    input logic        penable,
    input logic        pwrite,
    input logic [15:0] paddr,
    input logic [31:0] prdata,

    // DMA internal signals (for FSM tracking)
    input logic        busy,
    input logic        active,
    input logic        done,
    input logic        error_flag,
    input logic [2:0]  state_q,  // direct from DUT for FSM tracking

    // DMA transfer parameters
    input logic [31:0] total_data_size,
    input logic [2:0]  transfer_width,

    // Host interface
    input logic        host_req,
    input logic        host_we,
    input logic        host_rvalid,
    input logic        host_err,

    // Interrupts
    input logic        intr_done,
    input logic        intr_chunk,
    input logic        intr_error
);

    // ── Register access coverage ──
    covergroup reg_access_cg @(posedge clk);
        REG_ADDR: coverpoint paddr {
            bins known[] = {
                16'h0000, 16'h0004, 16'h0008, 16'h000C, 16'h0010,
                16'h0028, 16'h002C, 16'h0030, 16'h0034,
                16'h0038, 16'h003C, 16'h0040, 16'h0044, 16'h004C
            };
            bins reserved = {[16'h0050:16'h0064]};
            illegal_bins other = default;
        }
        REG_ACCESS: coverpoint pwrite;
        REG_ACCESS_X REG_ADDR: cross REG_ADDR, REG_ACCESS;
    endgroup

    // ── DMA FSM state coverage ──
    covergroup fsm_cg @(posedge clk);
        DMA_STATE: coverpoint state_q {
            bins idle     = {0};  // DmaIdle
            bins read     = {1};  // DmaRead
            bins send_rd  = {2};  // DmaSendRead
            bins wait_rd  = {3};  // DmaWaitRead
            bins write    = {4};  // DmaWrite
            bins send_wr  = {5};  // DmaSendWrite
            bins wait_wr  = {6};  // DmaWaitWrite
            bins done_st  = {7};  // DmaDone
        }
        BUSY: coverpoint busy;
        ACTIVE: coverpoint active;
    endgroup

    // ── DMA Transfer coverage ──
    covergroup transfer_cg @(posedge clk);
        TRANSFER_SIZE: coverpoint total_data_size {
            bins single = {1};
            bins small  = {[2:4]};
            bins medium = {[5:8]};
            bins large  = {[9:16]};
        }
        WIDTH: coverpoint transfer_width {
            bins byte   = {0};
            bins half   = {1};
            bins word   = {2};
        }
        DONE: coverpoint done;
        ERROR: coverpoint error_flag;
        INTR_DONE: coverpoint intr_done;
        INTR_ERROR: coverpoint intr_error;
        HOST_ERR: coverpoint host_err;
        // Cross: transfer size × width
        SIZE_X_WIDTH: cross TRANSFER_SIZE, WIDTH;
        // Cross: done × error
        DONE_X_ERR: cross DONE, ERROR;
    endgroup

    // ── Host interface coverage ──
    covergroup host_cg @(posedge clk);
        HOST_REQ: coverpoint host_req {
            bins asserted = {1};
        }
        HOST_WE: coverpoint host_we {
            bins read  = {0};
            bins write = {1};
        }
        HOST_RVALID: coverpoint host_rvalid;
        HOST_REQ_X_WE: cross HOST_REQ, HOST_WE;
    endgroup

    // Constructor
    function new();
        reg_access_cg  = new();
        fsm_cg         = new();
        transfer_cg    = new();
        host_cg        = new();
    endfunction

    // Print coverage summary
    function void report();
        $display("[COV] Coverage report:");
        $display("  Register access:  %0d/%0d bins",
                 reg_access_cg.get_cover_FC() * 100 > 0 ? 1 : 0, 0);
        $display("  FSM states:       %0.1f%%", fsm_cg.get_coverage());
        $display("  Transfers:        %0.1f%%", transfer_cg.get_coverage());
        $display("  Host interface:   %0.1f%%", host_cg.get_coverage());
    endfunction
endinterface
