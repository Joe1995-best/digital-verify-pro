# {{ module_name }} — Simulation Makefile (auto-generated)

TOP        = tb_top
MODULE     = {{ module_name }}
SIM        = verilator
VERILATOR  = verilator
VVP        = vvp

# Source files
RTL_SRC    = ../../rtl/*.sv
ENV_SRC    = ../*.sv ../agents/*.sv ../sequences/*.sv ../assertions/*.sv ../scoreboard/*.sv ../coverage/*.sv ../tests/*.sv ../bfm/*.sv
VLOG_FLAGS = -sv -Wall

# DUT + env top
VLOG_SRC   = tb_top.sv ${RTL_SRC} ${ENV_SRC}

all: compile simulate

compile:
	verilator --sv --top-module ${TOP} ${VLOG_SRC} -o ${MODULE}.vvp

simulate: compile
	vvp ${MODULE}.vvp

clean:
	rm -rf obj_dir *.vvp *.vcd

.PHONY: all compile simulate clean
