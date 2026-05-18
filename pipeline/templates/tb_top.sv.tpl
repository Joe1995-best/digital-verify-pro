// {{ module_name }} — Testbench Top (auto-generated)

`timescale 1ns/1ps

module tb_top;
  import uvm_pkg::*;
  `include "uvm_macros.svh"

  // Clock and reset
  logic {{ clk_name }};
  logic {{ rst_name }};

  // APB interface
  apb_if apb_if_inst (.{{ clk_name }}({{ clk_name }}), .{{ rst_name }}({{ rst_name }}));

{% if protocol and protocol.get('type') %}
  // {{ protocol.type }} interface
  {{ protocol.name }}_if {{ protocol.name }}_if_inst (.{{ clk_name }}({{ clk_name }}), .{{ rst_name }}({{ rst_name }}));
{% endif %}

{% if interrupt %}
  // Interrupt interface
  intr_if intr_if_inst (.{{ clk_name }}({{ clk_name }}), .{{ rst_name }}({{ rst_name }}));
{% endif %}

{% if protocol and protocol.get('type') %}
  // BFM for protocol-level access
  {{ module_name }}_bfm bfm ({{ protocol.name }}_if_inst);
{% endif %}

  // DUT instantiation
  {{ module_name }} dut (
    .{{ clk_name }}   ({{ clk_name }}),
    .{{ rst_name }}   ({{ rst_name }}),
{% for sig in apb.signals %}
    .{{ sig.name }}(apb_if_inst.{{ sig.name }}),
{% endfor %}
{% if protocol and protocol.get('signals') %}{% for sig in protocol.signals %}
    .{{ sig.name }}({{ protocol.name }}_if_inst.{{ sig.name }}),{% endfor %}
{% endif %}
{% if interrupt %}
{% for sig in interrupt.signals %}
    .{{ sig.name }}(intr_if_inst.{{ sig.name }}){% if not loop.last %},{% endif %}
{% endfor %}
{% endif %}
  );

  // Clock generation
  initial begin
    {{ clk_name }} = 0;
    forever #10 {{ clk_name }} = ~{{ clk_name }};
  end

  // Reset generation
  initial begin
    {{ rst_name }} = 0;
    #100;
    {{ rst_name }} = 1;
  end

  // Set interface + BFM in config DB
  initial begin
    uvm_config_db#(apb_if)::set(null, "uvm_test_top.env.apb_agt.*", "vif", apb_if_inst);
{% if protocol and protocol.get('type') %}
    uvm_config_db#({{ module_name }}_bfm)::set(null, "uvm_test_top.env", "bfm", bfm);
{% endif %}
    run_test();
  end

  // VCD dump
  initial begin
    $dumpfile("{{ module_name }}.vcd");
    $dumpvars(0, tb_top);
  end
endmodule
