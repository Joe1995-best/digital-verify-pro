// vrf_driver_host.sv — DMA Host TL-UL interface driver
// Grants access, provides read data, completes writes

interface host_driver (
    input  logic        clk,
    input  logic        host_req,
    input  logic        host_we,
    input  logic [31:0] host_addr,
    input  logic [31:0] host_wdata,
    output logic        host_gnt,
    output logic [31:0] host_rdata,
    output logic        host_rvalid,
    output logic        host_err
);
    // Provide read data (single-word response)
    task automatic read_rsp(input [31:0] rdata, input int delay_cycles);
        // Wait for request if not already active
        if (!host_req) begin
            @(posedge clk);
            wait(host_req);
        end
        // Grant the request
        @(posedge clk);
        host_gnt = 1;
        // Hold grant for delay
        repeat (delay_cycles) @(posedge clk);
        host_gnt = 0;
        // After 1-2 cycles, return data
        @(posedge clk);
        host_rdata = rdata;
        host_rvalid = 1;
        @(posedge clk);
        host_rvalid = 0;
    endtask

    // Complete a write (single-word completion)
    task automatic write_rsp(input int delay_cycles);
        if (!host_req) begin
            @(posedge clk);
            wait(host_req);
        end
        @(posedge clk);
        host_gnt = 1;
        repeat (delay_cycles) @(posedge clk);
        host_gnt = 0;
        @(posedge clk);
        host_rvalid = 1;  // write complete ack
        @(posedge clk);
        host_rvalid = 0;
    endtask

    // Error response
    task automatic err_rsp();
        if (!host_req) begin
            @(posedge clk);
            wait(host_req);
        end
        @(posedge clk);
        host_gnt = 1;
        @(posedge clk);
        host_gnt = 0;
        @(posedge clk);
        host_err = 1;
        host_rvalid = 1;
        @(posedge clk);
        host_err = 0;
        host_rvalid = 0;
    endtask

    // Full DMA transfer: handle alternating read/write cycles
    task automatic handle_full_transfer(
        input int           n_words,
        input int           delay,
        input bit           inject_error,
        input bit [31:0]    custom_data[$:16]
    );
        for (int i = 0; i < n_words; i++) begin
            // Read phase
            if (!host_req) wait(host_req);
            if (!host_we) begin  // read request
                bit [31:0] rd;
                if (i < custom_data.size())
                    rd = custom_data[i];
                else
                    rd = $urandom;
                if (inject_error && i == n_words/2)
                    err_rsp();
                else
                    read_rsp(rd, delay);
            end else begin  // write request
                write_rsp(delay);
            end
        end
        // Drain any remaining write
        if (host_req && host_we) write_rsp(delay);
    endtask

    // Reset state
    task automatic reset();
        host_gnt = 0;
        host_rdata = 0;
        host_rvalid = 0;
        host_err = 0;
    endtask
endinterface
