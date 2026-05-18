// {{ module_name }} — Reset Sequence (auto-generated)

class reset_seq extends base_seq;
  `uvm_object_utils(reset_seq)

  function new(string n = "reset_seq"); super.new(n); endfunction

  task body();
    `uvm_info(get_type_name(), "Waiting for reset release...", UVM_MEDIUM)
    repeat (10) @(negedge vif.{{ clk_name }});
  endtask
endclass
