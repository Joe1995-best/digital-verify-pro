# Verification Patterns & Templates

Reference patterns for generating digital verification testbenches, inspired by chip-verify extension.

## Sequential Module TB Pattern (APB-based)

```verilog
`timescale 1ns / 1ps
module tb_<MODULE>();
    reg clk, rst_n;
    reg  psel, penable, pwrite;
    reg  [11:0] paddr;
    reg  [31:0] pwdata, prdata;
    wire pready, pslverr;

    <MODULE> dut (.*);

    integer pass=0, fail=0;

    task apb_write(input [11:0] a, input [31:0] d);
        @(posedge clk);
        psel=1; penable=0; pwrite=1; paddr=a; pwdata=d;
        @(posedge clk); penable=1;
        @(posedge clk); while(!pready) @(posedge clk);
        psel=0; penable=0; @(posedge clk);
    endtask

    task apb_read(input [11:0] a, input [31:0] exp);
        @(posedge clk);
        psel=1; penable=0; pwrite=0; paddr=a;
        @(posedge clk); penable=1;
        @(posedge clk); while(!pready) @(posedge clk);
        if(prdata!==exp) begin
            $display("FAIL: %h = %h (exp %h)", a, prdata, exp); fail++;
        end else begin
            $display("PASS: %h = %h", a, prdata); pass++;
        end
        psel=0; penable=0; @(posedge clk);
    endtask

    initial begin
        clk=0; forever #10 clk=~clk;
    end
    initial begin
        rst_n=0; #100; rst_n=1;
    end
    initial begin
        $dumpfile("<MODULE>.vcd"); $dumpvars(0, tb_<MODULE>);
        #150;
        apb_write(12'h00, 32'h000000FF);
        apb_read(12'h00, 32'h000000FF);
        #100;
        if(fail==0) $display("*** ALL TESTS PASSED ***");
        else $display("*** %0d TESTS FAILED ***", fail);
        $finish;
    end
endmodule
```

## Clock Generation Patterns

| Pattern | Code | When to Use |
|---------|------|-------------|
| 50MHz | `always #10 clk = ~clk` | Simple modules |
| 100MHz | `always #5 clk = ~clk` | Higher freq |
| Variable | Use `wait_clk(n)` task | Need cycle count |
| Gate | `AND` control + clk | Power-aware sims |

## Reset Patterns

| Type | Assert | Deassert | Check |
|------|--------|----------|-------|
| Async active-low | `rst_n = 0` | `#100; rst_n = 1` | All regs = 0 |
| Sync | `@(posedge clk); rst=1` | `@(posedge clk); rst=0` | All regs = reset val |

## Assertion Styles

```verilog
// Direct check
if (actual !== expected)
    $error("FAIL: %s", msg);

// Macro-style (less verbose)
`CHECK_EQ(actual, expected, "test_name")

// UVM-style (when UVM available)
`uvm_info("TEST", "checking...", UVM_LOW)
```

## Coverage Patterns

```verilog
// Toggle: automatically captured in VCD
// Functional: count which tests passed
// FSM: check all states visited in simulation log
```

## VCD Debug Workflow

```bash
# List all signals
python vdump.py <file>.vcd signals

# Check value at time
python vdump.py <file>.vcd value <signal> <time_ns>

# Sample at clock edges
python vdump.py <file>.vcd sample <clk> <signal> -b 0 -e 1000

# Find when signal = value
python vdump.py <file>.vcd find <signal> <value>
```
