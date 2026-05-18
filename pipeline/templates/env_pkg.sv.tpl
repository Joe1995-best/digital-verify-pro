// {{ module_name }} — UVM Environment Package (auto-generated)

package {{ module_name }}_env_pkg;
  import uvm_pkg::*;
  `include "uvm_macros.svh"

  // Transaction objects
  `include "apb_txn.sv"
  // Agent components
  `include "apb_sequencer.sv"
  `include "apb_driver.sv"
  `include "apb_monitor.sv"
  `include "apb_agent.sv"
  // Scoreboard
  `include "{{ module_name }}_sb.sv"
  // Environment
  `include "{{ module_name }}_env.sv"
  // Sequences (included from sequences/)
  // Tests (included from tests/)
endpackage
