// {{ module_name }} — Reset Assertions (auto-generated)

module reset_assertions (
  input logic {{ clk_name }},
  input logic {{ rst_name }},
);

  // After reset, known state must be reached within N cycles
  property reset_recovery;
    @(posedge {{ clk_name }})
      $rose({{ rst_name }}) |-> ##[1:10] 1;
  endproperty
  RESET_RECOVERY: assert property(reset_recovery)
    else $error("Reset recovery timeout");
endmodule
