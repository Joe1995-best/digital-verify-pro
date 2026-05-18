// {{ module_name }} — APB Transaction (auto-generated)

class apb_txn extends uvm_sequence_item;
  `uvm_object_utils(apb_txn)

  rand bit [{{ apb.data_width|default(32) - 1 }}:0] addr;
  rand bit [{{ apb.data_width|default(32) - 1 }}:0] data;
  rand bit write;
  rand int delay;

  constraint c_delay { delay inside {[0:3]}; }

  function new(string n = "apb_txn"); super.new(n); endfunction

  function string convert2string();
    return $sformatf("APB %s: addr=0x%0h data=0x%0h delay=%0d",
      write ? "WR" : "RD", addr, data, delay);
  endfunction

  // Enhanced do_print for UVM field printing
  virtual function void do_print(uvm_printer printer);
    super.do_print(printer);
    printer.print_field("addr",  addr,  {{ apb.data_width|default(32) }});
    printer.print_field("data",  data,  {{ apb.data_width|default(32) }});
    printer.print_field("write", write, 1);
    printer.print_field("delay", delay, 32);
  endfunction

  // do_compare override for scoreboard comparison
  virtual function bit do_compare(uvm_comparer comparer, uvm_sequence_item to);
    apb_txn rhs;
    bit same;
    if (!$cast(rhs, to)) begin
      return 0;
    end
    same = super.do_compare(comparer, to);
    same &= (this.addr  == rhs.addr);
    same &= (this.data  == rhs.data);
    same &= (this.write == rhs.write);
    return same;
  endfunction
endclass
