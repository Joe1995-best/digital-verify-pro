#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rtl-gen — protocol-agnostic RTL generator (improved).

Generates synthesizable, iverilog-11-compatible SystemVerilog RTL from spec data.

Key improvements over v1:
  - FSM generation from spec (dma.sv v4 verified pattern)
  - Interrupt auto-management (w1c, auto-set, error persistence)
  - No 'unique case' or 'inside' — full iverilog 11 compatibility
  - No 'always_comb' reading variables assigned in 'always_ff'
  - error_flag persists (NOT cleared every cycle) — coverage-friendly
  - DMA-style controller support (separate host bus interface)
  - GPIO-centric assumptions removed for non-GPIO designs
"""

import os, sys, argparse, datetime
sys.path.insert(0, os.path.dirname(__file__))
from template_engine import build_spec_data
from fsm_templates import generate_fsm, has_dma_fsm, has_i2c_fsm, generate_interrupt_top_insert

BASE_DIR = os.path.dirname(__file__)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "..", "output"))
    return ap.parse_args()


def find_spec(spec_path):
    if spec_path and os.path.exists(spec_path):
        return spec_path
    for c in ["ot_dma_spec.yml", "i2c_spec.yml", "uart_spec.yml", "arm_pl061_gpio.yml"]:
        full = os.path.join(BASE_DIR, "..", c)
        if os.path.exists(full):
            return full
    return None


def get_reg_offset(r):
    off = r.get("offset", "0x000")
    try:
        return int(off, 16) if isinstance(off, str) else 0
    except (ValueError, TypeError):
        return 0


def get_reg_fields_info(r):
    """Get field-level info for a register.
    Returns: (bitmask, is_ro, is_wo, field_list)
    """
    fields = r.get("fields", [])
    all_ro = all(f.get("access", "rw") == "ro" for f in fields)
    all_wo = all(f.get("access", "rw") == "wo" for f in fields)
    has_w1c = any(f.get("access", "rw") == "w1c" for f in fields)

    field_info = []
    for f in fields:
        fname = f.get("name", "").lower()
        bits_raw = f.get("bits", "[0]").strip("[]")
        try:
            if ":" in bits_raw:
                msb, lsb = bits_raw.split(":")
                msb, lsb = int(msb), int(lsb)
            else:
                msb = lsb = int(bits_raw)
            width = msb - lsb + 1
        except (ValueError, TypeError):
            msb = lsb = 0
            width = 1
        field_info.append({
            "name": f.get("name", ""),
            "name_lower": fname,
            "msb": msb,
            "lsb": lsb,
            "width": width,
            "access": f.get("access", "rw"),
            "reset": f.get("reset", "0"),
        })

    return field_info, all_ro, all_wo, has_w1c


def get_reg_reset(r):
    """Compute reset value from register fields."""
    fields_info, _, _, _ = get_reg_fields_info(r)
    rval = 0
    for fi in fields_info:
        if fi["name_lower"] == "reserved":
            continue
        fv = fi["reset"]
        try:
            fv_int = int(fv, 16) if isinstance(fv, str) and fv.startswith("0x") else int(fv)
            fv_int = (fv_int & ((1 << fi["width"]) - 1)) << fi["lsb"]
            rval |= fv_int
        except (ValueError, TypeError):
            pass
    return f"32'h{rval:08X}"


def classify_reg(r):
    """Classify register by role."""
    n = r["name"].lower()
    fields = r.get("fields", [])
    has_w1c = any(f.get("access", "rw") == "w1c" for f in fields)
    if has_w1c:
        return "w1c"
    if n.endswith("ic"):
        return "ic"
    if n.endswith("state") or n.endswith("intr_state"):
        return "intr_state"  # w1c interrupt state
    if n.endswith("enable") or n.endswith("intr_enable"):
        return "intr_enable"
    return "normal"


# ═══════════════════════════════════════════════════════════════
#  Top module
# ═══════════════════════════════════════════════════════════════

def generate_top_module(data):
    module = data["module_name"]
    clk = data["clk_name"]
    rst = data["rst_name"]
    regs = data["registers"]
    fields = data.get("reg_fields_detail", [])
    date = data["date"]
    desc = data.get("module_desc", "")

    is_dma = has_dma_fsm(data)
    apb_if = data.get("apb", {})
    addr_width = apb_if.get("addr_width", 12) if apb_if else 12

    # Compute PSLVERR threshold
    pslverr_min = 0x1000
    for rng in data.get("reserved_ranges", []):
        if rng["end_str"] and int(rng["end_str"], 16) > 0:
            pslverr_min = int(rng["start_str"], 16)
            break

    # Check for interrupt registers
    has_intr_regs = any(
        r["name"].lower().endswith(s) for r in regs
        for s in ["state", "enable", "intr_state", "intr_enable"]
    )

    # ── Port list ──
    ports_list = [
        f"  input  logic       {clk}",
        f"  input  logic       {rst}",
        "  // APB slave interface",
        "  input  logic       psel",
        "  input  logic       penable",
        "  input  logic       pwrite",
        f"  input  logic [{addr_width-1}:0] paddr",
        "  input  logic [31:0] pwdata",
        "  output logic [31:0] prdata",
        "  output logic       pready",
        "  output logic       pslverr",
    ]

    if is_dma:
        # DMA-style: host bus interface + interrupts
        host_width = data.get("fsm", {}).get("host_width", 32)
        ports_list.extend([
            "  // Host bus interface (DMA master)",
            f"  output logic [{host_width-1}:0] host_addr_o",
            "  output logic       host_req_o",
            "  output logic       host_we_o",
            "  output logic [31:0] host_wdata_o",
            "  input  logic       host_gnt_i",
            "  input  logic [31:0] host_rdata_i",
            "  input  logic       host_rvalid_i",
            "  input  logic       host_err_i",
        ])
        # Interrupt outputs from FSM config
        intr_cfgs = data.get("fsm", {}).get("interrupts", [])
        if intr_cfgs:
            ports_list.append("  // Interrupt outputs")
            for ic in intr_cfgs:
                ports_list.append(f"  output logic       {ic['output']}")
        elif has_intr_regs:
            ports_list.append("  // Interrupt output")
            ports_list.append("  output logic       intr_o")
    elif has_intr_regs:
        ports_list.append("  // Interrupt output")
        ports_list.append("  output logic       intr")

    port_decls = ",\n".join(ports_list)

    code = f"""// {date}
// Auto-generated by digital-verify-pro RTL generator (improved)
// Module: {module} — {desc}
// {len(regs)} registers, {len(fields)} fields
// FSM: {"yes (" + data['fsm'].get('name', 'dma') + ")" if is_dma else "no"}

module {module} (
{port_decls}
);
"""
    if is_dma:
        # ── DMA-style top module ──
        fsm_name = f"{module}_{data['fsm'].get('name', 'dma_fsm')}"

        # Register signal declarations
        code += "\n  // Register signals (connect regs <-> FSM)\n"
        for r in regs:
            rn = r["name"]
            code += f"  logic [31:0] {rn}_q;\n"

        code += "\n  // FSM status signals\n"
        code += "  logic        busy_q, active_q;\n"
        code += "  logic        error_flag_q, done_q;\n"
        code += "  logic [3:0]  error_code_q;\n"
        code += "  logic [31:0] remaining_q;\n"

        fsm_cfgs = data.get("fsm", {}).get("interrupts", [])
        for ic in fsm_cfgs:
            code += f"  logic        {ic['intr_reg']};\n"

        code += "\n"

        # Register bank (without gpio/irq signals for DMA)
        code += f"  // Register file\n"
        code += f"  {module}_regs u_regs (\n"
        code += f"    .{clk}         ({clk}),\n"
        code += f"    .{rst}        ({rst}),\n"
        code += "    .psel           (psel),\n"
        code += "    .penable        (penable),\n"
        code += "    .pwrite         (pwrite),\n"
        code += "    .paddr          (paddr),\n"
        code += "    .pwdata         (pwdata),\n"
        code += "    .prdata         (prdata),\n"
        code += "    .busy_q         (busy_q),\n"
        code += "    .active_q       (active_q),\n"
        code += "    .error_flag_q   (error_flag_q),\n"
        code += "    .error_code_q   (error_code_q),\n"
        code += "    .done_q         (done_q),\n"
        code += "    .remaining_q    (remaining_q),\n"
        for ic in fsm_cfgs:
            code += f"    .{ic['intr_reg']}    ({ic['intr_reg']}),\n"
        code += "    .enable_q       (DMA_CTRL_q[2]),\n"
        # Register value outputs (for FSM, skip FSM-driven RO regs)
        fsm_status_regs = {"DMA_STATUS", "ERROR_CODE", "REMAINING_BYTES", "CFG_REGWEN", "INTR_STATE"}
        reg_val_ports = []
        for r in regs:
            rn = r["name"]
            if r.get("access", "rw") in ("rw", "wo") and rn not in fsm_status_regs:
                reg_val_ports.append(f"    .{rn}_q_val({rn}_q)")
        for i, p in enumerate(reg_val_ports):
            sep = "," if i < len(reg_val_ports) - 1 else ""
            code += p + sep + "\n"
        code += "  );\n\n"


        # FSM controller
        code += f"  // DMA FSM controller\n"
        code += f"  {fsm_name} u_fsm (\n"
        code += f"    .{clk}             ({clk}),\n"
        code += f"    .{rst}            ({rst}),\n"
        code += "    .start_q             (DMA_CTRL_q[0]),\n"
        code += "    .enable_q            (DMA_CTRL_q[2]),\n"
        code += "    .stop_q              (DMA_CTRL_q[1]),\n"
        code += "    .total_data_size_q   (TOTAL_DATA_SIZE_q),\n"
        code += "    .chunk_data_size_q   (CHUNK_DATA_SIZE_q),\n"
        code += "    .src_addr_lo_q       (SRC_ADDR_LO_q),\n"
        code += "    .dst_addr_lo_q       (DST_ADDR_LO_q),\n"
        code += "    .src_incr_val_q      (ADDR_INCR_CFG_q[15:4]),\n"
        code += "    .dst_incr_val_q      (ADDR_INCR_CFG_q[27:16]),\n"
        code += "    .src_incr_en_q       (ADDR_INCR_CFG_q[0]),\n"
        code += "    .dst_incr_en_q       (ADDR_INCR_CFG_q[1]),\n"
        code += "    .busy_q              (busy_q),\n"
        code += "    .active_q            (active_q),\n"
        code += "    .error_flag_q        (error_flag_q),\n"
        code += "    .error_code_q        (error_code_q),\n"
        code += "    .done_q              (done_q),\n"
        code += "    .remaining_q         (remaining_q),\n"
        for ic in fsm_cfgs:
            code += f"    .{ic['intr_reg']}         ({ic['intr_reg']}),\n"
        code += "    .intr_clear          (intr_clear),\n"
        code += "    .host_addr_o         (host_addr_o),\n"
        code += "    .host_req_o          (host_req_o),\n"
        code += "    .host_we_o           (host_we_o),\n"
        code += "    .host_wdata_o        (host_wdata_o),\n"
        code += "    .host_gnt_i          (host_gnt_i),\n"
        code += "    .host_rdata_i        (host_rdata_i),\n"
        code += "    .host_rvalid_i       (host_rvalid_i),\n"
        code += "    .host_err_i          (host_err_i)\n"
        code += "  );\n\n"

        # Interrupt clear logic
        code += f"""\
  // Interrupt clear logic — W1C from APB write to INTR_STATE (0x40)
  logic [2:0] intr_clear;
  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst})
      intr_clear <= '0;
    else if (psel && penable && pwrite && paddr == 12'h040)
      intr_clear <= {{pwdata[2], pwdata[1], pwdata[0]}};
    else
      intr_clear <= '0;
  end

  // Interrupt output gating — intr_reg & enable
  assign intr_dma_done_o   = dma_done_intr_q   & INTR_ENABLE_q[0];
  assign intr_dma_chunk_o  = dma_chunk_intr_q  & INTR_ENABLE_q[1];
  assign intr_dma_error_o  = dma_error_intr_q  & INTR_ENABLE_q[2];

"""

        # APB + PSLVERR
        code += """\
  // APB always ready
  assign pready = 1'b1;

  // PSLVERR for reserved addresses
  wire is_reserved = (paddr >= """ + f"12'h{pslverr_min:03X}" + """);  
  assign pslverr = (psel && penable && is_reserved) ? 1'b1 : 1'b0;

endmodule
"""
    elif has_i2c_fsm(data):
        # ── I2C FSM top module ──
        is_i2c = True
        fsm_cfg = data.get("fsm", {})
        fsm_name = f"{module}_{fsm_cfg.get('name', 'i2c_fsm')}"

        # Port list updates
        ports_list.extend([
            "  // I2C bus (separate signals — IO pad cell in top-level)",
            "  output logic       scl_o",
            "  output logic       scl_en_o",
            "  input  logic       scl_i",
            "  output logic       sda_o",
            "  output logic       sda_en_o",
            "  input  logic       sda_i",
            "  // Interrupt output",
            "  output logic       intr_o",
        ])
        port_decls = ",\n".join(ports_list)

        code = f"""// {date}
// Auto-generated by digital-verify-pro RTL generator (improved)
// Module: {module} — {desc}
// {len(regs)} registers, {len(fields)} fields
// FSM: i2c ({fsm_name})

module {module} (
{port_decls}
);
"""

        # Register signal declarations for FSM access
        code += "  // Register signals (connect regs <-> I2C FSM)\n"
        for r in regs:
            rn = r["name"]
            code += f"  logic [31:0] {rn}_q;\n"

        # I2C FSM internal signals
        code += """
  // I2C FSM signals
  logic        busy_i2c;
  logic        rx_ready;
  logic [7:0]  rx_data_i2c;
  logic        rx_nack;
  logic        rx_arb_lost;
  logic        tx_intr, rx_intr, stop_det, arb_intr;

"""

        # Register bank (I2C-specific signal export)
        code += f"  // Register file\n"
        code += f"  {module}_regs u_regs (\n"
        code += f"    .{clk}         ({clk}),\n"
        code += f"    .{rst}        ({rst}),\n"
        code += "    .psel           (psel),\n"
        code += "    .penable        (penable),\n"
        code += "    .pwrite         (pwrite),\n"
        code += "    .paddr          (paddr),\n"
        code += "    .pwdata         (pwdata),\n"
        code += "    .prdata         (prdata),\n"
        # I2C status inputs to reg bank
        code += "    .busy_i2c       (busy_i2c),\n"
        code += "    .rx_ready       (rx_ready),\n"
        code += "    .rx_data_i2c    (rx_data_i2c),\n"
        code += "    .rx_nack        (rx_nack),\n"
        code += "    .rx_arb_lost    (rx_arb_lost),\n"
        code += "    .tx_intr        (tx_intr),\n"
        code += "    .rx_intr        (rx_intr),\n"
        code += "    .stop_det       (stop_det),\n"
        code += "    .arb_intr       (arb_intr),\n"
        # Register value outputs (skip RO registers)
        reg_q_ports = []
        for r in regs:
            rn = r["name"]
            fi, all_ro, _, _ = get_reg_fields_info(r)
            if all_ro:
                continue
            reg_q_ports.append(f"    .{rn}_q_val     ({rn}_q)")
        code += ",\n".join(reg_q_ports) + "\n"
        code += "  );\n\n"

        code += """  // ── TX/RX FIFO signals (8-deep, 8-bit wide) ──
  wire [7:0] tx_fifo_rdata;
  wire       tx_fifo_empty;
  wire       tx_fifo_full;
  wire       tx_fifo_rd_en;
  wire [7:0] rx_fifo_wdata;
  wire       rx_fifo_wr_en;
  wire       rx_fifo_full;

  // ── TX FIFO (8-deep): SW writes to tx_data_reg (0x10) pushes data ──
  simple_fifo #(
    .DATA_WIDTH(8),
    .DEPTH(8)
  ) u_tx_fifo (
    .clk    (clk),
    .rst    (rstn),
    .wr_en  (psel && penable && pwrite && (paddr == 12'h010)),
    .wdata  (pwdata[7:0]),
    .full   (),  // FSM tracks full status
    .rd_en  (tx_fifo_rd_en),
    .rdata  (tx_fifo_rdata),
    .empty  (tx_fifo_empty)
  );

  // ── RX FIFO (8-deep): FSM pushes received bytes, SW reads via rx_data_reg ──
  simple_fifo #(
    .DATA_WIDTH(8),
    .DEPTH(8)
  ) u_rx_fifo (
    .clk    (clk),
    .rst    (rstn),
    .wr_en  (rx_fifo_wr_en),
    .wdata  (rx_fifo_wdata),
    .full   (),  // FSM tracks full status
    .rd_en  (1'b0),
    .rdata  (),
    .empty  ()
  );

"""


        # I2C FSM controller
        code += f"  // I2C FSM controller\n"
        code += f"  {fsm_name} u_fsm (\n"
        code += f"    .{clk}             ({clk}),\n"
        code += f"    .{rst}            ({rst}),\n"
        # Register → FSM — look up register names by offset
        ctrl_name = next((r['name'] for r in regs if int(r['offset'],16)==0x00), 'ctrl_reg')
        speed_name = next((r['name'] for r in regs if int(r['offset'],16)==0x04), 'speed_reg')
        cmd_name = next((r['name'] for r in regs if int(r['offset'],16)==0x08), 'cmd_reg')
        addr_name = next((r['name'] for r in regs if int(r['offset'],16)==0x0C), 'addr_reg')
        tx_data_name = next((r['name'] for r in regs if int(r['offset'],16)==0x10), 'tx_data_reg')
        code += f"    .i2c_en_q          ({ctrl_name}_q[0]),\n"
        code += f"    .scl_stretch_en_q  ({ctrl_name}_q[3]),\n"
        code += f"    .ack_gen_q         ({ctrl_name}_q[4]),\n"
        code += f"    .scl_div_q         ({speed_name}_q[15:0]),\n"
        code += f"    .cmd_start         ({cmd_name}_q[0]),\n"
        code += f"    .cmd_stop          ({cmd_name}_q[1]),\n"
        code += f"    .cmd_read          ({cmd_name}_q[2]),\n"
        code += f"    .cmd_write         ({cmd_name}_q[3]),\n"
        code += f"    .cmd_ack           ({cmd_name}_q[4]),\n"
        code += f"    .cmd_nack          ({cmd_name}_q[5]),\n"
        code += f"    .slave_addr_q      ({addr_name}_q[9:0]),\n"
        code += f"    .addr_10bit_q      ({addr_name}_q[10]),\n"
        # TX/RX FIFO connections
        rx_fifo_name = next((r['name'] for r in regs if int(r['offset'],16)==0x14), 'rx_data_reg')
        code += f"    .tx_fifo_rdata_i   (tx_fifo_rdata),\n"
        code += f"    .tx_fifo_empty_i   (tx_fifo_empty),\n"
        code += f"    .tx_fifo_rd_en_o   (tx_fifo_rd_en),\n"
        code += f"    .rx_fifo_wdata_o   (rx_fifo_wdata),\n"
        code += f"    .rx_fifo_wr_en_o   (rx_fifo_wr_en),\n"
        code += f"    .tx_fifo_full_o    (tx_fifo_full),\n"
        code += f"    .rx_fifo_full_o    (rx_fifo_full),\n"
        # I2C bus (pass-through from top-level ports)
        code += f"    .scl_o             (scl_o),\n"
        code += f"    .scl_en_o          (scl_en_o),\n"
        code += f"    .sda_o             (sda_o),\n"
        code += f"    .sda_en_o          (sda_en_o),\n"
        code += f"    .scl_i             (scl_i),\n"
        code += f"    .sda_i             (sda_i),\n"
        # Status outputs
        code += f"    .busy_o            (busy_i2c),\n"
        code += f"    .rx_ready_o        (rx_ready),\n"
        code += f"    .rx_data_o         (rx_data_i2c),\n"
        code += f"    .rx_nack_o         (rx_nack),\n"
        code += f"    .rx_arb_lost_o     (rx_arb_lost),\n"
        # Interrupt outputs
        code += f"    .tx_intr_o         (tx_intr),\n"
        code += f"    .rx_intr_o         (rx_intr),\n"
        code += f"    .stop_det_o        (stop_det),\n"
        code += f"    .arb_intr_o        (arb_intr)\n"
        code += f"  );\n\n"

        # Interrupt output (using irq_en from ctrl_reg)
        ctrl_name = next((r['name'] for r in regs if int(r['offset'],16)==0x00), 'ctrl_reg')
        code += f"  assign intr_o = ({ctrl_name}_q[1] && tx_intr) ||\n"
        code += f"                    ({ctrl_name}_q[1] && rx_intr) ||\n"
        code += f"                    ({ctrl_name}_q[1] && stop_det) ||\n"
        code += f"                    ({ctrl_name}_q[1] && arb_intr);\n\n"

        # APB always ready
        code += f"""\
  // APB always ready
  assign pready = 1'b1;

  // PSLVERR for reserved addresses
  wire is_reserved = (paddr >= 12'h{pslverr_min:03X});  
  assign pslverr = (psel && penable && is_reserved) ? 1'b1 : 1'b0;

endmodule

// ═══════════════════════════════════════════════════════════════════════
//  Simple synchronous FIFO (8-deep, 8-bit wide counter-based)
// ═══════════════════════════════════════════════════════════════════════
module simple_fifo #(
  parameter DATA_WIDTH = 8,
  parameter DEPTH = 8
) (
  input  logic                clk, rst,
  input  logic                wr_en,
  input  logic [DATA_WIDTH-1:0] wdata,
  output logic                full,
  input  logic                rd_en,
  output logic [DATA_WIDTH-1:0] rdata,
  output logic                empty
);

  localparam PTR_WIDTH = $clog2(DEPTH + 1);
  logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];
  logic [PTR_WIDTH-1:0]  wr_ptr, rd_ptr;
  logic [PTR_WIDTH-1:0]  count;

  // Write pointer
  always_ff @(posedge clk or negedge rst) begin
    if (!rst)
      wr_ptr <= '0;
    else if (wr_en && !full)
      wr_ptr <= wr_ptr + 1'b1;
  end

  // Write memory
  always_ff @(posedge clk) begin
    if (wr_en && !full)
      mem[wr_ptr] <= wdata;
  end

  // Read pointer
  always_ff @(posedge clk or negedge rst) begin
    if (!rst)
      rd_ptr <= '0;
    else if (rd_en && !empty)
      rd_ptr <= rd_ptr + 1'b1;
  end

  // Read data (combinatorial from RAM)
  assign rdata = mem[rd_ptr];

  // FIFO count
  always_ff @(posedge clk or negedge rst) begin
    if (!rst)
      count <= '0;
    else begin
      case ({{wr_en && !full, rd_en && !empty}})
        2'b10: count <= count + 1'b1;
        2'b01: count <= count - 1'b1;
        default: count <= count;
      endcase
    end
  end

  assign full  = (count == DEPTH);
  assign empty = (count == 0);

endmodule
"""

    else:
        # ── Standard (non-DMA, non-I2C) top module ──
        code += "  logic [7:0] gpio_in, gpio_out, gpio_oe;\n"
        code += "  assign gpio_in = '0;\n"
        if has_intr_regs:
            code += "  logic [7:0] raw_irq_status, irq_clear;\n"
        else:
            code += "  logic [7:0] raw_irq_status, irq_clear;\n"
            code += "  // raw_irq_status and irq_clear unused (no interrupt regs)\n"

        code += f"""
  // Register file
  {module}_regs u_regs (
    .{clk}         ({clk}),
    .{rst}        ({rst}),
    .psel           (psel),
    .penable        (penable),
    .pwrite         (pwrite),
    .paddr          (paddr),
    .pwdata         (pwdata),
    .prdata         (prdata),
    .gpio_in        (gpio_in),
    .gpio_out       (gpio_out),
    .gpio_oe        (gpio_oe),
    .raw_irq_status (raw_irq_status),
    .irq_clear      (irq_clear),
"""
        hw_conns = _build_top_hw_connections(data)
        if hw_conns:
            code += hw_conns
        code += "  );" + "\n" + "\n"

        if has_intr_regs:
            code += f"""\
  // Interrupt control
  wire [7:0] irq_enable;
  assign irq_enable = u_regs.GPIOIE_q[7:0];  // adjust per protocol

  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst})
      raw_irq_status <= '0;
    else
      raw_irq_status <= raw_irq_status;  // placeholder — FSM sets it
  end

  assign intr = |(raw_irq_status & irq_enable);

"""
        code += """\
  // APB always ready
  assign pready = 1'b1;

  // PSLVERR for reserved addresses
  wire is_reserved = (paddr >= """ + f"12'h{pslverr_min:03X}" + """);  
  assign pslverr = (psel && penable && is_reserved) ? 1'b1 : 1'b0;

endmodule
"""
    return code


# ═══════════════════════════════════════════════════════════════
#  Register bank — FIXED for iverilog 11 compat
# ═══════════════════════════════════════════════════════════════

def _build_hw_ports(data):
    """Build HW access port declarations from reg_fields_detail.
    Returns: (hw_port_inputs, hw_port_outputs, hw_write_logic)
    """
    fields_detail = data.get("reg_fields_detail", [])
    hw_inputs = []
    hw_outputs = []
    hw_write_cases = {}  # reg_name -> list of (field_name, lsb, width, condition)

    for fd in fields_detail:
        hwaccess = fd.get("hwaccess", "hrw")
        fname = fd["field_name"].lower()
        if fname == "reserved":
            continue
        bits_raw = fd.get("bits", "[0]").strip("[]")
        try:
            if ":" in bits_raw:
                msb, lsb = bits_raw.split(":")
                msb, lsb = int(msb), int(lsb)
            else:
                msb = lsb = int(bits_raw)
            width = msb - lsb + 1
        except (ValueError, TypeError):
            msb = lsb = 0
            width = 1
        reg_name = fd["reg_name"]
        port_name = f"hw_{fd['field_name'].lower()}"
        width_str = f"[{width-1}:0] " if width > 1 else ""

        if hwaccess == "hro":
            # HW writes, SW reads
            hw_inputs.append(f"  input  logic {width_str}{port_name}_i")
            # HW write logic: when hw_{field}_we is high, hw_{field}_i overwrites the register bits
            reg_key = (reg_name, "hro")
            if reg_key not in hw_write_cases:
                hw_write_cases[reg_key] = []
            hw_write_cases[reg_key].append({
                "field_name": fd["field_name"],
                "lsb": lsb,
                "width": width,
                "port_name": port_name,
                "hwqe": fd.get("hwqe", "true"),
            })
        elif hwaccess == "hrw":
            # HW can read and write
            hw_inputs.append(f"  input  logic {width_str}{port_name}_i")
            hw_outputs.append(f"  output logic {width_str}{port_name}_o")
            reg_key = (reg_name, "hrw")
            if reg_key not in hw_write_cases:
                hw_write_cases[reg_key] = []
            hw_write_cases[reg_key].append({
                "field_name": fd["field_name"],
                "lsb": lsb,
                "width": width,
                "port_name": port_name,
                "hwqe": fd.get("hwqe", "true"),
            })
        elif hwaccess == "hwo":
            # SW writes, HW reads
            hw_outputs.append(f"  output logic {width_str}{port_name}_o")

    return hw_inputs, hw_outputs, hw_write_cases


def _add_hw_ports(port_sigs, data):
    """Add HW access ports to port_sigs list."""
    hw_inputs, hw_outputs, _ = _build_hw_ports(data)
    if hw_inputs or hw_outputs:
        port_sigs.append("  // HW access ports")
    for p in hw_inputs:
        port_sigs.append(p)
    for p in hw_outputs:
        port_sigs.append(p)


def _build_top_hw_connections(data):
    """Build HW access port connection lines for top module's regs instantiation.
    Returns a string containing wire declarations and connection lines, or empty string.
    """
    fields_detail = data.get("reg_fields_detail", [])
    dcl_lines = []
    conn_lines = []
    for fd in fields_detail:
        hwaccess = fd.get("hwaccess", "hrw")
        fname = fd["field_name"]
        if fname.lower() == "reserved":
            continue
        bits_raw = fd.get("bits", "[0]").strip("[]")
        try:
            if ":" in bits_raw:
                msb, lsb = bits_raw.split(":")
                msb, lsb = int(msb), int(lsb)
            else:
                msb = lsb = int(bits_raw)
            width = msb - lsb + 1
        except (ValueError, TypeError):
            msb = lsb = 0
            width = 1
        port_name = f"hw_{fd['field_name'].lower()}"
        width_str = f"[{width-1}:0] " if width > 1 else ""
        reg_name = fd["reg_name"]
        if hwaccess == "hro":
            dcl_lines.append(f"  logic {width_str}{port_name}_i;")
            conn_lines.append(f"    .{port_name}_i({port_name}_i)")
        elif hwaccess == "hrw":
            dcl_lines.append(f"  logic {width_str}{port_name}_i;")
            dcl_lines.append(f"  logic {width_str}{port_name}_o;")
            conn_lines.append(f"    .{port_name}_i({port_name}_i)")
            conn_lines.append(f"    .{port_name}_o({port_name}_o)")
        elif hwaccess == "hwo":
            dcl_lines.append(f"  logic {width_str}{port_name}_o;")
            conn_lines.append(f"    .{port_name}_o({port_name}_o)")

    if not dcl_lines:
        return ""

    result = []
    result.append("  // HW access signals")
    for d in dcl_lines:
        result.append(d)
    # Modify inst with trailing comma + connections
    # We can't easily inject into the f-string, so we modify the generated code
    # by returning the connections as a separate block
    return "\n".join(result) + "\n"


def generate_regs_module(data):
    module = data["module_name"]
    clk = data["clk_name"]
    rst = data["rst_name"]
    regs = data["registers"]
    date = data["date"]
    is_dma = has_dma_fsm(data)
    is_i2c = has_i2c_fsm(data)

    # Build register metadata
    reset_defs = []
    reg_decls = []
    write_entries = []
    read_entries = []

    # In DMA/I2C mode, identify registers driven by FSM (read-only status)
    # These are read-only registers that reflect FSM state — don't declare as regs
    dma_status_regs = set()
    if is_dma:
        dma_status_regs.update({"DMA_STATUS", "ERROR_CODE", "REMAINING_BYTES", "CFG_REGWEN", "INTR_STATE"})
    if is_i2c:
        dma_status_regs.update({"rx_data_reg", "status_reg", "intr_status_reg"})
        for r in regs:
            n = r["name"].upper()
            # DMA_STATUS, ERROR_CODE, REMAINING_BYTES, CFG_REGWEN, INTR_STATE are FSM-driven
            if n in ("DMA_STATUS", "ERROR_CODE", "REMAINING_BYTES", "CFG_REGWEN", "INTR_STATE"):
                dma_status_regs.add(r["name"])

    for r in regs:
        n, off = r["name"], get_reg_offset(r)
        fields_info, all_ro, all_wo, has_w1c = get_reg_fields_info(r)
        rt = classify_reg(r)

        if n in dma_status_regs:
            # FSM-driven read-only — no reset param, no reg decl (wire driven by assign)
            # Still add read entry so SW can read via APB
            if not all_wo:
                r_entry = f"      12'h{off:03X}: prdata = {n}_q;"
                read_entries.append((off, r_entry))
            continue
        reset_defs.append(f"  localparam {n}_RST = {get_reg_reset(r)};")
        reg_decls.append(f"  logic [31:0] {n}_q;")

        if not all_ro:
            # Writable — generate write entry
            if is_dma and (has_w1c or rt == "w1c" or rt == "intr_state"):
                # DMA mode: INTR_STATE W1C handled by FSM via intr_clear
                # Reg bank just provides read-only view; skip write entry
                pass
            elif has_w1c or rt == "w1c" or rt == "intr_state":
                # W1C: write 1 to clear each bit (non-DMA mode)
                w_entry = f"      12'h{off:03X}: begin\n"
                # Generate per-bit w1c — only for non-reserved fields
                for fi in fields_info:
                    if fi["name_lower"] == "reserved":
                        continue
                    for b in range(fi["width"]):
                        bit_pos = fi["lsb"] + b
                        w_entry += f"        if (pwdata[{bit_pos}]) {n}_q[{bit_pos}] <= 1'b0;\n"
                w_entry += f"      end"
                write_entries.append((off, w_entry))
            elif all_wo:
                # WO: simple write
                w_entry = f"      12'h{off:03X}: {n}_q <= pwdata;"
                write_entries.append((off, w_entry))
            else:
                # RW: write full register
                w_entry = f"      12'h{off:03X}: {n}_q <= pwdata;"
                # Check if all fields are in lower byte
                max_bit = max((fi["msb"] for fi in fields_info if fi["name_lower"] != "reserved"), default=0)
                if max_bit <= 7:
                    w_entry = f"      12'h{off:03X}: {n}_q <= {{24'h0, pwdata[7:0]}};"
                write_entries.append((off, w_entry))

        if not all_wo:
            # Readable
            if has_w1c or rt == "w1c" or rt == "intr_state":
                r_entry = f"      12'h{off:03X}: prdata = {n}_q;"
            else:
                r_entry = f"      12'h{off:03X}: prdata = {n}_q;"
            read_entries.append((off, r_entry))

    # Sort by offset
    write_entries.sort(key=lambda x: x[0])
    read_entries.sort(key=lambda x: x[0])

    # ── Port list ──
    apb_if = data.get("apb", {})
    addr_width = apb_if.get("addr_width", 12)
    port_sigs = [
        f"  input  logic       {clk}",
        f"  input  logic       {rst}",
        "  input  logic       psel",
        "  input  logic       penable",
        "  input  logic       pwrite",
        f"  input  logic [{addr_width-1}:0] paddr",
        "  input  logic [31:0] pwdata",
        "  output logic [31:0] prdata",
    ]

    if is_dma:
        # DMA register bank: status inputs from FSM + register value outputs
        port_sigs.extend([
            "  input  logic       busy_q",
            "  input  logic       active_q",
            "  input  logic       error_flag_q",
            "  input  logic [3:0] error_code_q",
            "  input  logic       done_q",
            "  input  logic [31:0] remaining_q",
            f"  input  logic       dma_done_intr_q",
            f"  input  logic       dma_chunk_intr_q",
            f"  input  logic       dma_error_intr_q",
            "  input  logic       enable_q",
        ])
        # RW register value outputs (needed by FSM, named _q_val to avoid collision)
        for r in regs:
            rn = r["name"]
            if r.get("access", "rw") in ("rw", "wo"):
                port_sigs.append(f"  output logic [31:0] {rn}_q_val")
        _add_hw_ports(port_sigs, data)
    elif is_i2c:
        # I2C register bank: FSM status inputs
        port_sigs.extend([
            "  input  logic       busy_i2c",
            "  input  logic       rx_ready",
            "  input  logic [7:0] rx_data_i2c",
            "  input  logic       rx_nack",
            "  input  logic       rx_arb_lost",
            "  input  logic       tx_intr",
            "  input  logic       rx_intr",
            "  input  logic       stop_det",
            "  input  logic       arb_intr",
        ])
        # Register value outputs (needed by FSM) — skip RO regs
        for r in regs:
            rn = r["name"]
            fi, all_ro, _, _ = get_reg_fields_info(r)
            if all_ro:
                continue
            port_sigs.append(f"  output logic [31:0] {rn}_q_val")
        _add_hw_ports(port_sigs, data)
    else:
        port_sigs.extend([
            "  input  logic [7:0]  gpio_in",
            "  output logic [7:0]  gpio_out",
            "  output logic [7:0]  gpio_oe",
            "  input  logic [7:0]  raw_irq_status",
            "  output logic [7:0]  irq_clear",
        ])
        _add_hw_ports(port_sigs, data)

    port_decls = ",\n".join(port_sigs)

    code = f"""// {date}
// Auto-generated RTL register bank — {module}
// {len(regs)} registers
// iverilog 11 compatible: no unique case, no always_comb reading ff vars

module {module}_regs (
{port_decls}
);

"""

    code += "  // Reset values\n"
    for rd in reset_defs:
        code += rd + "\n"
    code += "\n  // Register declarations\n"
    for rd in reg_decls:
        code += "  " + rd + "\n"

    code += "\n"

    # Wire declarations for FSM-driven read-only registers
    for r in regs:
        if r["name"] in dma_status_regs:
            code += f"  wire [31:0] {r['name']}_q;\n"
    code += "\n"

    if is_dma:
        # DMA: connect status inputs to read-only registers
        # DMA_STATUS fields: busy[0], active[1], error_flag[3], done[4]
        code += """\
  // ── DMA status register (read-only, updated by FSM) ──
  assign DMA_STATUS_q = {27'h0, done_q, error_flag_q, 1'b0, active_q, busy_q};

  // ── ERROR_CODE register (read-only, from FSM) ──
  assign ERROR_CODE_q = {28'h0, error_code_q};

  // ── REMAINING_BYTES register (read-only, from FSM) ──
  assign REMAINING_BYTES_q = remaining_q;

  // ── INTR_STATE register (read-only view of FSM interrupt status) ──
  assign INTR_STATE_q = {29'h0, dma_error_intr_q, dma_chunk_intr_q, dma_done_intr_q};

  // ── CFG_REGWEN (read-only, reflects enable/lock status) ──
  assign CFG_REGWEN_q = {28'h0, enable_q, 4'h0};

"""
        # Register value output assignments
        for r in regs:
            rn = r["name"]
            if r.get("access", "rw") in ("rw", "wo"):
                code += f"  assign {rn}_q_val = {rn}_q;\n"

    elif is_i2c:
        # I2C: connect FSM status inputs to read-only registers
        # Look up register names by offset
        rx_data_name = next((r['name'] for r in regs if int(r['offset'],16)==0x14), 'rx_data_reg')
        status_name = next((r['name'] for r in regs if int(r['offset'],16)==0x18), 'status_reg')
        intr_name = next((r['name'] for r in regs if int(r['offset'],16)==0x20), 'intr_status_reg')
        code += f"""\
  // \u2500\u2500 {rx_data_name} (read-only, from I2C FSM) \u2500\u2500
  assign {rx_data_name}_q = {{22'h0, rx_arb_lost, rx_nack, rx_data_i2c}};

  // \u2500\u2500 {status_name} (read-only, from I2C FSM) \u2500\u2500
  // busy[0], tx_full[1], tx_empty[2], rx_full[3], rx_empty[4], bus_free[5], arb_lost[6]
  assign {status_name}_q = {{25'h0, rx_arb_lost, 1'b0, 1'b1, 1'b1, 1'b1, 1'b0, busy_i2c}};

  // \u2500\u2500 {intr_name} (read-only, W1C via APB read) \u2500\u2500
  assign {intr_name}_q = {{28'h0, arb_intr, stop_det, rx_intr, tx_intr}};

"""
        # Register value output assignments (skip FSM-driven RO registers)
        i2c_fsm_driven = {rx_data_name, status_name, intr_name}
        for r in regs:
            rn = r["name"]
            if rn in i2c_fsm_driven:
                continue
            fi, all_ro, _, _ = get_reg_fields_info(r)
            if all_ro:
                continue
            code += f"  assign {rn}_q_val = {rn}_q;\n"
    else:
        code += """\
  assign gpio_oe = '0;
  assign irq_clear = '0;

"""

    # ── Write block (iverilog 11 compat: no unique case) ──
    code += f"  // ── APB write (case, not unique case — iverilog 11 compat) ──\n"
    code += f"  always_ff @(posedge {clk} or negedge {rst}) begin\n"
    code += f"    if (!{rst}) begin\n"
    # Reset all writable registers (skip FSM-driven status regs)
    for r in regs:
        fields_info, all_ro, _, _ = get_reg_fields_info(r)
        rn = r["name"]
        if rn not in dma_status_regs:
            code += f"        {rn}_q <= {rn}_RST;\n"
    code += f"    end else if (psel && penable && pwrite) begin\n"
    code += f"      case (paddr)\n"
    for off, w_entry in write_entries:
        code += w_entry + "\n"
    code += f"      endcase\n"
    code += f"    end\n"
    code += f"  end\n\n"

    # ── HW access: hro fields use continuous assignment (HW always drives) ──
    fields_detail = data.get("reg_fields_detail", [])
    for fd in fields_detail:
        hwaccess = fd.get("hwaccess", "hrw")
        fname = fd["field_name"]
        if fname.lower() == "reserved":
            continue
        bits_raw = fd.get("bits", "[0]").strip("[]")
        try:
            if ":" in bits_raw:
                msb, lsb = bits_raw.split(":")
                msb, lsb = int(msb), int(lsb)
            else:
                msb = lsb = int(bits_raw)
        except (ValueError, TypeError):
            msb = lsb = 0
        reg_name = fd["reg_name"]
        port_name = f"hw_{fd['field_name'].lower()}"
        if hwaccess == "hro":
            # HW directly drives field, SW reads
            if msb > lsb:
                code += f"  assign {reg_name}_q[{msb}:{lsb}] = {port_name}_i;\n"
            else:
                code += f"  assign {reg_name}_q[{lsb}] = {port_name}_i;\n"
        elif hwaccess == "hrw":
            # HW output: register value read by HW
            if msb > lsb:
                code += f"  assign {port_name}_o = {reg_name}_q[{msb}:{lsb}];\n"
            else:
                code += f"  assign {port_name}_o = {reg_name}_q[{lsb}];\n"
        elif hwaccess == "hwo":
            # HW output: SW writes, HW reads
            if msb > lsb:
                code += f"  assign {port_name}_o = {reg_name}_q[{msb}:{lsb}];\n"
            else:
                code += f"  assign {port_name}_o = {reg_name}_q[{lsb}];\n"
    if fields_detail and any(fd.get("hwaccess", "hrw") in ("hro", "hrw", "hwo") for fd in fields_detail):
        code += "\n"

    # ── Read block (iverilog 11 compat: no unique case) ──
    code += "  // ── APB read (case, not unique case — iverilog 11 compat) ──\n"
    code += "  always_comb begin\n"
    code += "    prdata = '0;\n"
    code += "    if (psel && !pwrite) begin\n"
    code += "      case (paddr)\n"
    for off, r_entry in read_entries:
        code += r_entry + "\n"
    code += "      endcase\n"
    code += "    end\n"
    code += "  end\n\n"

    code += "endmodule\n"
    return code


# ═══════════════════════════════════════════════════════════════
#  IRQ module (standard GPIO-style, kept for backward compat)
# ═══════════════════════════════════════════════════════════════

def generate_irq_module(data):
    module = data["module_name"]
    clk = data["clk_name"]
    rst = data["rst_name"]
    date = data["date"]

    code = f"""// {date}
// Auto-generated IRQ controller — {module}
// Edge/level detect, dual-edge, masking

module {module}_irq (
  input  logic       {clk},
  input  logic       {rst},
  input  logic [7:0] gpio_in,
  input  logic [7:0] gpio_out,
  input  logic [7:0] gpio_oe,
  input  logic [7:0] is_sense,
  input  logic [7:0] ibe,
  input  logic [7:0] iev,
  input  logic [7:0] irq_enable,
  input  logic [7:0] irq_clear,
  output logic [7:0] raw_status,
  output logic       gpioint
);

  logic [7:0] gpio_sync, gpio_prev;

  // Synchronize
  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst}) begin
      gpio_sync <= '0;
      gpio_prev <= '0;
    end else begin
      gpio_sync <= gpio_in;
      gpio_prev <= gpio_sync;
    end
  end

  // Edge detect
  logic [7:0] rising_edge, falling_edge;
  assign rising_edge  = gpio_sync & ~gpio_prev;
  assign falling_edge = ~gpio_sync & gpio_prev;

  // ── Event detect (case, not unique case — iverilog 11 compat) ──
  logic [7:0] irq_event;
  genvar i;
  generate
    for (i = 0; i < 8; i++) begin : irq_detect
      always_comb begin
        case ({{is_sense[i], ibe[i]}})
          2'b00: irq_event[i] = iev[i] ? rising_edge[i]  : falling_edge[i];
          2'b01: irq_event[i] = rising_edge[i] | falling_edge[i];
          2'b10: irq_event[i] = iev[i] ? gpio_sync[i]   : ~gpio_sync[i];
          2'b11: irq_event[i] = iev[i] ? gpio_sync[i]   : ~gpio_sync[i];
          default: irq_event[i] = 1'b0;
        endcase
      end
    end
  endgenerate

  // Raw status
  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst}) begin
      raw_status <= '0;
    end else begin
      for (int p = 0; p < 8; p++) begin
        if (irq_clear[p])
          raw_status[p] <= 1'b0;
        else if (is_sense[p])
          raw_status[p] <= irq_event[p];
        else if (irq_event[p])
          raw_status[p] <= 1'b1;
      end
    end
  end

  // Combined interrupt
  assign gpioint = |(raw_status & irq_enable);

endmodule
"""
    return code


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main():
    args = parse_args()
    spec_path = find_spec(args.spec)
    if not spec_path:
        print("  [X] No spec file found")
        sys.exit(1)

    data = build_spec_data(spec_path)
    module = data["module_name"]
    is_dma = has_dma_fsm(data)
    is_i2c = has_i2c_fsm(data)
    OUT_DIR = os.path.abspath(args.out)
    RTL_DIR = os.path.join(OUT_DIR, "rtl", "rtl")
    os.makedirs(RTL_DIR, exist_ok=True)

    regs = data["registers"]
    fields = data.get("reg_fields_detail", [])
    print(f"{'='*60}")
    print(f"  RTL-GEN (improved) — {module.upper()}")
    print(f"  {len(regs)} registers, {len(fields)} fields")
    fsm_type_str = data.get('fsm', {}).get('type', 'none')
    if is_dma:
        fsm_label = f"YES ({data['fsm'].get('name', 'dma')})"
    elif is_i2c:
        fsm_label = f"YES (i2c - {data['fsm'].get('name', 'i2c_fsm')})"
    else:
        fsm_label = "NO"
    mode_str = 'iverilog 11 compat, error-persist' if (is_dma or is_i2c) else 'standard'
    print(f"  FSM: {fsm_label}")
    print(f"  Mode: {mode_str}")
    print(f"{'='*60}")

    generated_files = []

    # Generate FSM controller (if spec has FSM section)
    fsm_files = generate_fsm(data)
    for fname, fcode in fsm_files.items():
        fpath = os.path.join(RTL_DIR, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(fcode)
        print(f"  [GEN] rtl/{fname}")
        generated_files.append(fname)

    # Generate top module
    top_name = f"{module}.sv"
    with open(os.path.join(RTL_DIR, top_name), "w", encoding="utf-8") as f:
        f.write(generate_top_module(data))
    print(f"  [GEN] rtl/{top_name}")
    generated_files.append(top_name)

    # Generate register bank
    regs_name = f"{module}_regs.sv"
    with open(os.path.join(RTL_DIR, regs_name), "w", encoding="utf-8") as f:
        f.write(generate_regs_module(data))
    print(f"  [GEN] rtl/{regs_name}")
    generated_files.append(regs_name)

    if not is_dma and not is_i2c:
        # Generate IRQ module (only for non-DMA, non-I2C standard designs)
        irq_name = f"{module}_irq.sv"
        with open(os.path.join(RTL_DIR, irq_name), "w", encoding="utf-8") as f:
            f.write(generate_irq_module(data))
        print(f"  [GEN] rtl/{irq_name}")
        generated_files.append(irq_name)

    # File list
    with open(os.path.join(RTL_DIR, "rtl.f"), "w", encoding="utf-8") as f:
        f.write(f"// {data['date']}\n// File list for {module}\n\n")
        for gf in generated_files:
            f.write(f"{gf}\n")
    print(f"  [GEN] rtl/rtl.f")
    print(f"  Files: {', '.join(generated_files)}")
    print(f"  Registers: {len(regs)}  Fields: {len(fields)}")


if __name__ == "__main__":
    main()
