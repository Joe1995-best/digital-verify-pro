// {{ module_name }} — UVM Environment Configuration (auto-generated)

class {{ module_name }}_env_cfg extends uvm_object;
  `uvm_object_utils({{ module_name }}_env_cfg)

  // Global env config parameters
  int has_coverage       = 1;
  int has_scoreboard     = 1;
  int has_assertions     = 1;
  int max_timeout_ns     = 200000;

  // Agent configs
  int apb_agent_is_active = 1;  // 1=UVM_ACTIVE, 0=UVM_PASSIVE
{% for iface in interfaces %}
  int {{ iface.name }}_agent_is_active = 1;
{% endfor %}

  function new(string name = "{{ module_name }}_env_cfg");
    super.new(name);
  endfunction

  // do_print for debug visibility
  virtual function void do_print(uvm_printer printer);
    printer.print_string("type", get_type_name());
    printer.print_int("has_coverage", has_coverage);
    printer.print_int("has_scoreboard", has_scoreboard);
    printer.print_int("has_assertions", has_assertions);
    printer.print_int("max_timeout_ns", max_timeout_ns);
    printer.print_int("apb_agent_is_active", apb_agent_is_active);
{% for iface in interfaces %}
    printer.print_int("{{ iface.name }}_agent_is_active", {{ iface.name }}_agent_is_active);
{% endfor %}
  endfunction

  // do_compare for config-aware comparisons
  virtual function bit do_compare(uvm_object rhs, uvm_comparer comparer);
    {{ module_name }}_env_cfg rhs_;
    bit same;
    if (!$cast(rhs_, rhs)) return 0;
    same = super.do_compare(rhs, comparer);
    same &= (has_coverage       == rhs_.has_coverage);
    same &= (has_scoreboard     == rhs_.has_scoreboard);
    same &= (has_assertions     == rhs_.has_assertions);
    same &= (max_timeout_ns     == rhs_.max_timeout_ns);
    same &= (apb_agent_is_active == rhs_.apb_agent_is_active);
{% for iface in interfaces %}
    same &= ({{ iface.name }}_agent_is_active == rhs_.{{ iface.name }}_agent_is_active);
{% endfor %}
    return same;
  endfunction

endclass : {{ module_name }}_env_cfg
