// {{ module_name }} — Base Test (auto-generated)

import uvm_pkg::*;

class base_test extends uvm_test;
  `uvm_component_utils(base_test)

  {{ module_name }}_env env;

  function new(string n, uvm_component p); super.new(n, p); endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    env = {{ module_name }}_env::type_id::create("env", this);
  endfunction

  function void end_of_elaboration_phase(uvm_phase phase);
    uvm_top.print_topology();
  endfunction

  function void report_phase(uvm_phase phase);
    uvm_report_server svr = uvm_report_server::get_server();
    if (svr.get_severity_count(UVM_FATAL) + svr.get_severity_count(UVM_ERROR) > 0)
      `uvm_info("RESULT", "*** TEST FAILED ***", UVM_LOW)
    else
      `uvm_info("RESULT", "*** TEST PASSED ***", UVM_LOW)
  endfunction
endclass : base_test
