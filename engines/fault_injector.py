#!/usr/bin/env python3
"""
fault_injector.py — Full-featured Fault Injection Engine for iverilog/UVM

Generates:
  1. JSON injection plan (human-readable + regression meta-data)
  2. SystemVerilog task library (pure Verilog — no DPI/PLI needed)
  3. Parameterised fault-injector wrapper module
  4. UVM-compatible sequence with randomised injection timing

Supported fault modes:
  • bus_hang        — force bus select / ready low to create timeout
  • reset_glitch    — illegal posedge on active-low reset
  • seu             — single-event upset: flip one random bit
  • clk_stall       — pause clock for N cycles (hang FSM/pipeline)
  • data_corrupt    — invert random bit(s) on data path
  • protocol_viol   — violate interface protocol (e.g. I2C SDA-change-while-SCL-high)
  • stuck_at        — stuck-at-0 or stuck-at-1 on a signal
  • glitch          — transient pulse on combinational output

Usage (CLI):
    python engines/fault_injector.py --spec i2c_spec.yml --mode seu --out ./fi/
    python engines/fault_injector.py --rtl rtl/i2c.sv --mode reset_glitch,clk_stall --out fi/

Usage (API):
    from engines.fault_injector import FaultInjector
    fi = FaultInjector(spec_path="i2c_spec.yml")
    fi.generate_all(output_dir="./fi/")

Design philosophy:
    Pure SystemVerilog — no simulator-specific DPI/PLI. Works with iverilog.
"""

import argparse
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Fault Mode Definitions
# ---------------------------------------------------------------------------

class FaultMode(Enum):
    """Supported fault-injection modes."""
    BUS_HANG = "bus_hang"
    RESET_GLITCH = "reset_glitch"
    SEU = "seu"
    CLK_STALL = "clk_stall"
    DATA_CORRUPT = "data_corrupt"
    PROTOCOL_VIOL = "protocol_viol"
    STUCK_AT = "stuck_at"
    GLITCH = "glitch"

    @classmethod
    def from_str(cls, s: str) -> "FaultMode":
        for m in cls:
            if m.value == s:
                return m
        raise ValueError(f"Unknown fault mode: {s}")


# ── Per-mode meta-data ────────────────────────────────────────────────────

_FAULT_META: Dict[FaultMode, Dict[str, Any]] = {
    FaultMode.BUS_HANG: {
        "sv_task": "fi_bus_hang",
        "args": [
            ("target", "string", '"psel"'),
            ("hold_ns", "int", "100"),
        ],
        "description": "Force APB/AHB select low to hang bus transaction",
        "target_signals": ["psel", "penable", "hsel"],
    },
    FaultMode.RESET_GLITCH: {
        "sv_task": "fi_reset_glitch",
        "args": [
            ("rst_signal", "string", '"rst_n"'),
            ("glitch_ns", "int", "5"),
        ],
        "description": "Inject illegal posedge on active-low reset",
        "target_signals": ["rst_n", "reset_n"],
    },
    FaultMode.SEU: {
        "sv_task": "fi_seu",
        "args": [
            ("reg_name", "string", '"ctrl_reg_q"'),
            ("bit_idx", "int", "-1"),  # -1 = random
        ],
        "description": "Single-event upset: flip one bit of a register",
        "target_signals": ["ctrl_reg_q", "status_reg_q", "data_reg"],
    },
    FaultMode.CLK_STALL: {
        "sv_task": "fi_clk_stall",
        "args": [
            ("clk_signal", "string", '"clk"'),
            ("stall_cycles", "int", "10"),
        ],
        "description": "Pause clock for N cycles to stall FSM/pipeline",
        "target_signals": ["clk", "pclk", "aclk"],
    },
    FaultMode.DATA_CORRUPT: {
        "sv_task": "fi_data_corrupt",
        "args": [
            ("data_signal", "string", '"pwdata"'),
            ("bit_mask", "int", "32'hFFFF_FFFF"),
            ("duration_ns", "int", "20"),
        ],
        "description": "Invert random bits on a data bus",
        "target_signals": ["pwdata", "prdata", "wdata", "rdata"],
    },
    FaultMode.PROTOCOL_VIOL: {
        "sv_task": "fi_protocol_viol",
        "args": [
            ("protocol", "string", '"i2c"'),
            ("viol_type", "int", "0"),  # 0=SDA-change-while-SCL-high
        ],
        "description": "Violate interface protocol timing rule",
        "target_signals": ["sda", "scl", "tvalid", "tready"],
    },
    FaultMode.STUCK_AT: {
        "sv_task": "fi_stuck_at",
        "args": [
            ("target", "string", '"pready"'),
            ("stuck_value", "int", "0"),
            ("duration_ns", "int", "200"),
        ],
        "description": "Force signal to stuck-at-0 or stuck-at-1",
        "target_signals": ["pready", "hreadyout", "interrupt"],
    },
    FaultMode.GLITCH: {
        "sv_task": "fi_glitch",
        "args": [
            ("target", "string", '"prdata[0]"'),
            ("pulse_ns", "int", "2"),
        ],
        "description": "Transient pulse / runt glitch on combinational output",
        "target_signals": ["prdata[0]", "interrupt", "error"],
    },
}


# ---------------------------------------------------------------------------
# JSON Plan
# ---------------------------------------------------------------------------

def generate_plan(
    modes: Optional[List[FaultMode]] = None,
    seed: int = 42,
    iterations: int = 10,
    module_name: str = "dut",
) -> Dict[str, Any]:
    """Generate a JSON-serialisable fault-injection plan."""
    if modes is None:
        modes = list(FaultMode)

    rng = random.Random(seed)
    injections: List[Dict[str, Any]] = []

    for mode in modes:
        meta = _FAULT_META[mode]
        for i in range(iterations):
            entry: Dict[str, Any] = {
                "id": f"{mode.value}_{i:04d}",
                "mode": mode.value,
                "iteration": i,
                "description": meta["description"],
                "sv_task": meta["sv_task"],
                "target_signals": meta["target_signals"],
            }
            # Add mode-specific randomisation
            if mode == FaultMode.SEU:
                entry["target_bit"] = rng.randint(0, 31)
                entry["reg_name"] = rng.choice(meta["target_signals"])
            elif mode == FaultMode.BUS_HANG:
                entry["target"] = rng.choice(meta["target_signals"])
                entry["hold_ns"] = rng.choice([50, 100, 200, 500])
            elif mode == FaultMode.RESET_GLITCH:
                entry["glitch_ns"] = rng.choice([3, 5, 10])
            elif mode == FaultMode.CLK_STALL:
                entry["stall_cycles"] = rng.choice([5, 10, 20, 50])
            elif mode == FaultMode.DATA_CORRUPT:
                entry["bit_mask"] = f"0x{rng.getrandbits(32):08X}"
            elif mode == FaultMode.PROTOCOL_VIOL:
                entry["protocol"] = rng.choice(["i2c", "apb", "axi_stream"])
            elif mode == FaultMode.STUCK_AT:
                entry["stuck_value"] = rng.choice([0, 1])
                entry["duration_ns"] = rng.choice([100, 200, 500])
            elif mode == FaultMode.GLITCH:
                entry["pulse_ns"] = rng.choice([1, 2, 5])

            injections.append(entry)

    return {
        "version": "2.0.0",
        "generator": "digital-verify-pro/fault_injector.py",
        "module": module_name,
        "seed": seed,
        "iterations_per_mode": iterations,
        "total_injections": len(injections),
        "modes": [m.value for m in modes],
        "injections": injections,
    }


def write_plan(plan: Dict[str, Any], path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# SystemVerilog Task Library (pure Verilog — no DPI)
# ---------------------------------------------------------------------------

def _sv_tasks_header(module_name: str) -> str:
    return f"""// Auto-generated by digital-verify-pro/fault_injector.py
// Fault injection task library — pure SystemVerilog, iverilog compatible
// Module: {module_name}
// NOTE: All tasks use `force`/`release` which are supported by iverilog.

`ifndef FAULT_INJECTOR_TASKS_SV
`define FAULT_INJECTOR_TASKS_SV

`timescale 1ns/1ps

package fault_injector_tasks;

  // Global seed — override from testbench via plusarg: +FI_SEED=123
  int fi_seed = 42;
  int fi_rand_state = 0;

  initial begin
    if ($value$plusargs("FI_SEED=%d", fi_seed))
      $display("[FI] Using seed %0d from plusarg", fi_seed);
    fi_rand_state = fi_seed;
  end

  function automatic int fi_urandom_range(int max_val, int min_val=0);
    // Simple LCG — deterministic, simulator-independent
    fi_rand_state = (fi_rand_state * 1103515245 + 12345) & 32'h7FFF_FFFF;
    fi_urandom_range = min_val + (fi_rand_state % (max_val - min_val + 1));
  endfunction

"""


def _sv_task_bus_hang() -> str:
    return """
  // ── BUS_HANG ─────────────────────────────────────────────────────────
  task automatic fi_bus_hang(
    ref logic target,
    input int hold_ns = 100
  );
    $display("[FI] BUS_HANG: forcing target low for %0d ns", hold_ns);
    force target = 1'b0;
    #hold_ns;
    release target;
    $display("[FI] BUS_HANG: released target");
  endtask
"""


def _sv_task_reset_glitch() -> str:
    return """
  // ── RESET_GLITCH ───────────────────────────────────────────────────────
  task automatic fi_reset_glitch(
    ref logic rst_n,
    input int glitch_ns = 5
  );
    $display("[FI] RESET_GLITCH: posedge glitch on rst_n for %0d ns", glitch_ns);
    force rst_n = 1'b1;   // illegal posedge during active-low reset
    #glitch_ns;
    release rst_n;
    $display("[FI] RESET_GLITCH: released rst_n");
  endtask
"""


def _sv_task_seu() -> str:
    return """
  // ── SEU (Single Event Upset) ─────────────────────────────────────────
  task automatic fi_seu(
    ref logic [31:0] reg_val,
    input int bit_idx = -1
  );
    int target_bit;
    if (bit_idx < 0)
      target_bit = fi_urandom_range(31, 0);
    else
      target_bit = bit_idx;
    $display("[FI] SEU: flipping bit %0d of reg", target_bit);
    force reg_val[target_bit] = ~reg_val[target_bit];
    #1ns;                  // hold for 1 ns (transient)
    release reg_val[target_bit];
    $display("[FI] SEU: released bit %0d", target_bit);
  endtask
"""


def _sv_task_clk_stall() -> str:
    return """
  // ── CLK_STALL ──────────────────────────────────────────────────────────
  task automatic fi_clk_stall(
    ref logic clk,
    input int stall_cycles = 10
  );
    $display("[FI] CLK_STALL: pausing clk for %0d cycles", stall_cycles);
    force clk = 1'b0;
    #(stall_cycles * 20); // assume 50 MHz = 20 ns period
    release clk;
    $display("[FI] CLK_STALL: clk resumed");
  endtask
"""


def _sv_task_data_corrupt() -> str:
    return """
  // ── DATA_CORRUPT ─────────────────────────────────────────────────────
  task automatic fi_data_corrupt(
    ref logic [31:0] data_sig,
    input logic [31:0] bit_mask = 32'hFFFF_FFFF,
    input int duration_ns = 20
  );
    logic [31:0] corrupt_val;
    int xor_bits;
    xor_bits = fi_urandom_range(31, 0);
    corrupt_val = data_sig ^ (bit_mask & (32'h1 << xor_bits));
    $display("[FI] DATA_CORRUPT: xor bit %0d for %0d ns", xor_bits, duration_ns);
    force data_sig = corrupt_val;
    #duration_ns;
    release data_sig;
    $display("[FI] DATA_CORRUPT: released");
  endtask
"""


def _sv_task_protocol_viol() -> str:
    return """
  // ── PROTOCOL_VIOL ────────────────────────────────────────────────────
  task automatic fi_protocol_viol(
    ref logic scl,
    ref logic sda,
    input int viol_type = 0  // 0 = SDA change while SCL high
  );
    if (viol_type == 0) begin
      $display("[FI] PROTOCOL_VIOL: I2C SDA change while SCL high");
      force scl = 1'b1;
      #5ns;
      force sda = ~sda;
      #10ns;
      release sda;
      release scl;
    end else begin
      $display("[FI] PROTOCOL_VIOL: unknown type %0d", viol_type);
    end
    $display("[FI] PROTOCOL_VIOL: done");
  endtask
"""


def _sv_task_stuck_at() -> str:
    return """
  // ── STUCK_AT ─────────────────────────────────────────────────────────
  task automatic fi_stuck_at(
    ref logic target,
    input int stuck_value = 0,
    input int duration_ns = 200
  );
    $display("[FI] STUCK_AT: forcing target = %0d for %0d ns", stuck_value, duration_ns);
    force target = stuck_value[0];
    #duration_ns;
    release target;
    $display("[FI] STUCK_AT: released");
  endtask
"""


def _sv_task_glitch() -> str:
    return """
  // ── GLITCH ───────────────────────────────────────────────────────────
  task automatic fi_glitch(
    ref logic target,
    input int pulse_ns = 2
  );
    logic orig;
    orig = target;
    $display("[FI] GLITCH: %0d ns pulse on target", pulse_ns);
    force target = ~orig;
    #pulse_ns;
    force target = orig;
    #pulse_ns;
    release target;
    $display("[FI] GLITCH: done");
  endtask
"""


def _sv_tasks_footer() -> str:
    return """
endpackage : fault_injector_tasks
`endif // FAULT_INJECTOR_TASKS_SV
"""


def generate_sv_tasks(module_name: str, modes: Optional[List[FaultMode]] = None) -> str:
    """Generate a pure-SystemVerilog fault-injection task package."""
    if modes is None:
        modes = list(FaultMode)

    parts = [_sv_tasks_header(module_name)]
    task_map = {
        FaultMode.BUS_HANG: _sv_task_bus_hang(),
        FaultMode.RESET_GLITCH: _sv_task_reset_glitch(),
        FaultMode.SEU: _sv_task_seu(),
        FaultMode.CLK_STALL: _sv_task_clk_stall(),
        FaultMode.DATA_CORRUPT: _sv_task_data_corrupt(),
        FaultMode.PROTOCOL_VIOL: _sv_task_protocol_viol(),
        FaultMode.STUCK_AT: _sv_task_stuck_at(),
        FaultMode.GLITCH: _sv_task_glitch(),
    }
    for m in modes:
        parts.append(task_map[m])
    parts.append(_sv_tasks_footer())
    return "\n".join(parts)


def write_sv_tasks(text: str, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# SystemVerilog Wrapper Module (parameterised)
# ---------------------------------------------------------------------------

def generate_sv_wrapper(module_name: str, modes: Optional[List[FaultMode]] = None) -> str:
    """Generate a self-contained fault-injector wrapper module.

    Usage in testbench:
        fault_injector #(.FAULT_MODE("seu"), .TRIGGER_CYCLE(200))
            fi_inst (.clk(clk), .rst_n(rst_n), .target(ctrl_reg_q));
    """
    if modes is None:
        modes = list(FaultMode)

    mode_list = ", ".join(f'"{m.value}"' for m in modes)

    return f"""// Auto-generated by digital-verify-pro/fault_injector.py
// Parameterised fault-injector wrapper — iverilog compatible
// Module: {module_name}

`ifndef FAULT_INJECTOR_WRAPPER_SV
`define FAULT_INJECTOR_WRAPPER_SV

`timescale 1ns/1ps

module fault_injector #(
  parameter string FAULT_MODE  = "none",      // {mode_list}
  parameter int   TRIGGER_CYCLE = 100,
  parameter int   DURATION_NS   = 50,
  parameter int   SEED          = 42,
  parameter int   DATA_WIDTH    = 32
)(
  input  wire              clk,
  input  wire              rst_n,
  inout  wire [DATA_WIDTH-1:0] target,        // signal to corrupt
  output wire [DATA_WIDTH-1:0] target_out     // corrupted output
);

  // Internal state
  reg [DATA_WIDTH-1:0] target_force;
  reg                  force_active;
  int                  cycle_cnt;
  int                  rand_state;

  assign target_out = force_active ? target_force : target;

  // Simple LCG PRNG
  function automatic int fi_rand();
    rand_state = (rand_state * 1103515245 + 12345) & 32'h7FFF_FFFF;
    fi_rand = rand_state;
  endfunction

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cycle_cnt   <= 0;
      force_active <= 1'b0;
      rand_state   <= SEED;
    end else begin
      cycle_cnt <= cycle_cnt + 1;

      if (cycle_cnt == TRIGGER_CYCLE && !force_active) begin
        force_active <= 1'b1;
        case (FAULT_MODE)
          "bus_hang":
            target_force <= {{DATA_WIDTH{{1'b0}}}};
          "reset_glitch":
            ; // handled outside (rst_n is not target)
          "seu": begin
            int bit_idx;
            bit_idx = fi_rand() % DATA_WIDTH;
            target_force <= target ^ (1 << bit_idx);
          end
          "clk_stall":
            ; // handled by clock gating externally
          "data_corrupt":
            target_force <= target ^ (fi_rand());
          "protocol_viol":
            target_force <= ~target; // invert to violate protocol
          "stuck_at":
            target_force <= {{DATA_WIDTH{{1'b0}}}}; // stuck-at-0 default
          "glitch":
            target_force <= ~target;
          default:
            target_force <= target;
        endcase
        // Auto-release after duration
        // (simplified — real implementation would count time)
      end

      if (cycle_cnt == TRIGGER_CYCLE + (DURATION_NS / 20) && force_active)
        force_active <= 1'b0;
    end
  end

endmodule
`endif // FAULT_INJECTOR_WRAPPER_SV
"""


def write_sv_wrapper(text: str, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# UVM Sequence (optional — for UVM environments)
# ---------------------------------------------------------------------------

def generate_uvm_sequence(module_name: str, modes: Optional[List[FaultMode]] = None) -> str:
    """Generate a UVM sequence that randomly triggers fault injection."""
    if modes is None:
        modes = list(FaultMode)

    task_cases = []
    for m in modes:
        meta = _FAULT_META[m]
        args = ", ".join(f"{a[0]}={a[2]}" for a in meta["args"])
        task_cases.append(f"""
      "{m.value}": begin
        fault_injector_tasks.{meta["sv_task"]}({args});
      end""")

    return f"""// Auto-generated by digital-verify-pro/fault_injector.py
// UVM fault-injection sequence — {module_name}

`ifndef FAULT_INJECTOR_SEQ_SV
`define FAULT_INJECTOR_SEQ_SV

`include "uvm_macros.svh"
import uvm_pkg::*;
import fault_injector_tasks::*;

class fault_injector_seq extends uvm_sequence #(uvm_sequence_item);
  `uvm_object_utils(fault_injector_seq)

  rand int trigger_delay_ns;
  rand string fault_mode;

  constraint c_delay {{ trigger_delay_ns inside {{ [100:1000] }}; }}
  constraint c_mode  {{ fault_mode inside {{ {" ".join(f'"{m.value}"' for m in modes)} }}; }}

  function new(string name = "fault_injector_seq");
    super.new(name);
  endfunction

  virtual task body();
    #trigger_delay_ns;
    `uvm_info("FI", $sformatf("Injecting fault: %s", fault_mode), UVM_LOW)
    case (fault_mode)
{chr(10).join(task_cases)}
      default: `uvm_warning("FI", "Unknown fault mode")
    endcase
  endtask

endclass
`endif // FAULT_INJECTOR_SEQ_SV
"""


def write_uvm_sequence(text: str, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

class FaultInjector:
    """High-level API for generating all fault-injection artefacts."""

    def __init__(self, spec_path: str = "", rtl_path: str = "", module_name: str = ""):
        self.spec_path = spec_path
        self.rtl_path = rtl_path
        self.module_name = module_name or self._detect_module_name()
        self.modes: List[FaultMode] = list(FaultMode)

    def _detect_module_name(self) -> str:
        if self.rtl_path and os.path.isfile(self.rtl_path):
            with open(self.rtl_path, encoding="utf-8", errors="replace") as f:
                m = re.search(r'module\s+(\w+)', f.read())
                if m:
                    return m.group(1)
        if self.spec_path:
            return Path(self.spec_path).stem.replace("_spec", "").replace(".yml", "")
        return "dut"

    def set_modes(self, modes: List[FaultMode]) -> "FaultInjector":
        self.modes = modes
        return self

    def generate_all(self, output_dir: str, seed: int = 42, iterations: int = 10) -> Dict[str, str]:
        """Generate plan, SV tasks, wrapper, and UVM sequence. Returns paths."""
        os.makedirs(output_dir, exist_ok=True)
        paths: Dict[str, str] = {}

        # 1. JSON plan
        plan = generate_plan(
            modes=self.modes,
            seed=seed,
            iterations=iterations,
            module_name=self.module_name,
        )
        paths["plan"] = write_plan(plan, os.path.join(output_dir, "fault_injection_plan.json"))

        # 2. SV task library
        sv_tasks = generate_sv_tasks(self.module_name, self.modes)
        paths["sv_tasks"] = write_sv_tasks(sv_tasks, os.path.join(output_dir, "fault_injector_tasks.sv"))

        # 3. SV wrapper module
        sv_wrapper = generate_sv_wrapper(self.module_name, self.modes)
        paths["sv_wrapper"] = write_sv_wrapper(sv_wrapper, os.path.join(output_dir, "fault_injector.sv"))

        # 4. UVM sequence
        uvm_seq = generate_uvm_sequence(self.module_name, self.modes)
        paths["uvm_seq"] = write_uvm_sequence(uvm_seq, os.path.join(output_dir, "fault_injector_seq.sv"))

        return paths

    def generate_plan_only(self, output_path: str, **kwargs: Any) -> str:
        plan = generate_plan(modes=self.modes, module_name=self.module_name, **kwargs)
        return write_plan(plan, output_path)

    def generate_sv_only(self, output_dir: str) -> Dict[str, str]:
        """Generate only SV artefacts (no JSON plan)."""
        os.makedirs(output_dir, exist_ok=True)
        return {
            "sv_tasks": write_sv_tasks(
                generate_sv_tasks(self.module_name, self.modes),
                os.path.join(output_dir, "fault_injector_tasks.sv"),
            ),
            "sv_wrapper": write_sv_wrapper(
                generate_sv_wrapper(self.module_name, self.modes),
                os.path.join(output_dir, "fault_injector.sv"),
            ),
            "uvm_seq": write_uvm_sequence(
                generate_uvm_sequence(self.module_name, self.modes),
                os.path.join(output_dir, "fault_injector_seq.sv"),
            ),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fault Injection Engine for digital-verify-pro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python engines/fault_injector.py --spec i2c_spec.yml --out ./fi/
  python engines/fault_injector.py --rtl rtl/i2c.sv --mode seu,reset_glitch --out ./fi/
  python engines/fault_injector.py --spec spi_spec.yml --mode all --seed 123 --iter 20
        """,
    )
    ap.add_argument("--spec", help="Path to spec YAML (for module name detection)")
    ap.add_argument("--rtl", help="Path to RTL file (for module name detection)")
    ap.add_argument("--mode", default="all",
                    help="Comma-separated fault modes (default: all). Options: "
                         "bus_hang, reset_glitch, seu, clk_stall, data_corrupt, "
                         "protocol_viol, stuck_at, glitch")
    ap.add_argument("--out", default="output/fault_injector", help="Output directory")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--iter", type=int, default=10, help="Iterations per mode")
    ap.add_argument("--plan-only", action="store_true", help="Generate only JSON plan")
    ap.add_argument("--sv-only", action="store_true", help="Generate only SV artefacts")
    ap.add_argument("--list-modes", action="store_true", help="List supported modes and exit")
    args = ap.parse_args(argv)

    if args.list_modes:
        print("Supported fault modes:")
        for m in FaultMode:
            meta = _FAULT_META[m]
            print(f"  {m.value:18s} — {meta['description']}")
            print(f"    SV task: {meta['sv_task']}({', '.join(a[0] for a in meta['args'])})")
        return 0

    # Parse modes
    if args.mode == "all":
        modes: List[FaultMode] = list(FaultMode)
    else:
        modes = [FaultMode.from_str(s.strip()) for s in args.mode.split(",")]

    fi = FaultInjector(spec_path=args.spec or "", rtl_path=args.rtl or "")
    fi.set_modes(modes)

    if args.plan_only:
        path = fi.generate_plan_only(
            os.path.join(args.out, "fault_injection_plan.json"),
            seed=args.seed,
            iterations=args.iter,
        )
        print(f"[FI] Plan written to: {path}")
    elif args.sv_only:
        paths = fi.generate_sv_only(args.out)
        for k, v in paths.items():
            print(f"[FI] {k}: {v}")
    else:
        paths = fi.generate_all(args.out, seed=args.seed, iterations=args.iter)
        for k, v in paths.items():
            print(f"[FI] {k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
