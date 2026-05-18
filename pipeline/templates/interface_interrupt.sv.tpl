// {{ module_name }} — Interrupt Interface (auto-generated, iverilog-compatible)

interface intr_if (input logic {{ clk_name }}, input logic {{ rst_name }});
{% for sig in interrupt.signals %}
  logic {% if sig.width > 1 %}[{{ sig.width - 1 }}:0] {% endif %}{{ sig.name }};
{% endfor %}
endinterface : intr_if
