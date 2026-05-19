#!/usr/bin/env python3
"""spi_rtl_stitch.py — Post-process SPI slave RTL: add FSM + FIFOs + wire hw_*.

Usage:
    python tools/spi_rtl_stitch.py --dir output_spi/rtl/rtl/
"""
import os, sys, shutil
from pathlib import Path

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", "-d", required=True, help="RTL output directory")
    args = ap.parse_args()

    rtl_dir = Path(args.dir)
    if not rtl_dir.exists():
        print(f"[ERR] {rtl_dir} not found"); return 1

    # Copy FSM template
    fsm_src = Path(__file__).resolve().parent.parent / "pipeline" / "templates" / "spi_slave_fsm.sv"
    if not fsm_src.exists():
        print(f"[ERR] FSM template not found: {fsm_src}"); return 1
    fsm_dst = rtl_dir / "spi_slave_spi_slave_fsm.sv"
    shutil.copy2(fsm_src, fsm_dst)
    print(f"[OK] FSM: {fsm_dst.name}")

    # Patch top module
    top = rtl_dir / "spi_slave.sv"
    src = top.read_text(encoding="utf-8")

    if "u_fsm" in src:
        print("[OK] Already has FSM instantiation, skipping")
        return 0

    add = """
  // -- SPI FSM + FIFOs (added by spi_rtl_stitch) --
  wire [7:0] tx_fifo_rdata;
  wire       tx_fifo_empty, tx_fifo_full;
  wire [7:0] rx_fifo_wdata, rx_fifo_rdata;
  wire       rx_fifo_full, rx_fifo_empty;
  logic      tx_fifo_rd_en;
  wire       rx_fifo_rd;
  logic [7:0] rx_byte;
  logic       busy_spi, rx_ready_spi;
  logic       rx_overflow, tx_underflow;
  logic       rx_full_intr, tx_empty_intr, rx_overflow_intr, tx_underflow_intr;

  // TX FIFO: SW writes to tx_data_reg (0x0C) pushes data
  simple_fifo #(.DATA_WIDTH(8), .DEPTH(8)) u_tx_fifo (
    .clk(clk), .rst(rstn),
    .wr_en(psel && penable && pwrite && (paddr == 12'h00C)),
    .wdata(pwdata[7:0]), .full(tx_fifo_full),
    .rd_en(tx_fifo_rd_en), .rdata(tx_fifo_rdata), .empty(tx_fifo_empty));

  // RX FIFO: FSM pushes, SW reads via rx_data_reg (0x10)
  assign rx_fifo_rd = psel && penable && !pwrite && (paddr == 12'h010);
  simple_fifo #(.DATA_WIDTH(8), .DEPTH(8)) u_rx_fifo (
    .clk(clk), .rst(rstn),
    .wr_en(rx_fifo_wr_en), .wdata(rx_fifo_wdata), .full(rx_fifo_full),
    .rd_en(rx_fifo_rd), .rdata(rx_fifo_rdata), .empty(rx_fifo_empty));

  // SPI FSM controller
  spi_slave_spi_slave_fsm u_fsm (
    .clk(clk), .rstn(rstn),
    .spi_en_q(hw_spi_en_o), .lsb_first_q(hw_lsb_first_o),
    .loopback_q(hw_loopback_o), .cpol_cpha_q({hw_cpha_o, hw_cpol_o}),
    .tx_fifo_rdata_i(tx_fifo_rdata), .tx_fifo_empty_i(tx_fifo_empty),
    .tx_fifo_rd_en_o(tx_fifo_rd_en),
    .rx_fifo_wdata_o(rx_fifo_wdata), .rx_fifo_wr_en_o(rx_fifo_wr_en),
    .sclk_i(sclk_i), .mosi_i(mosi_i), .miso_o(miso_o), .cs_i(cs_i),
    .busy_o(busy_spi), .rx_ready_o(rx_ready_spi),
    .rx_overflow_o(rx_overflow), .tx_underflow_o(tx_underflow),
    .rx_full_intr_o(rx_full_intr), .tx_empty_intr_o(tx_empty_intr),
    .rx_overflow_intr_o(rx_overflow_intr), .tx_underflow_intr_o(tx_underflow_intr));

  // Connect FSM status to regs hw_* inputs
  assign hw_rx_data_i = rx_fifo_rdata;
  assign hw_busy_i = busy_spi;
  assign hw_rx_full_i = rx_fifo_full;
  assign hw_rx_empty_i = rx_fifo_empty;
  assign hw_tx_full_i = tx_fifo_full;
  assign hw_tx_empty_i = tx_fifo_empty;
  assign hw_rx_overflow_i = rx_overflow;
  assign hw_tx_underflow_i = tx_underflow;

  // Interrupt: FSM outputs gated by enable regs
  assign intr = (hw_rx_full_en_o && rx_full_intr) ||
                (hw_tx_empty_en_o && tx_empty_intr) ||
                (hw_rx_overflow_en_o && rx_overflow_intr) ||
                (hw_tx_underflow_en_o && tx_underflow_intr);
"""
    if "endmodule" in src:
        src = src.replace("endmodule", add + "\nendmodule")
        top.write_text(src, encoding="utf-8")
        print(f"[OK] Top: {top.name} (+FSM +FIFOs +hw_* wiring)")
    else:
        print("[ERR] No endmodule"); return 1

    # Update rtl.f
    rtl_f = rtl_dir / "rtl.f"
    if rtl_f.exists():
        fsm_line = "../../output_spi/rtl/rtl/spi_slave_spi_slave_fsm.sv"
        if fsm_line not in rtl_f.read_text():
            with open(rtl_f, "a") as f:
                f.write(fsm_line + "\n")
            print(f"[OK] rtl.f +FSM")

    # Verify compile
    import subprocess
    ivl = r"C:\ProgramData\chocolatey\lib\iverilog\tools\bin\iverilog.exe"
    sv_files = list(rtl_dir.glob("*.sv"))
    result = subprocess.run(
        [ivl, "-g2012", "-s", "spi_slave", "-o", str(rtl_dir / "spi_slave.o")] + [str(f) for f in sv_files],
        capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        print(f"[OK] Compilation PASSED ({len(sv_files)} files)")
    else:
        print(f"[WARN] Compilation has issues:")
        for line in result.stderr.split("\n")[:5]:
            print(f"  {line}")

    print(f"\n[OK] SPI RTL stitching complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
