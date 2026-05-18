// {{ module_name }} — Base Sequence (auto-generated)

class base_seq extends uvm_sequence;
  `uvm_object_utils(base_seq)

  function new(string n = "base_seq"); super.new(n); endfunction

  task body();
    `uvm_info(get_type_name(), "Base sequence body — override in subclass", UVM_MEDIUM)
  endtask
endclass
