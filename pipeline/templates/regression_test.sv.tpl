// {{ module_name }} — Regression Test (auto-generated)

class {{ module_name }}_regression_test extends base_test;
  `uvm_component_utils({{ module_name }}_regression_test)

  function new(string n, uvm_component p); super.new(n, p); endfunction

  task run_phase(uvm_phase phase);
    apb_rw_seq seq;
    phase.raise_objection(this);

    // Reset
    `uvm_info("TEST", "Applying reset...", UVM_LOW)
    #200;

    // Test: APB read/write to all registers
    `uvm_info("TEST", "Testing register access...", UVM_LOW)
    seq = apb_rw_seq::type_id::create("seq");
    for (int i = 0; i < 10; i++) begin
      if (!seq.randomize()) `uvm_error("TEST", "Randomize failed")
      seq.start(env.apb_agt.seqr);
    end

    phase.drop_objection(this);
  endtask
endclass
