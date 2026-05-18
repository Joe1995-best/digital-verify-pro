// {{ module_name }} — APB Driver (auto-generated)

class apb_driver extends uvm_driver;
  `uvm_component_utils(apb_driver)
  virtual apb_if vif;

  function new(string n, uvm_component p); super.new(n, p); endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(apb_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "apb_if not set")
  endfunction

  task run_phase(uvm_phase phase);
    @(posedge vif.{{ clk_name }});
    forever begin
      seq_item_port.get_next_item(req);
      drive_transaction(req);
      seq_item_port.item_done();
    end
  endtask

  task drive_transaction(apb_txn txn);
    @(posedge vif.drv_cb);
    vif.drv_cb.psel   <= 1;
    vif.drv_cb.pwrite <= txn.write;
    vif.drv_cb.paddr  <= txn.addr;
    vif.drv_cb.pwdata <= txn.write ? txn.data : '0;
    repeat (txn.delay) @(posedge vif.drv_cb);
    vif.drv_cb.penable <= 1;
    do @(posedge vif.drv_cb); while (!vif.drv_cb.pready);
    txn.data = vif.drv_cb.prdata;
    if (vif.drv_cb.pslverr)
      `uvm_warning(get_type_name(), $sformatf("PSLVERR on APB %s addr=0x%0h",
        txn.write ? "WR" : "RD", txn.addr))
    vif.drv_cb.penable <= 0;
    @(posedge vif.drv_cb);
  endtask
endclass : apb_driver
