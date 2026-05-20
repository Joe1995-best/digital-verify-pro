"""iverilog 编译配置 — 可独立运行，也可被 run_sim.py 调用"""
SIMULATOR = "iverilog"
OUTPUT    = "build/simv"
SOURCES   = ["../rtl/rtl/*.sv", "../rtl/verification/env/*.sv"]
INCDIRS   = ["../rtl/rtl", "../rtl/verification/env"]
DEFINES   = {"UVM_NO_DEPRECATED": None, "CLK_PERIOD": "20"}

COMPILE_CMD = "iverilog -g2012 -o {output} {incflags} {defines} {sources}"
