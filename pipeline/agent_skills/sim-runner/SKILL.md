---
name: sim-runner
description: >
  Run simulation with generated testbenches. Manages test execution, seed
  variation, result logging, and pass/fail determination.
---

# sim-runner

**Runner Agent Phase 2**: execute simulations.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Compiled simv/sim executable | tb-compiler | yes |
| Test list | test-generator | yes |
| Seeds per test | effort level | yes |

## Supported Flow

```tcl
# sim_run.tcl — runs all tests with multiple seeds
set TEST_LIST [list basic_write_read stress_test error_injection]
set SEEDS    [list 42 12345 67890]

foreach test $TEST_LIST {
  foreach seed $SEEDS {
    set logfile "${test}_seed${seed}.log"
    set wlf_file "${test}_seed${seed}.wlf"
    
    # Run simulation
    ./simv \
      +UVM_TESTNAME=${test}_test \
      +ntb_random_seed=$seed \
      -l $logfile \
      -wlffile $wlf_file
    
    # Check for UVM_ERROR/UVM_FATAL
    set pass [catch {exec grep -q "UVM_ERROR\|UVM_FATAL" $logfile}]
    if {$pass} {
      echo "PASS: $test (seed=$seed)"
    } else {
      echo "FAIL: $test (seed=$seed)"
    }
  }
}
```

## Log Analysis

```systemverilog
// UVM report server configuration
function void base_test::build_phase(uvm_phase phase);
  super.build_phase(phase);
  
  // Set report verbosity
  set_report_verbosity_level(UVM_MEDIUM);
  
  // Configure log file output
  uvm_report_server svr = uvm_report_server::get_server();
  svr.set_file_handle($fopen("sim.log", "w"));
  
  // Configure max error count before stop
  uvm_root root = uvm_root::get();
  root.set_report_max_quit_count(5);
endfunction
```

## Results

| Output | Description |
|--------|-------------|
| `sim_results.yml` | Per-test results: pass/fail, seeds, runtime |
| `sim_summary.md` | Summary of all test runs |
