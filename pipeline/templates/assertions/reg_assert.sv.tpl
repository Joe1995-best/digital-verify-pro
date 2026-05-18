// {{ module_name }} — Register Assertions (auto-generated)

module reg_assertions (
  input logic {{ clk_name }},
  input logic {{ rst_name }},
  input logic psel,
  input logic penable,
  input logic pwrite,
  input logic [{{ apb.addr_width|default(12) - 1 }}:0] paddr,
  input logic [{{ apb.data_width|default(32) - 1 }}:0] pwdata,
);

  // Register address must be aligned
  property addr_align;
    @(posedge {{ clk_name }}) disable iff (!{{ rst_name }})
      (psel && penable) |-> (paddr % 4 == 0);
  endproperty
  ADDR_ALIGN: assert property(addr_align)
    else $error("Register: unaligned address 0x%0h", paddr);

{% for rng in reserved_ranges %}
  // Reserved range {{ rng.start_str }} — {{ rng.end_str }} must return PSLVERR
  property rsvd_pslverr;
    @(posedge {{ clk_name }}) disable iff (!{{ rst_name }})
      (psel && penable && paddr >= {{ rng.start_str }} && paddr <= {{ rng.end_str }}) |-> ##[1:16] pslverr;
  endproperty
  RSVD_PSLVERR_{{ loop.index }}: assert property(rsvd_pslverr)
    else $error("Reserved access 0x%0h did not return PSLVERR", paddr);
{% endfor %}

endmodule
