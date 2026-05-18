`define uvm_component_utils(T)
`define uvm_object_utils(T)
`define uvm_field_utils(T)
`define uvm_field_int(NAME,FLAGS)
`define uvm_field_sarray_int(NAME,FLAGS)
`define uvm_object_utils_begin(T)
`define uvm_object_utils_end
`define uvm_declare_p_sequencer(T)
`define uvm_info(ID,MSG,VERB) uvm_pkg::uvm_info(ID,MSG,VERB)
`define uvm_warning(ID,MSG) uvm_pkg::uvm_warning(ID,MSG)
`define uvm_error(ID,MSG) uvm_pkg::uvm_error(ID,MSG)
`define uvm_fatal(ID,MSG) uvm_pkg::uvm_fatal(ID,MSG)
`ifndef UVM_DO
`define UVM_DO(SEQ,SEQR) SEQ.set_item_context(SEQR); SEQ.body()
`endif
