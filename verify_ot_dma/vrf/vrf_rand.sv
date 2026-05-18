// vrf_rand.sv — Verification Random Framework (iverilog-compatible)
// Weighted random selection, pattern generation, valid value pools

// DMA register address pool
function automatic [15:0] pick_reg_addr();
    int r = {$urandom} % 20;
    // 90% valid addresses, 10% reserved (for PSLVERR)
    if (r < 18) begin
        int idx = {$urandom} % 14;
        case (idx)
            0: return 16'h0000;  // src_addr_lo
            1: return 16'h0004;  // src_addr_hi
            2: return 16'h0008;  // dst_addr_lo
            3: return 16'h000C;  // dst_addr_hi
            4: return 16'h0010;  // asid
            5: return 16'h0028;  // total_size
            6: return 16'h002C;  // chunk_size
            7: return 16'h0030;  // transfer_width
            8: return 16'h0034;  // ctrl (enable/start/stop)
            9: return 16'h0038;  // status (RO)
            10: return 16'h003C; // error_code (RO)
            11: return 16'h0040; // intr_status (RO)
            12: return 16'h0044; // intr_enable
            13: return 16'h004C; // incr_config
        endcase
    end else begin
        // Reserved address
        return {$urandom} % 16 + 16'h0050;
    end
endfunction

// Random data pattern (for coverage diversity)
function automatic [31:0] random_data_pattern(input int idx);
    int r = idx % 8;
    case (r)
        0: return 32'h0000_0000;           // all zeros
        1: return 32'hFFFF_FFFF;           // all ones
        2: return 32'hA5A5_A5A5;           // alternating A5
        3: return 32'h5A5A_5A5A;           // alternating 5A
        4: return 32'hF0F0_F0F0;           // nibble pattern
        5: return 32'h0F0F_0F0F;           // inverted nibble
        6: return 32'hFF00_00FF;           // byte swap
        7: return {$urandom};              // true random
    endcase
endfunction

// Random DMA transfer size (weighted: 1 is most common)
function automatic [31:0] random_transfer_size();
    int r = {$urandom} % 100;
    if (r < 30) return 1;
    if (r < 70) return {$urandom} % 4 + 2;    // 2-5
    if (r < 90) return {$urandom} % 4 + 6;    // 6-9
    return {$urandom} % 8 + 10;                // 10-17
endfunction

// Random DMA transfer width (0=byte, 1=halfword, 2=word)
function automatic [2:0] random_transfer_width();
    int r = {$urandom} % 100;
    if (r < 40) return 0;  // byte
    if (r < 75) return 1;  // half-word
    return 2;               // word
endfunction

// Random aligned address (aligned to transfer width)
function automatic [31:0] random_aligned_addr(input [2:0] width);
    int r = {$urandom} % 4;
    case (r)
        0: return 32'h0000_1000;
        1: return 32'h0000_2000;
        2: return 32'h0000_3000;
        3: return 32'h0000_4000;
    endcase
endfunction

// Random host response data
function automatic [31:0] random_host_data();
    int r = {$urandom} % 5;
    case (r)
        0: return 32'hDEAD_BEEF;
        1: return 32'hCAFE_CAFE;
        2: return 32'hA5A5_A5A5;
        3: return 32'h5A5A_5A5A;
        4: return {$urandom};
    endcase
endfunction
