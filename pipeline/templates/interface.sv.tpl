// {{ module_name }} — Generic Protocol Interface (auto-generated, iverilog-compatible)

interface {{ interface.name }}_if (input logic {{ clk_name }}, input logic {{ rst_name }});
{% for sig in interface.signals %}
  {% if sig.direction == "bidir" %}
  wire {% if sig.width > 1 %}[{{ sig.width - 1 }}:0] {% endif %}{{ sig.name }};
  {% else %}
  logic {% if sig.width > 1 %}[{{ sig.width - 1 }}:0] {% endif %}{{ sig.name }};
  {% endif %}
{% endfor %}
endinterface : {{ interface.name }}_if
