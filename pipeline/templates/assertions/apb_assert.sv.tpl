// {{ module_name }} — APB Protocol Assertions (auto-generated)

module apb_assertions (
  input logic {{ clk_name }},
  input logic {{ rst_name }},
{% for sig in apb.signals %}
  input logic {{ sig.name }},
{% endfor %}
);

  // PSEL must be asserted before PENABLE
  property psel_before_penable;
    @(posedge {{ clk_name }}) disable iff (!{{ rst_name }})
      $rose(penable) |-> $past(psel);
  endproperty
  PSEL_BEFORE_PENABLE: assert property(psel_before_penable)
    else $error("APB: PENABLE asserted without PSEL");

  // PREADY must eventually be asserted
  property pready_eventually;
    @(posedge {{ clk_name }}) disable iff (!{{ rst_name }})
      $rose(psel) && $rose(penable) |-> ##[1:16] pready;
  endproperty
  PREADY_EVENTUALLY: assert property(pready_eventually)
    else $warning("APB: PREADY timeout (16 cycles)");

  // No X/Z on control signals
  property no_x_on_control;
    @(posedge {{ clk_name }}) disable iff (!{{ rst_name }})
      (psel && penable) |-> (!$isunknown({psel, penable, pwrite}));
  endproperty
  NO_X_CTRL: assert property(no_x_on_control)
    else $error("APB: X/Z detected on control signals");

endmodule
