// vrf_driver_apb.sv — APB master driver
// Drives psel/penable/pwrite/paddr/pwdata, receives prdata/pready/pslverr

interface apb_driver (
    input logic        clk,
    output logic       psel,
    output logic       penable,
    output logic       pwrite,
    output logic [15:0] paddr,
    output logic [31:0] pwdata,
    input  logic [31:0] prdata,
    input  logic        pready,
    input  logic        pslverr
);
    // APB write: addr + data
    task automatic write(input [15:0] addr, input [31:0] data);
        @(posedge clk);
        psel = 1; penable = 0; pwrite = 1; paddr = addr; pwdata = data;
        @(posedge clk);
        penable = 1;
        @(posedge clk);
        psel = 0; penable = 0;
    endtask

    // APB read: addr → data
    task automatic read(input [15:0] addr, output [31:0] data,
                        output logic got_slverr);
        @(posedge clk);
        psel = 1; penable = 0; pwrite = 0; paddr = addr; pwdata = 0;
        @(posedge clk);
        penable = 1;
        @(posedge clk);
        data = prdata;
        got_slverr = pslverr;
        psel = 0; penable = 0;
    endtask

    // APB read with auto-check PSLVERR
    task automatic read_check(input [15:0] addr, input [31:0] expected,
                              output logic match);
        logic [31:0] rd;
        logic slv;
        read(addr, rd, slv);
        match = (rd === expected);
    endtask

    // Random register transaction
    task automatic xact(DmaRegTransaction t);
        if (t.is_write) begin
            write(t.addr, t.wdata);
            t.completed = 1;
        end else begin
            logic slv;
            read(t.addr, t.rdata, slv);
            t.got_pslverr = slv;
            t.completed = 1;
        end
    endtask
endinterface
