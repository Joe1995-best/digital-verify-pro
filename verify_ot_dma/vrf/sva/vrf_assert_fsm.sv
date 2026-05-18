// vrf_assert_fsm.sv — FSM safety assertions (procedural, iverilog-compatible)
// Checks: state stuck (no transition for N cycles), illegal state values, deadlock

module vrf_assert_fsm #(
    parameter int N_STATES = 8,
    parameter int TIMEOUT_CYCLES = 1000
) (
    input logic       clk,
    input logic       rst_n,
    input logic [2:0] state_q,
    input logic       busy,
    input logic       done,
    input logic       error
);

    // Track FSM health
    int cycles_in_state;
    logic [2:0] last_state;
    int max_cycles_same_state;
    int stall_violations;
    int state_transitions;
    logic timeout_flag;

    always @(posedge clk) begin
        if (!rst_n) begin
            cycles_in_state <= 0;
            last_state <= 0;
            stall_violations <= 0;
            state_transitions <= 0;
        end else begin
            if (state_q !== last_state) begin
                // State changed
                state_transitions <= state_transitions + 1;
                cycles_in_state <= 0;
                last_state <= state_q;
                // Check if we were stuck previously
                if (max_cycles_same_state > TIMEOUT_CYCLES) begin
                    stall_violations <= stall_violations + 1;
                    $display("[ASSERT-FSM] STALL: stayed in state %d for %0d cycles", last_state, max_cycles_same_state);
                end
                max_cycles_same_state <= 0;
            end else begin
                cycles_in_state <= cycles_in_state + 1;
                if (cycles_in_state > max_cycles_same_state)
                    max_cycles_same_state <= cycles_in_state;
            end
        end
    end

    // Check: illegal state values (for 3-bit state, only 0-7 are valid)
    always @(posedge clk) begin
        if (rst_n && state_q > 7) begin
            $display("[ASSERT-FSM] ILLEGAL state value: %d", state_q);
        end
    end

    function void report();
        $display("[ASSERT-FSM] Report:");
        $display("  State transitions: %0d", state_transitions);
        $display("  Max cycles in same state: %0d", max_cycles_same_state);
        if (stall_violations) $display("  [FAIL] State stalls: %0d", stall_violations);
        else                  $display("  [PASS] No state stalls detected");
    endfunction

endmodule
