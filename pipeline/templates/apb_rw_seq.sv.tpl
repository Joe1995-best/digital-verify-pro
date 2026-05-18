// {{ module_name }} — APB Read/Write Sequence (auto-generated)

class apb_rw_seq extends base_seq;
  `uvm_object_utils(apb_rw_seq)

  rand int addr;
  rand int data;
  rand bit write;
  rand int delay;

  constraint c_addr { addr inside {[0:{{ (2 ** apb.addr_width|default(12)) - 1 }}]}; }
  constraint c_delay { delay inside {[0:3]}; }

  function new(string n = "apb_rw_seq"); super.new(n); endfunction

  task body();
    apb_txn txn = apb_txn::type_id::create("txn");
    txn.addr  = addr;
    txn.data  = write ? data : 0;
    txn.write = write;
    txn.delay = delay;
    `uvm_info(get_type_name(), $sformatf(
      "APB %s: addr=0x%0h data=0x%0h delay=%0d",
      write ? "WRITE" : "READ", addr, data, delay), UVM_MEDIUM)
    start_item(txn);
    finish_item(txn);
    if (!write)
      `uvm_info(get_type_name(), $sformatf("Read data=0x%0h", txn.data), UVM_MEDIUM)
  endtask
endclass
