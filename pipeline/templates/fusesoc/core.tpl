# {{ module_name }} — FuseSoC core file (auto-generated)
# https://github.com/olofk/fusesoc

name: work:ip:{{ module_name }}:0.1
description: "{{ module_desc }}"

filesets:
  rtl:
    files:
      - rtl/rtl/*.sv
    file_type: systemVerilogSource

  verification:
    depend:
      - lowrisc:dv:uvm_lib
    files:
      - rtl/verification/env/*.sv
      - rtl/verification/env/agents/*.sv
      - rtl/verification/env/sequences/*.sv
      - rtl/verification/env/assertions/*.sv
      - rtl/verification/env/scoreboard/*.sv
      - rtl/verification/env/coverage/*.sv
      - rtl/verification/env/tests/*.sv
      - rtl/verification/env/bfm/*.sv
    file_type: systemVerilogSource

targets:
  default: &default
    filesets: [rtl, verification]
    tools: [verilator]
  lint:
    filesets: [rtl]
    tools: [verilator]
    verilator_options:
      - --lint-only
