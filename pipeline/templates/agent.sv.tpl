// {{ module_name }} — APB Agent (auto-generated)

class apb_agent extends uvm_agent;
  `uvm_component_utils(apb_agent)
  apb_sequencer seqr;
  apb_driver    drv;
  apb_monitor   mon;

  function new(string n, uvm_component p); super.new(n, p); endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (get_is_active() == UVM_ACTIVE) begin
      seqr = apb_sequencer::type_id::create("seqr", this);
      drv  = apb_driver::type_id::create("drv", this);
    end
    mon = apb_monitor::type_id::create("mon", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    if (get_is_active() == UVM_ACTIVE)
      drv.seq_item_port.connect(seqr.seq_item_export);
  endfunction
endclass : apb_agent
