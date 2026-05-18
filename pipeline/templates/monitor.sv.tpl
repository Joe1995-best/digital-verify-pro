// {{ module_name }} — APB Monitor (auto-generated)

class apb_monitor extends uvm_monitor;
  `uvm_component_utils(apb_monitor)
  virtual apb_if vif;
  uvm_analysis_port mon_analysis_port;

  function new(string n, uvm_component p); super.new(n, p); endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(apb_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "apb_if not set")
    mon_analysis_port = new("mon_analysis_port", this);
  endfunction

  task run_phase(uvm_phase phase);
    @(posedge vif.{{ clk_name }});
    forever begin
      @(posedge vif.mon_cb.psel);
      apb_txn txn = apb_txn::type_id::create("txn");
      txn.addr  = vif.mon_cb.paddr;
      txn.write = vif.mon_cb.pwrite;
      txn.data  = vif.mon_cb.pwrite ? vif.mon_cb.pwdata : vif.mon_cb.prdata;
      @(posedge vif.mon_cb.pready);
      mon_analysis_port.write(txn);
    end
  endtask
endclass : apb_monitor
