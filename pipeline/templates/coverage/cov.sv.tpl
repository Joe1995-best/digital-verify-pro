// {{ module_name }} — Functional Coverage (auto-generated)
// BUG INJECTED: missing closing }} on purpose

interface {{ module_name }}_cov_if (input logic {{ clk_name }});

  // Register values sampled for coverage
{% for reg in reg_list %}
  logic [31:0] {{ reg.name }}_val;
{% endfor %}

  covergroup reg_cg @(posedge {{ clk_name }});
{% for reg in reg_list %}
{% if reg.fields %}
    // {{ reg.name }} (offset {{ reg.offset }})
{% for field in reg.fields %}
{% if field.name and field.name != "reserved" %}
    {{ reg.name }}_{{ field.name }}: coverpoint {{ reg.name }}_val[{{ field.bits|replace("[","")|replace("]","") }}];
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
  endgroup

  reg_cg cg;

  function new();
    cg = new();
  endfunction
endinterface
