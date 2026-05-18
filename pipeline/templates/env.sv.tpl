// {{ module_name }} — UVM Environment (auto-generated)

class {{ module_name }}_env extends uvm_env;
  `uvm_component_utils({{ module_name }}_env)

  // BFM handle for protocol-level access from sequences
  virtual {{ module_name }}_bfm bfm;

  apb_agent apb_agt;
  {{ module_name }}_sb   sb;

  function new(string n, uvm_component p); super.new(n, p); endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    apb_agt = apb_agent::type_id::create("apb_agt", this);
    uvm_config_db::set(this, "apb_agt", "is_active", UVM_ACTIVE);
    sb = {{ module_name }}_sb::type_id::create("sb", this);
    // Get BFM from config
    if (!uvm_config_db#({{ module_name }}_bfm)::get(this, "", "bfm", bfm))
      `uvm_warning("NOBFM", "{{ module_name }}_bfm not set via uvm_config_db")
  endfunction

  function void connect_phase(uvm_phase phase);
    apb_agt.mon.mon_analysis_port.connect(sb.apb_export);
  endfunction

  function void check_phase(uvm_phase phase);
    int err_count;
    err_count = sb.get_error_count();
    if (err_count > 0) begin
      `uvm_error(get_type_name(), $sformatf(
        "Check phase: %0d error(s) detected in scoreboard", err_count))
    end else begin
      `uvm_info(get_type_name(), "Check phase: All scoreboard comparisons passed", UVM_LOW)
    end
  endfunction
endclass : {{ module_name }}_env
