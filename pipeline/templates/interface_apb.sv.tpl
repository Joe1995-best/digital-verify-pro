// {{ module_name }} — APB Interface (auto-generated, iverilog-compatible)

interface apb_if (input logic {{ clk_name }}, input logic {{ rst_name }});
{% for sig in apb.signals %}
  logic {% if sig.width > 1 %}[{{ sig.width - 1 }}:0] {% endif %}{{ sig.name }};
{% endfor %}
endinterface : apb_if
