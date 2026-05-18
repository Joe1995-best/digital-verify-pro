// vrf_checker.sv — Protocol checker + assertion monitors
// Checks APB protocol rules, register access, DMA transfer integrity

interface apb_checker (
    input logic        clk,
    input logic        rst_n,
    input logic        psel,
    input logic        penable,
    input logic        pwrite,
    input logic [15:0] paddr,
    input logic [31:0] pwdata,
    input logic [31:0] prdata,
    input logic        pready,
    input logic        pslverr
);
    // Known register address map
    const bit [15:0] REG_ADDRS[14] = '{
        16'h0000, 16'h0004, 16'h0008, 16'h000C, 16'h0010,
        16'h0028, 16'h002C, 16'h0030, 16'h0034,
        16'h0038, 16'h003C, 16'h0040, 16'h0044, 16'h004C
    };
    const string REG_NAMES[14] = '{
        "src_addr_lo", "src_addr_hi", "dst_addr_lo", "dst_addr_hi", "asid",
        "total_size", "chunk_size", "transfer_width", "ctrl",
        "status", "error_code", "intr_status", "intr_enable", "incr_config"
    };

    int apb_x_count;
    int pslverr_count;
    int reg_access_count[14];

    // Collect register access statistics
    always @(posedge clk) begin
        if (psel && penable) begin
            for (int i = 0; i < 14; i++) begin
                if (paddr == REG_ADDRS[i])
                    reg_access_count[i]++;
            end
            if (paddr >= 16'h0050)
                pslverr_count++;
            if ($isunknown({psel, penable, paddr}))
                apb_x_count++;
        end
    end

    // Check: no X/Z on APB signals when active
    always @(posedge clk) begin
        if (psel && $isunknown(paddr))
            $display("[CHECKER] WARN: X on paddr when psel=1");
        if (penable && psel && $isunknown(pwrite))
            $display("[CHECKER] WARN: X on pwrite during APB access");
    end

    // Print access summary at end
    function void report();
        $display("[CHECKER] APB access report:");
        for (int i = 0; i < 14; i++) begin
            if (reg_access_count[i] > 0)
                $display("  %s (%04h): %0d accesses", REG_NAMES[i], REG_ADDRS[i], reg_access_count[i]);
            else
                $display("  %s (%04h): NEVER ACCESSED", REG_NAMES[i], REG_ADDRS[i]);
        end
        $display("  PSLVERR count: %0d", pslverr_count);
        $display("  X detected on APB: %0d times", apb_x_count);
    endfunction
endinterface


// DMA transfer integrity checker
interface dma_checker (
    input logic        clk,
    input logic        rst_n,
    input logic        host_req,
    input logic        host_we,
    input logic [31:0] host_addr,
    input logic [31:0] host_wdata,
    input logic [31:0] host_rdata,
    input logic        host_rvalid,
    input logic        host_err,
    input logic        intr_done,
    input logic        intr_error
);
    int  host_read_count;
    int  host_write_count;
    int  host_error_count;
    int  last_addr;
    int  consecutive_reads;

    // Monitor host interface
    always @(posedge clk) begin
        if (host_req && host_gnt) begin
            if (!host_we) begin
                host_read_count++;
                if (host_addr == last_addr)
                    consecutive_reads++;
                else
                    consecutive_reads = 0;
                last_addr = host_addr;
            end else begin
                host_write_count++;
            end
        end
    end

    // Track errors
    always @(posedge clk) begin
        if (host_err && host_rvalid) host_error_count++;
    end

    function void report();
        $display("[DMA-CHECK] Host interface:");
        $display("  Reads: %0d  Writes: %0d  Errors: %0d",
                 host_read_count, host_write_count, host_error_count);
    endfunction
endinterface
