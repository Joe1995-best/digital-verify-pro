// vrf_assert_apb.sv — APB protocol checkers (procedural, works with iverilog 11)
// Checks: X detection, addr stability, psel/penable protocol, pready validity

module vrf_assert_apb (
    input logic       clk,
    input logic       rst_n,
    input logic       psel,
    input logic       penable,
    input logic       pwrite,
    input logic [15:0] paddr,
    input logic [31:0] pwdata,
    input logic [31:0] prdata,
    input logic        pready,
    input logic        pslverr
);

    // Track violations
    int violation_x;
    int violation_penable_no_psel;
    int violation_addr_change;
    int violation_ready_no_psel;
    int total_apb_xfers;

    logic [15:0] last_paddr;
    logic        last_psel;

    always @(posedge clk) begin
        if (!rst_n) begin last_paddr <= 0; last_psel <= 0; end
        else begin last_paddr <= paddr; last_psel <= psel; end
    end

    // Check: X detection on control signals
    always @(*) begin
        if (psel !== 0 && psel !== 1) begin
            violation_x = violation_x + 1;
            $display("[ASSERT] X on psel at time %0t", $time);
        end
        if (penable !== 0 && penable !== 1) begin
            violation_x = violation_x + 1;
            $display("[ASSERT] X on penable at time %0t", $time);
        end
    end

    // Check: penable only if psel was high last cycle
    always @(posedge clk) begin
        if (rst_n && penable && !last_psel) begin
            violation_penable_no_psel <= violation_penable_no_psel + 1;
            $display("[ASSERT] penable without psel at time %0t", $time);
        end
    end

    // Check: addr stable during access
    always @(posedge clk) begin
        if (rst_n && psel && penable) begin
            total_apb_xfers <= total_apb_xfers + 1;
            if (last_psel && last_paddr !== paddr) begin
                violation_addr_change <= violation_addr_change + 1;
                $display("[ASSERT] addr changed mid-access: %h -> %h at time %0t", last_paddr, paddr, $time);
            end
        end
    end

    // Check: pready only if psel is asserted
    always @(posedge clk) begin
        if (rst_n && pready && !psel) begin
            violation_ready_no_psel <= violation_ready_no_psel + 1;
            $display("[ASSERT] pready without psel at time %0t", $time);
        end
    end

    function void report();
        $display("[ASSERT-APB] Report:");
        $display("  Transactions: %0d", total_apb_xfers);
        if (violation_x)                $display("  [FAIL] X on control: %0d", violation_x);
        if (violation_penable_no_psel)  $display("  [FAIL] penable no psel: %0d", violation_penable_no_psel);
        if (violation_addr_change)      $display("  [FAIL] addr change: %0d", violation_addr_change);
        if (violation_ready_no_psel)    $display("  [FAIL] pready no psel: %0d", violation_ready_no_psel);
        if (total_apb_xfers == 0)       $display("  [WARN] No APB transactions");
    endfunction

endmodule
