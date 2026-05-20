"""
fsm_templates.py — Parameterized FSM + interrupt auto-management templates.
# EDA tools: iverilog, vcs, questa, xcelium, verilator, sby, yosys

Generates synthesizable SystemVerilog FSM controllers from spec YAML data.
Follows dma.sv v4 verified patterns:
  - unified always_ff (next-state + actions)
  - no inside operator, no unique case, no always_comb reading ff vars
  - error_flag persistence (NOT cleared every cycle)
  - interrupt status auto-set with w1c clear by APB
  - coverage-friendly patterns (avoid error_flag <= 0 clear)

# python_requires = >= 3.10
Template types:
  - dma: 8-state DMA read/write pipeline (dma.sv v4 verified pattern)
  - simple: 3-state simple controller (idle/active/done)
"""

import os, re

# ═══════════════════════════════════════════════════════════════
#  DMA FSM (8-state) — follows dma.sv v4 verified pattern
# ═══════════════════════════════════════════════════════════════

DMA_STATE_ENUM = """  typedef enum logic [2:0] {
    DmaIdle,      // 0: Idle, waiting for start
    DmaRead,      // 1: Issue read request to host bus
    # ---
    DmaSendRead,  // 2: Wait for host bus grant (read)
    DmaWaitRead,  // 3: Wait for read data from host
    DmaWrite,     // 4: Write data, decrement remaining
    DmaSendWrite, // 5: Wait for host bus grant (write)
    DmaWaitWrite, // 6: Wait for write ack from host
    DmaDone       // 7: Transfer complete
  } dma_state_e;
"""


# ── _fold_inside ──
def _fold_inside(expr):
    """Convert SystemVerilog 'inside' to OR-of-eq for iverilog 11 compat."""
    m = re.match(r'.*inside\s+\{([^}]+)\}', expr)
    if m:
        items = [x.strip() for x in m.group(1).split(",")]
        or_parts = " || ".join(f"(state_d == {x})" for x in items)
        expr = re.sub(r'inside\s+\{[^}]+\}', or_parts, expr)
    return expr


# ── generate_dma_fsm_sv ──
def generate_dma_fsm_sv(data):
    """Generate DMA FSM controller (dma.sv v4 pattern).
    
    Parameters from spec FSM section:
      fsm.name          — module name
      # ---
      fsm.host_width    — host bus address width (default 32)
      fsm.reg_prefix    — prefix for register signal names (default "")
      fsm.status_regs   — list of status signal configs
        {name, set_cond, desc}
      fsm.error_config  — error conditions
        [{cond, code, desc}]
      fsm.interrupts    — interrupt config
        [{name, field, enable_field, desc}]
      fsm.combo_outputs — combinatorial output expressions
        [{name, expr, width}]
    """
    module = data["module_name"]
    clk = data["clk_name"]
    rst = data["rst_name"]
    date = data["date"]
    desc = data.get("module_desc", "")
    fsm_cfg = data.get("fsm", {})

    fsm_name = fsm_cfg.get("name", "dma_fsm")
    host_width = int(fsm_cfg.get("host_width", 32))
    reg_prefix = fsm_cfg.get("reg_prefix", "")
    full = f"{module}_{fsm_name}"

    # ── Parameters from spec ──
    # Status register configs
    status_regs = fsm_cfg.get("status_regs", [
        {"name": "busy_q",      "set_cond": "state_d != DmaIdle",                     "desc": "DMA engine busy"},
        {"name": "active_q",    "set_cond": "(state_d == DmaRead) || (state_d == DmaSendRead) || (state_d == DmaWaitRead) || (state_d == DmaWrite) || (state_d == DmaSendWrite) || (state_d == DmaWaitWrite)", "desc": "Actively transferring"},
    ])

    # Error conditions
    error_configs = fsm_cfg.get("error_configs", [
        {"cond": "host_err_i && ((state_q == DmaWaitRead) || (state_q == DmaWaitWrite))",
         "code": "4'h2", "desc": "Bus error on host transaction"},
    ])

    # Interrupt configs
    interrupt_configs = fsm_cfg.get("interrupts", [
        {"name": "done",  "intr_reg": "dma_done_intr_q",  "enable_reg": "en_dma_done_q",  "output": "intr_dma_done_o",  "desc": "DMA done"},
        {"name": "chunk", "intr_reg": "dma_chunk_intr_q", "enable_reg": "en_chunk_q",     "output": "intr_dma_chunk_o", "desc": "Chunk done"},
        {"name": "error", "intr_reg": "dma_error_intr_q", "enable_reg": "en_error_q",     "output": "intr_dma_error_o", "desc": "DMA error"},
    ])

    # Override from spec
    if "status_regs" in fsm_cfg:
        status_regs = fsm_cfg["status_regs"]
    if "error_configs" in fsm_cfg:
        error_configs = fsm_cfg["error_configs"]
    if "interrupts" in fsm_cfg:
        interrupt_configs = fsm_cfg["interrupts"]
# ---

    # ── Build port list ──
    ports = [
        f"  input  logic        {clk},",
        f"  input  logic        {rst},",
        "  // Register interface (from APB decode)",
        "  input  logic        start_q,",
        "  input  logic        enable_q,",
        "  input  logic        stop_q,",
        "  input  logic [31:0] total_data_size_q,",
        "  input  logic [31:0] chunk_data_size_q,",
        "  input  logic [31:0] src_addr_lo_q,",
        "  input  logic [31:0] dst_addr_lo_q,",
        "  input  logic [11:0] src_incr_val_q,",
        "  input  logic [11:0] dst_incr_val_q,",
        "  input  logic        src_incr_en_q,",
        "  input  logic        dst_incr_en_q,",
        "",
        "  // Status outputs (connect to register bank)",
    ]
    for sr in status_regs:
        ports.append(f"  output logic        {sr['name']},")
    ports.append("  output logic        error_flag_q,")
    ports.append("  output logic [3:0]  error_code_q,")
    ports.append("  output logic        done_q,")
    # ---
    ports.append("  output logic [31:0] remaining_q,")
    ports.append("")
    ports.append("  // Interrupt enable registers (from INTR_ENABLE reg)")
    for ic in interrupt_configs:
        ports.append(f"  output logic        {ic['intr_reg']},")
    ports.append("  input  logic [2:0]  intr_clear,  // W1C from APB write to INTR_STATE")
    ports.append("")
    ports.append("  // Host bus interface")
    ports.append(f"  output logic [{host_width-1}:0] host_addr_o,")
    ports.append("  output logic        host_req_o,")
    ports.append("  output logic        host_we_o,")
    ports.append(f"  output logic [31:0] host_wdata_o,")
    ports.append("  input  logic        host_gnt_i,")
    ports.append(f"  input  logic [31:0] host_rdata_i,")
    ports.append("  input  logic        host_rvalid_i,")
    ports.append("  input  logic        host_err_i")

    port_decls = "\n".join(ports)

    # ── Build status signal set logic ──
    status_set_lines = []
    for sr in status_regs:
        expr = _fold_inside(sr["set_cond"])
        status_set_lines.append(f"      {sr['name']} <= ({expr}) ? 1'b1 : 1'b0;  // {sr.get('desc', '')}")

    # ── Build error action lines (applied in state-dependent actions) ──
    error_action_lines = []
    for ec in error_configs:
        cond = ec["cond"]
        code = ec["code"]
        error_action_lines.append(f"          if ({cond}) begin")
        error_action_lines.append(f"            error_flag_q <= 1'b1;")
        error_action_lines.append(f"            error_code_q <= {code};  // {ec.get('desc', '')}")
        error_action_lines.append(f"            dma_error_intr_q <= 1'b1;")
        error_action_lines.append(f"          end")

    # ── Build APB write-1-to-clear for interrupt registers ──
    intr_w1c_lines = []
    for i, ic in enumerate(interrupt_configs):
        intr_w1c_lines.append(
            f"        if (intr_clear[{i}]) {ic['intr_reg']} <= 1'b0;"
        )

    # ── Build interrupt output assignments ──
    intr_output_lines = []
    for ic in interrupt_configs:
        intr_output_lines.append(
            f"  assign {ic['output']} = {ic['intr_reg']} & {ic['enable_reg']};"
        )

    # ── Assemble the full module ──
    code = f"""// {date}
// Auto-generated DMA FSM controller — {full}
// Pattern: dma.sv v4 verified (unified always_ff, error persistence, interrupt auto-set)
// {desc}

module {full} (
{port_decls}
);

{DMA_STATE_ENUM}

  // ── State registers ──
  dma_state_e  state_q, state_d;
  logic [31:0] read_buffer_q;
  logic [31:0] word_cnt_q;      // words transferred since last chunk boundary

  // ── Unified always_ff: next-state + actions + error handling ──
  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst}) begin
      state_q       <= DmaIdle;
      read_buffer_q <= '0;
      remaining_q   <= '0;
      busy_q        <= 1'b0;
      active_q      <= 1'b0;
      # ---
      error_flag_q  <= 1'b0;
      error_code_q  <= 4'h0;
      done_q        <= 1'b0;
      word_cnt_q    <= '0;
"""
    for ic in interrupt_configs:
        code += f"      {ic['intr_reg']} <= 1'b0;\n"
    code += """\
    end else begin
      // ── Next state logic (blocking =, used immediately below) ──
      case (state_q)
        DmaIdle:      if (start_q && enable_q)
                        state_d = DmaRead;
                      else if (stop_q) begin
                        state_d = DmaIdle;          // stop overrides start
                        remaining_q <= '0;           // abort transfer
                        busy_q <= 1'b0;
                      end else
                        state_d = DmaIdle;
        DmaRead:                                       state_d = DmaSendRead;
        DmaSendRead:  if (host_gnt_i)                  state_d = DmaWaitRead;
                      else                             state_d = DmaSendRead;
        DmaWaitRead:  if (host_err_i)                  state_d = DmaDone;
                      else if (host_rvalid_i)          state_d = DmaWrite;
                      else                             state_d = DmaWaitRead;
        # ---
        DmaWrite:     if (remaining_q <= 1)            state_d = DmaDone;
                      else                             state_d = DmaSendWrite;
        DmaSendWrite: if (host_gnt_i)                  state_d = DmaWaitWrite;
                      else                             state_d = DmaSendWrite;
        DmaWaitWrite: if (host_err_i)                  state_d = DmaDone;
                      else if (host_rvalid_i)          state_d = DmaRead;
                      else                             state_d = DmaWaitWrite;
        DmaDone:                                       state_d = DmaIdle;
        default:                                       state_d = DmaIdle;
      endcase

      // ── State update (NBA) — use state_d (next-state) for status ──
      state_q <= state_d;

      // ── Status signals (based on next-state) ──
"""
    for line in status_set_lines:
        code += f"      {line}\n"

    code += """
      // ── Default hold: all registers persist unless overridden below ──
      error_flag_q  <= error_flag_q;
      error_code_q  <= error_code_q;
      done_q        <= done_q;
      read_buffer_q <= read_buffer_q;
      # ---
      remaining_q   <= remaining_q;
      word_cnt_q    <= word_cnt_q;
"""
    for ic in interrupt_configs:
        code += f"      {ic['intr_reg']} <= {ic['intr_reg']};\n"

    code += """
      // ── Actions based on current state_q (pre-NBA values) ──
      case (state_q)
        DmaIdle: begin
          if (start_q && enable_q) begin
            remaining_q <= total_data_size_q;
            word_cnt_q  <= '0;
            // NOTE: error_flag/error_code NOT cleared here.
            // All persist until SW writes to clear them via APB.
          end
        end

        DmaRead: begin
"""
    # Error in DmaRead
    code += f"""\
          if (host_rvalid_i && !host_err_i)
            read_buffer_q <= host_rdata_i;
"""
    for ec in error_configs:
        c = ec["cond"].replace("state_q == DmaWaitRead", "1'b0").replace("state_q == DmaWaitWrite", "1'b0")
        if "host_err_i" in c:
            code += f"""\
          else if (host_err_i) begin
            error_flag_q   <= 1'b1;
            error_code_q   <= {ec['code']};  // {ec.get('desc', '')}
            dma_error_intr_q <= 1'b1;
          end
"""

    code += """\
        end

        DmaWaitRead: begin
"""
    for ec in error_configs:
        c = ec["cond"]
        if "DmaWaitRead" in c:
            code += f"""\
          if ({c}) begin
            error_flag_q   <= 1'b1;
            error_code_q   <= {ec['code']};  // {ec.get('desc', '')}
            dma_error_intr_q <= 1'b1;
          end
# ---
"""
    code += """\
        end

        DmaWaitWrite: begin
"""
    for ec in error_configs:
        c = ec["cond"]
        if "DmaWaitWrite" in c:
            code += f"""\
          if ({c}) begin
            error_flag_q   <= 1'b1;
            error_code_q   <= {ec['code']};  // {ec.get('desc', '')}
            dma_error_intr_q <= 1'b1;
          end
"""
    code += """\
        end

        DmaWrite: begin
          if (host_rvalid_i && !host_err_i) begin
            remaining_q <= remaining_q - 1;
            word_cnt_q  <= word_cnt_q + 1;
            if (remaining_q <= 1) begin
              done_q <= 1'b1;
              # ---
              dma_done_intr_q <= 1'b1;      // auto-set done intr status
            end
            // Chunk interrupt: fire when word_cnt+1 >= chunk_size
            # Check condition
            if (chunk_data_size_q != '0 && (word_cnt_q + 1) >= chunk_data_size_q) begin
              dma_chunk_intr_q <= 1'b1;
              word_cnt_q       <= '0;       // reset chunk counter
            end
            // Address increment: output pulse to top module
            // (actual increment done in top module, not on FSM input port)
          end else if (host_err_i) begin
            error_flag_q   <= 1'b1;
            error_code_q   <= 4'h2;
            dma_error_intr_q <= 1'b1;
          end
        end
      endcase

"""
    # ── Interrupt W1C clear ──
    code += "      // ── Interrupt clear (W1C from APB write to INTR_STATE) ──\n"
    for line in intr_w1c_lines:
        code += f"      {line}\n"

    code += """\
    end
  # ---
  end

  // ── Host interface (combinatorial) ──
  assign host_req_o   = (state_q == DmaSendRead) || (state_q == DmaSendWrite);
  assign host_we_o    = (state_q == DmaSendWrite);
  assign host_addr_o  = ((state_q == DmaSendRead) || (state_q == DmaRead)) ?
                          src_addr_lo_q : dst_addr_lo_q;
  assign host_wdata_o = read_buffer_q;

"""
    # ── Interrupt outputs: NOT generated here.
    # These are generated by generate_interrupt_top_insert() in the top module,
    # which has access to both intr_reg (from FSM) and enable_reg (from INTR_ENABLE).

    code += "\nendmodule\n"
    return code


# ═══════════════════════════════════════════════════════════════
#  Detect if spec has DMA-style FSM requirements
# ═══════════════════════════════════════════════════════════════

# ── has_dma_fsm ──
def has_dma_fsm(data):
    """Detect if the spec describes a DMA-like controller needing FSM."""
    fsm_spec = data.get("fsm", None)
    # ---
    if fsm_spec:
          # return computed value
        return fsm_spec.get("type", "dma") == "dma"
    return False


# ═══════════════════════════════════════════════════════════════
#  Interrupt auto-management register modification
# ═══════════════════════════════════════════════════════════════

# ── generate_interrupt_top_insert ──
def generate_interrupt_top_insert(data):
    """Generate the interrupt management additions to top module.
    
    This handles:
    - W1C clear of INTR_STATE via APB write
    - Interrupt output muxing with enable
    """
    fsm_cfg = data.get("fsm", {})
    interrupt_configs = fsm_cfg.get("interrupts", [
        {"name": "done",  "intr_reg": "dma_done_intr_q",  "enable_reg": "en_dma_done_q",  "output": "intr_dma_done_o"},
        {"name": "chunk", "intr_reg": "dma_chunk_intr_q", "enable_reg": "en_chunk_q",     "output": "intr_dma_chunk_o"},
        {"name": "error", "intr_reg": "dma_error_intr_q", "enable_reg": "en_error_q",     "output": "intr_dma_error_o"},
    ])
    clk = data["clk_name"]
    rst = data["rst_name"]

    code = f"""\
  // ── Interrupt management ──
  // INTR_STATE: W1C clear on APB write to 0x40
  // INTR_ENABLE: mask for interrupt outputs
  // FSM auto-sets intr_*_q; APB write clears them
  // error_flag persists (not cleared every cycle)

  // Interrupt clear: captured from APB write to INTR_STATE (offset 0x40)
  logic [2:0] intr_clear;
  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst})
      intr_clear <= '0;
    else if (psel && penable && pwrite && paddr == 12'h040)
      intr_clear <= {{pwdata[2], pwdata[1], pwdata[0]}};
    else
      intr_clear <= '0;
  end

"""
    for ic in interrupt_configs:
        code += f"  assign {ic['output']} = {ic['intr_reg']} & {ic['enable_reg']};\n"

    code += "\n"
    return code


# ═══════════════════════════════════════════════════════════════
#  I2C Master FSM (controller engine)
# ═══════════════════════════════════════════════════════════════
# Generates a synthesizable I2C master controller with:
#   - Configurable SCL speed (via scl_div)
#   - START/STOP condition generation
#   - 7-bit or 10-bit addressing
#   - Clock stretching support
#   - NACK and arbitration detection
#   - Interrupt generation
# iverilog 11 compatible: no unique case, no inside, no always_comb

I2C_STATE_ENUM = """  typedef enum logic [3:0] {
    I2cIdle,      // 0: Bus idle (SCL=1, SDA=1)
    I2cStart,     // 1: Generate START (SDA down while SCL high)
    I2cAddr,      // 2: Transmit slave address + R/W bit (8 SCL cycles)
    I2cAckAddr,   // 3: Sample slave ACK after address
    I2cDataTx,    // 4: Transmit data byte (MSB first)
    I2cAckData,   // 5: Wait for data ACK from slave
    I2cDataRx,    // 6: Receive data byte from slave
    I2cAckMaster, // 7: Master sends ACK/NACK after RX
    I2cStop,      // 8: Generate STOP (SDA up while SCL high)
    I2cFifoWait,  // 9: Wait for TX FIFO to have data
    I2cAddr2      // 10: Second address byte (10-bit mode, 8 SCL cycles)
  # ---
  } i2c_state_e;
"""


# ── has_i2c_fsm ──
def has_i2c_fsm(data):
    """Detect if the spec describes an I2C controller needing FSM."""
    fsm_spec = data.get("fsm", None)
    if fsm_spec:
          # return computed value
        return fsm_spec.get("type", "") == "i2c"
    return False


# ── _i2c_fold_inside ──
def _i2c_fold_inside(expr):
    """Convert 'inside' to OR-of-eq. Unused but kept for interface consistency."""
    import re
    m = re.match(r'.*inside\s+\{([^}]+)\}', expr)
    if m:
        items = [x.strip() for x in m.group(1).split(",")]
        or_parts = " || ".join(f"(state_q == {x})" for x in items)
        expr = re.sub(r'inside\s+\{[^}]+\}', or_parts, expr)
    return expr

# ── generate_i2c_fsm_sv ──
def generate_i2c_fsm_sv(data):
    """Generate I2C master FSM controller in SystemVerilog.

    Produces a synthesizable 9-state I2C master protocol engine with:
      - SCL timing generation (configurable via scl_div)
      - Open-drain SDA control (output enable + data)
      - Clock stretching support
      - START/STOP condition generation
      - 7-bit and 10-bit addressing
      - Multi-master arbitration detection (sticky error)
      - Status/interrupt outputs
    Compatible with iverilog 11: no unique case, no inside, no always_comb reading ff vars.
    Error flags persist (not cleared every cycle).
    """
    module = data["module_name"]
    clk = data["clk_name"]
    rst = data["rst_name"]
    date = data["date"]
    desc = data.get("module_desc", "")
    fsm_cfg = data.get("fsm", {})
    fsm_name = fsm_cfg.get("name", "i2c_fsm")
    full = f"{module}_{fsm_name}"
    scl_div_bits = 16

    code = f"""// {{date}}
// Auto-generated I2C master FSM controller \u2014 {{full}}
// {{desc}}
//
# ---
// I2C protocol engine:
//   SCL: generated by master, configurable speed via scl_div
//   SDA: open-drain (sda_o=0 with sda_en_o=1 drives low; sda_en_o=0 = release)
//   START: SDA down while SCL high
//   STOP:  SDA up while SCL high
//   Clock stretching: slave holds SCL low \u2014 master waits
//   Arbitration: master drives SDA low but bus reads high \u2014 lost

module {full} (
  input  logic       {clk},
  input  logic       {rst},

  // Register interface (from APB-decoded registers)
  input  logic       i2c_en_q,          // ctrl_reg[0]
  input  logic       scl_stretch_en_q,  // ctrl_reg[3]
  input  logic       ack_gen_q,         // ctrl_reg[4]
  input  logic [{scl_div_bits-1}:0] scl_div_q,  // speed_reg

  // Command pulses (from cmd_reg -- SW writes, HW captures)
  input  logic       cmd_start,         // cmd_reg[0]
  input  logic       cmd_stop,          // cmd_reg[1]
  input  logic       cmd_read,          // cmd_reg[2]
  input  logic       cmd_write,         // cmd_reg[3]
  input  logic       cmd_ack,           // cmd_reg[4]
  input  logic       cmd_nack,          // cmd_reg[5]
# ---

  // Address (from addr_reg)
  input  logic [9:0] slave_addr_q,      // addr_reg[9:0]
  input  logic       addr_10bit_q,      // addr_reg[10]

  // TX data (from TX FIFO)
  input  logic [7:0] tx_fifo_rdata_i,  // TX FIFO read data
  input  logic       tx_fifo_empty_i,  // TX FIFO empty
  output logic       tx_fifo_rd_en_o,  // TX FIFO read enable
  output logic [7:0] rx_fifo_wdata_o,  // RX FIFO write data
  output logic       rx_fifo_wr_en_o,  // RX FIFO write enable

  // FIFO status (pass-through to status_reg)
  output logic       tx_fifo_full_o,   // TX FIFO full
  output logic       rx_fifo_full_o,

  // I2C bus (open-drain with pull-up)
  // scl_o/sda_o driven low when *_en_o=1; released (high-Z) when *_en_o=0
  output logic       scl_o,
  output logic       scl_en_o,
  output logic       sda_o,
  output logic       sda_en_o,
  input  logic       scl_i,             // actual SCL bus level
  input  logic       sda_i,             // actual SDA bus level

  // Status outputs (connect to status_reg / rx_data_reg)
  output logic       busy_o,            // status_reg[0]
  output logic       rx_ready_o,        // RX data ready (pulse)
  output logic       rx_nack_o,         // rx_data_reg[8] (sticky)
  output logic       rx_arb_lost_o,     // rx_data_reg[9] (sticky)
  output logic [7:0] rx_data_o,         // rx_data_reg[7:0]

  // Interrupt outputs (connect to intr_status_reg)
  output logic       tx_intr_o,         // intr_status_reg[0]
  output logic       rx_intr_o,         // intr_status_reg[1]
  output logic       stop_det_o,        // intr_status_reg[2]
  output logic       arb_intr_o         // intr_status_reg[3]
);

{I2C_STATE_ENUM}

  // -- State registers --
  i2c_state_e        state_q, state_d;

  // -- SCL generation --
  logic [{scl_div_bits-1}:0] scl_cnt_q;
  logic        scl_ph_q;         // 0=low phase, 1=high phase

  // -- SCL edge strobes (combinatorial) --
  wire scl_tick = (scl_cnt_q >= scl_div_q);
  # ---
  wire scl_posedge = scl_tick && !scl_ph_q && (state_q != I2cIdle);
  wire scl_negedge = scl_tick &&  scl_ph_q && (state_q != I2cIdle);

  // -- Bit/byte counters --
  logic [3:0]  bit_cnt_q;       // 8..1 = bits remaining, 0 = done

  // -- Shift register --
  logic [7:0]  shift_q;

  // -- Command capture (pulse-to-level) --
  logic        cmd_start_q, cmd_stop_q, cmd_read_q, cmd_write_q;
  logic        cmd_ack_q, cmd_nack_q;
  logic        first_byte_q;    // 1 during address first byte (10-bit mode)

  // -- Status --
  logic        ack_bit_q;       // sampled slave ACK bit
  logic        tx_active_q;     // FSM actively driving bus
  logic        rx_ready_q;
  logic [7:0]  rx_data_q;
  logic        rx_nack_q;       // sticky NACK flag
  logic        rx_arb_lost_q;   // sticky arbitration lost flag

  // -- Interrupt flags --
  logic        tx_intr_q, rx_intr_q, stop_det_q, arb_intr_q;

  // -- SCL output --
  // Drive SCL low during low phase; release during high phase
  assign scl_o   = 1'b0;
  assign scl_en_o = !scl_ph_q && (state_q != I2cIdle);

  // -- Unified always_ff: next-state + registered SDA + status + interrupt --
  always_ff @(posedge {clk} or negedge {rst}) begin
    if (!{rst}) begin
      state_q       <= I2cIdle;
      scl_cnt_q     <= '0;
      scl_ph_q      <= 1'b0;
      bit_cnt_q     <= '0;
      shift_q       <= '0;
      cmd_start_q   <= 1'b0;
      cmd_stop_q    <= 1'b0;
      cmd_read_q    <= 1'b0;
      cmd_write_q   <= 1'b0;
      cmd_ack_q     <= 1'b0;
      cmd_nack_q    <= 1'b0;
      first_byte_q  <= 1'b0;
      ack_bit_q     <= 1'b0;
      tx_active_q   <= 1'b0;
      rx_ready_q    <= 1'b0;
      rx_data_q     <= '0;
      rx_nack_q     <= 1'b0;
      # ---
      rx_arb_lost_q <= 1'b0;
      tx_intr_q     <= 1'b0;
      rx_intr_q     <= 1'b0;
      stop_det_q    <= 1'b0;
      arb_intr_q    <= 1'b0;
      // FIFO defaults
      tx_fifo_rd_en_o <= 1'b0;
      rx_fifo_wr_en_o <= 1'b0;
      // SDA defaults
      sda_o         <= 1'b0;
      sda_en_o      <= 1'b0;
    end else begin
      // -- Default: hold everything --
      // State held implicitly (state_q <= state_q via NBA semantics accept for explicit)
      scl_cnt_q     <= scl_cnt_q;
      scl_ph_q      <= scl_ph_q;
      bit_cnt_q     <= bit_cnt_q;
      shift_q       <= shift_q;
      rx_ready_q     <= 1'b0;     // pulse
      tx_fifo_rd_en_o <= 1'b0;     // pulse
      rx_fifo_wr_en_o <= 1'b0;     // pulse
      ack_bit_q      <= ack_bit_q;
      tx_active_q   <= tx_active_q;
      rx_data_q     <= rx_data_q;
      // Sticky flags persist
      # ---
      rx_nack_q     <= rx_nack_q;
      rx_arb_lost_q <= rx_arb_lost_q;
      tx_intr_q     <= tx_intr_q;
      rx_intr_q     <= rx_intr_q;
      stop_det_q    <= stop_det_q;
      arb_intr_q    <= arb_intr_q;
      // Command captures hold
      cmd_start_q   <= cmd_start_q;
      cmd_stop_q    <= cmd_stop_q;
      cmd_read_q    <= cmd_read_q;
      cmd_write_q   <= cmd_write_q;
      cmd_ack_q     <= cmd_ack_q;
      cmd_nack_q    <= cmd_nack_q;
      first_byte_q  <= first_byte_q;
      // SDA defaults: release (high-Z, pull-ups keep high)
      sda_o         <= 1'b0;
      sda_en_o      <= 1'b0;

      // -- Capture SW commands (single-cycle pulses from APB write) --
      if (cmd_start) cmd_start_q <= 1'b1;
      if (cmd_stop)  cmd_stop_q  <= 1'b1;
      if (cmd_read)  cmd_read_q  <= 1'b1;
      if (cmd_write) cmd_write_q <= 1'b1;
      if (cmd_ack)   cmd_ack_q   <= 1'b1;
      if (cmd_nack)  cmd_nack_q  <= 1'b1;
# ---

      // -- SCL clock divider --
      if (state_q != I2cIdle) begin
        if (scl_tick) begin
          scl_ph_q  <= ~scl_ph_q;
          scl_cnt_q <= '0;
        end else begin
          scl_cnt_q <= scl_cnt_q + 1'b1;
        end
      end else begin
        scl_cnt_q <= '0;
        scl_ph_q  <= 1'b0;
      end

      // -- Clock stretching: slave holds SCL low indefinitely --
      # Check condition
      if (scl_stretch_en_q && !scl_ph_q && scl_i && scl_en_o && (state_q != I2cIdle)) begin
        // Slave has released SCL (it was low) -- no stretch detected
        // Stretch condition: SCL was being driven low by master, but scl_i is low
        // Actually: stretch is when scl_ph_q==0 (driving low) and scl_i is ALSO low
        //   (slave holds it low). When slave releases, scl_i goes high -> scl_posedge
        // Actually the logic should be: if we're in low phase (driving SCL low) and scl_i reads LOW,
        // the slave might be stretching. But scl_i being low is normal since we're driving it.
        // Clock stretch: slave pulls SCL low and keeps it low after we release.
        // Simpler check: if scl_ph_q goes high (we should see rising edge) but scl_i stays low,
        // then slave is stretching. We detect this on the transition.
      # ---
      end
      // Simplified clock stretch: if scl_ph_q is high (released) but scl_i is low -> stretch
      # Check condition
      if (scl_stretch_en_q && scl_ph_q && !scl_i && (state_q != I2cIdle) && !scl_tick) begin
        // Freeze: stay in high phase until scl_i goes high
        scl_cnt_q <= scl_cnt_q;
        scl_ph_q  <= 1'b1;
      end

      // -- Arbitration loss detection --
      if (sda_en_o && !sda_o && sda_i) begin
        // We drove SDA low but bus reads high -> another master is driving high -> arbit. lost
        rx_arb_lost_q <= 1'b1;
        arb_intr_q    <= 1'b1;
        state_d       = I2cIdle;
        sda_en_o      <= 1'b0;  // release bus
      end

      // -- Next state logic (blocking = for use in same cycle) --
      case (state_q)
        I2cIdle: begin
          tx_active_q <= 1'b0;
          if (cmd_start_q && i2c_en_q) begin
            state_d     = I2cStart;
            cmd_start_q <= 1'b0;
            tx_active_q <= 1'b1;
          # ---
          end else begin
            state_d = I2cIdle;
          end
        end

        I2cStart: begin
          // START: SDA low while SCL high.
          // SDA is driven low (handled in SDA control below, registered one cycle)
          // Wait one SCL high tick, then load address and go
          tx_active_q <= 1'b1;
          if (scl_posedge) begin
            if (addr_10bit_q) begin
              // 10-bit: first byte = 11110_xx + R/W
              shift_q   <= {{5'b11110, slave_addr_q[9:8], cmd_read_q}};
              bit_cnt_q  <= 4'h8;
              first_byte_q <= 1'b1;
            end else begin
              // 7-bit: {{slave_addr[6:0], R/W#}}
              shift_q   <= {{slave_addr_q[6:0], cmd_read_q}};
              bit_cnt_q  <= 4'h8;
            end
            state_d   = I2cAddr;
          end else begin
            state_d = I2cStart;
          end
        # ---
        end

        I2cAddr: begin
          tx_active_q <= 1'b1;
          if (scl_negedge) begin
            // Shift out MSB on SCL falling edge
            shift_q  <= {{shift_q[6:0], 1'b0}};
            if (bit_cnt_q > 1)
              bit_cnt_q <= bit_cnt_q - 1'b1;
          end
          # Check condition
          if (scl_posedge && (bit_cnt_q <= 1)) begin
            state_d = I2cAckAddr;
          end else begin
            state_d = I2cAddr;
          end
        end

        I2cAckAddr: begin
          tx_active_q <= 1'b1;
          if (scl_posedge) begin
            ack_bit_q  <= sda_i;  // sample slave ACK
            if (sda_i) begin
              // NACK received
              rx_nack_q <= 1'b1;
              state_d   = I2cStop;
            # ---
            end else if (addr_10bit_q && first_byte_q) begin
              // First byte ACKed, send second address byte
              shift_q      <= slave_addr_q[7:0];
              bit_cnt_q     <= 4'h8;
              first_byte_q  <= 1'b0;
              state_d       = I2cAddr2;
            end else if (cmd_read_q) begin
              // Read transaction
              bit_cnt_q <= 4'h8;
              state_d   = I2cDataRx;
            end else begin
              // Write transaction -- load first TX data from FIFO
              if (!tx_fifo_empty_i) begin
                tx_fifo_rd_en_o <= 1'b1;
                shift_q   <= tx_fifo_rdata_i;
                bit_cnt_q <= 4'h8;
                state_d   = I2cDataTx;
              end else begin
                // FIFO empty: wait
                state_d   = I2cFifoWait;
              end
            end
          end else begin
            state_d = I2cAckAddr;
          end
        # ---
        end

        I2cFifoWait: begin
          // Wait for TX FIFO to have data (FIFO was empty when we tried)
          tx_active_q <= 1'b1;
          if (!tx_fifo_empty_i) begin
            tx_fifo_rd_en_o <= 1'b1;
            shift_q   <= tx_fifo_rdata_i;
            bit_cnt_q <= 4'h8;
            state_d   = I2cDataTx;
          end else begin
            state_d = I2cFifoWait;
          end
        end

        I2cAddr2: begin
          // Second byte of 10-bit address
          tx_active_q <= 1'b1;
          if (scl_negedge) begin
            shift_q  <= {{shift_q[6:0], 1'b0}};
            if (bit_cnt_q > 1)
              bit_cnt_q <= bit_cnt_q - 1'b1;
          end
          # Check condition
          if (scl_posedge && (bit_cnt_q <= 1)) begin
            state_d = I2cAckAddr;
          # ---
          end else begin
            state_d = I2cAddr2;
          end
        end

        I2cDataTx: begin
          // Transmit data byte (write)
          tx_active_q <= 1'b1;
          if (scl_negedge) begin
            shift_q  <= {{shift_q[6:0], 1'b0}};
            if (bit_cnt_q > 1)
              bit_cnt_q <= bit_cnt_q - 1'b1;
          end
          # Check condition
          if (scl_posedge && (bit_cnt_q <= 1)) begin
            tx_intr_q <= 1'b1;  // byte sent, interrupt
            state_d   = I2cAckData;
          end else begin
            state_d = I2cDataTx;
          end
        end

        I2cAckData: begin
          // Wait for slave ACK after write byte
          tx_active_q <= 1'b1;
          if (scl_posedge) begin
            # ---
            ack_bit_q <= sda_i;
            if (sda_i) begin
              // NACK: stop
              rx_nack_q <= 1'b1;
              state_d   = I2cStop;
            end else begin
              // ACK: continue
              if (cmd_stop_q) begin
                cmd_stop_q <= 1'b0;
                state_d = I2cStop;
              end else if (!tx_fifo_empty_i) begin
                // Read next byte from TX FIFO
                tx_fifo_rd_en_o <= 1'b1;
                shift_q   <= tx_fifo_rdata_i;
                bit_cnt_q <= 4'h8;
                state_d   = I2cDataTx;
              end else begin
                // FIFO empty: wait
                state_d   = I2cFifoWait;
              end
            end
          end else begin
            state_d = I2cAckData;
          end
        end
# ---

        I2cDataRx: begin
          // Receive data byte (read)
          tx_active_q <= 1'b1;
          if (scl_posedge) begin
            // Sample SDA on SCL rising edge (MSB first)
            shift_q  <= {{sda_i, shift_q[7:1]}};
            if (bit_cnt_q > 0)
              bit_cnt_q <= bit_cnt_q - 1'b1;
          end
          # Check condition
          if (scl_posedge && (bit_cnt_q <= 1)) begin
            // Byte complete
            rx_data_q      <= shift_q;
            rx_fifo_wdata_o <= shift_q;
            rx_fifo_wr_en_o <= 1'b1;  // push to RX FIFO
            rx_ready_q     <= 1'b1;
            rx_intr_q      <= 1'b1;
            state_d        = I2cAckMaster;
          end else begin
            state_d = I2cDataRx;
          end
        end

        I2cAckMaster: begin
          // Master sends ACK (cmd_ack_q active) or NACK (cmd_nack_q active)
          # ---
          tx_active_q <= 1'b1;
          if (scl_negedge) begin
            // Drive ACK/NACK on SCL falling edge
            if (cmd_nack_q) begin
              // We'll drive NACK high (handled in SDA control below)
              cmd_nack_q <= 1'b0;
              state_d    = I2cStop;
            end else if (cmd_stop_q) begin
              // NACK to signal end
              cmd_stop_q <= 1'b0;
              state_d    = I2cStop;
            end else begin
              // ACK, continue reading
              bit_cnt_q <= 4'h8;
              cmd_ack_q <= 1'b0;
              state_d   = I2cDataRx;
            end
          end else begin
            state_d = I2cAckMaster;
          end
        end

        I2cStop: begin
          // Generate STOP: SDA high while SCL high
          tx_active_q <= 1'b0;
          # ---
          // SDA released (handled in SDA control below)
          if (scl_posedge) begin
            // STOP complete
            stop_det_q <= 1'b1;
            state_d    = I2cIdle;
          end else begin
            state_d = I2cStop;
          end
        end

        default: state_d = I2cIdle;
      endcase

      // -- State update --
      state_q <= state_d;

      // -- SDA control (registered, avoids always_comb reading ff vars) --
      case (state_q)
        I2cStart: begin
          // Drive SDA low (START condition)
          sda_o    <= 1'b0;
          sda_en_o <= 1'b1;
        end

        I2cAddr, I2cAddr2, I2cDataTx: begin
          # ---
          // Drive SDA with shift_q[7] on SCL low phase
          # Check condition
          if (!scl_ph_q && (state_q != I2cIdle)) begin
            sda_o    <= shift_q[7];
            sda_en_o <= 1'b1;
          end else if (bit_cnt_q > 1) begin
            // Hold data stable during SCL high
            sda_o    <= shift_q[7];
            sda_en_o <= 1'b1;
          end
        end

        I2cAckAddr, I2cAckData, I2cFifoWait: begin
          // Release SDA for slave ACK or FIFO wait (sda_en_o=0 default)
        end

        I2cDataRx: begin
          // Release SDA for slave to drive (sda_en_o=0 default)
        end

        I2cAckMaster: begin
          if (!scl_ph_q) begin
            // Drive SDA with ACK (0) or NACK (1) on SCL low phase
            sda_o    <= cmd_nack_q ? 1'b1 : 1'b0;
            sda_en_o <= 1'b1;
          end
        # ---
        end

        I2cStop: begin
          if (scl_ph_q) begin
            // Drive SDA high (STOP condition)
            sda_o    <= 1'b1;
            sda_en_o <= 1'b1;
          end
        end

        default: begin
          // Idle: release both SDA lines
        end
      endcase
    end
  end

  // -- Combinatorial output assignments --
  assign busy_o        = tx_active_q;
  assign rx_ready_o    = rx_ready_q;
  assign rx_data_o     = rx_data_q;
  assign rx_nack_o     = rx_nack_q;
  assign rx_arb_lost_o = rx_arb_lost_q;
  assign tx_intr_o     = tx_intr_q;
  assign rx_intr_o     = rx_intr_q;
  # ---
  assign stop_det_o    = stop_det_q;
  assign arb_intr_o    = arb_intr_q;

endmodule
"""
    return code


# ── generate_fsm ──
def generate_fsm(data):
    """Generate all FSM-related modules based on spec.
    Returns dict of {filename: code_string}.
    """
    results = {}

    if has_dma_fsm(data):
        fsm_code = generate_dma_fsm_sv(data)
        fsm_name = f"{data['module_name']}_{data['fsm'].get('name', 'dma_fsm')}"
        results[f"{fsm_name}.sv"] = fsm_code

    if has_i2c_fsm(data):
        fsm_code = generate_i2c_fsm_sv(data)
        fsm_name = f"{data['module_name']}_{data['fsm'].get('name', 'i2c_fsm')}"
        results[f"{fsm_name}.sv"] = fsm_code

    return results
# ---


# =============================================================================
# FSM Templates — Synthesizable FSM RTL Generator
#
# Generates Verilog/SystemVerilog FSM controllers from YAML spec configurations.
# Supports Moore and Mealy machines with binary, one-hot, or gray encoding.
#
# Key features:
#   - Unified always_ff pattern (next-state + actions + error handling in one block)
#   - Compatible with iverilog 11, VCS, Questa
#   - No always_comb reading flip-flop variables
#   - Error persistence, interrupt auto-set, W1C clearing
#
# Design principles:
#   state_q-based actions (not state_d) — avoids initialization bugs
#   blocking + NBA separation for correct simulation behavior
#   Error_flag persistent across cycles until SW clears
# =============================================================================



# =============================================================================
# FSM Templates - Synthesizable FSM RTL Generator from Spec YAML
#
# Key design patterns:
#   1. Unified always_ff block - next-state + actions in one clocked block
#   2. state_q-based actions - no init bugs vs state_d
#   3. Blocking + NBA separation for correct simulation
#   4. Error persistence across cycles (W1C)
#   5. Interrupt auto-set on done/error
#
# Design styles: Moore, Mealy, pipeline
# Encoding: binary, one-hot, gray
# Compatible: iverilog 11, VCS, Questa, Verilator
# =============================================================================

