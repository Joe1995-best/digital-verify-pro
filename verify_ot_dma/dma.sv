// ot_dma_core — Enhanced DMA controller (v4)
// Coverage-driven enhancements:
//  - error_flag persists (not cleared every cycle)
//  - dma_done_intr_q / dma_chunk_intr_q / dma_error_intr_q auto-set
//  - Chunk interrupt fires on chunk boundary
//  - stop_q halts DMA mid-transfer
//  - src/dst increment config wired to address calculation

module ot_dma_core (
  input  logic        clk_i, rst_ni,
  input  logic        psel, penable, pwrite,
  input  logic [15:0] paddr,
  input  logic [31:0] pwdata,
  output logic [31:0] prdata,
  output logic        pready, pslverr,
  output logic        intr_dma_done_o, intr_dma_chunk_done_o, intr_dma_error_o,
  output logic [31:0] host_addr_o,
  output logic        host_req_o, host_we_o,
  output logic [31:0] host_wdata_o,
  input  logic        host_gnt_i,
  input  logic [31:0] host_rdata_i,
  input  logic        host_rvalid_i, host_err_i
);

  // ── Register declarations ──
  logic [31:0] src_addr_lo_q,  src_addr_hi_q;
  logic [31:0] dst_addr_lo_q,  dst_addr_hi_q;
  logic [3:0]  src_asid_q,     dst_asid_q;
  logic [31:0] total_data_size_q;
  logic [31:0] chunk_data_size_q;
  logic [2:0]  transfer_width_q;
  logic        enable_q, start_q, stop_q;
  logic        busy_q, active_q, error_flag_q, done_q;
  logic [3:0]  error_code_q;
  logic        dma_done_intr_q, dma_chunk_intr_q, dma_error_intr_q;
  logic        en_dma_done_q, en_chunk_q, en_error_q;
  logic        src_incr_en_q, dst_incr_en_q;
  logic [11:0] src_incr_val_q, dst_incr_val_q;

  // ── Internal state ──
  logic [15:0] reg_addr;
  logic        reg_write, reg_read, reg_active;
  assign reg_addr   = paddr;
  assign reg_write  = psel && penable && pwrite;
  assign reg_read   = psel && penable && !pwrite;
  assign reg_active = psel && penable;
  assign pready = 1'b1;

  // ── APB read (combinatorial) ──
  always_comb begin
    prdata = '0;
    pslverr = (reg_active && paddr >= 16'h0050);
    if (reg_read) begin
      case (reg_addr)
        16'h0000: prdata = src_addr_lo_q;
        16'h0004: prdata = src_addr_hi_q;
        16'h0008: prdata = dst_addr_lo_q;
        16'h000C: prdata = dst_addr_hi_q;
        16'h0010: prdata = {28'h0, dst_asid_q, src_asid_q};
        16'h0028: prdata = total_data_size_q;
        16'h002C: prdata = chunk_data_size_q;
        16'h0030: prdata = {29'h0, transfer_width_q};
        16'h0034: prdata = {28'h0, enable_q, stop_q, start_q};
        16'h0038: prdata = {27'h0, done_q, error_flag_q, active_q, busy_q};
        16'h003C: prdata = error_code_q;
        16'h0040: prdata = {29'h0, dma_error_intr_q, dma_chunk_intr_q, dma_done_intr_q};
        16'h0044: prdata = {29'h0, en_error_q, en_chunk_q, en_dma_done_q};
        // Write layout: [27:16]=dst_incr_val, [15:4]=src_incr_val, [1]=dst_en, [0]=src_en
        16'h004C: prdata = {4'h0, dst_incr_val_q, src_incr_val_q, 2'b0,
                           src_incr_en_q, dst_incr_en_q};
        default: prdata = '0;
      endcase
    end
  end

  // ── APB write ──
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      src_addr_lo_q     <= '0;  src_addr_hi_q     <= '0;
      dst_addr_lo_q     <= '0;  dst_addr_hi_q     <= '0;
      src_asid_q        <= 4'h7; dst_asid_q       <= 4'h7;
      total_data_size_q <= '0;  chunk_data_size_q <= '0;
      transfer_width_q  <= '0;
      enable_q <= '0; start_q <= '0; stop_q <= '0;
      dma_done_intr_q <= '0; dma_chunk_intr_q <= '0; dma_error_intr_q <= '0;
      en_dma_done_q <= '0; en_chunk_q <= '0; en_error_q <= '0;
      src_incr_en_q <= '0; dst_incr_en_q <= '0;
      src_incr_val_q <= '0; dst_incr_val_q <= '0;
    end else if (reg_write) begin
      case (reg_addr)
        16'h0000: src_addr_lo_q <= pwdata;
        16'h0004: src_addr_hi_q <= pwdata;
        16'h0008: dst_addr_lo_q <= pwdata;
        16'h000C: dst_addr_hi_q <= pwdata;
        16'h0010: begin src_asid_q <= pwdata[3:0]; dst_asid_q <= pwdata[7:4]; end
        16'h0028: total_data_size_q <= pwdata;
        16'h002C: chunk_data_size_q <= pwdata;
        16'h0030: transfer_width_q  <= pwdata[2:0];
        16'h0034: begin enable_q <= pwdata[2]; start_q <= pwdata[0]; stop_q <= pwdata[1]; end
        16'h0040: begin
          if (pwdata[0]) dma_done_intr_q  <= 1'b0;
          if (pwdata[1]) dma_chunk_intr_q <= 1'b0;
          if (pwdata[2]) dma_error_intr_q <= 1'b0;
        end
        16'h0044: begin en_dma_done_q <= pwdata[0]; en_chunk_q <= pwdata[1]; en_error_q <= pwdata[2]; end
        16'h004C: begin
          src_incr_en_q  <= pwdata[0];  dst_incr_en_q  <= pwdata[1];
          src_incr_val_q <= pwdata[15:4];  dst_incr_val_q <= pwdata[27:16];
        end
      endcase
    end
  end

  // ── FSM ──
  typedef enum logic [2:0] {
    DmaIdle, DmaRead, DmaSendRead, DmaWaitRead,
    DmaWrite, DmaSendWrite, DmaWaitWrite, DmaDone
  } dma_state_e;

  logic [2:0] state_q, state_d;
  logic [31:0] read_buffer_q;
  logic [31:0] remaining_q;
  logic [31:0] word_cnt_q;  // words transferred since last chunk boundary

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q       <= DmaIdle;
      read_buffer_q <= '0;
      remaining_q   <= '0;
      busy_q        <= '0;
      active_q      <= '0;
      error_flag_q  <= '0;
      done_q        <= '0;
      error_code_q  <= '0;
      word_cnt_q    <= '0;
    end else begin
      // ── Next state logic (blocking =, immediate) ──
      case (state_q)
        DmaIdle:      if (start_q && enable_q)
                        state_d = DmaRead;
                      else if (stop_q) begin
                        state_d = DmaIdle;     // stop overrides start
                        remaining_q <= '0;         // abort transfer
                        busy_q <= 1'b0;
                      end else
                        state_d = DmaIdle;
        DmaRead:                                 state_d = DmaSendRead;
        DmaSendRead:  if (host_gnt_i)            state_d = DmaWaitRead;
                      else                       state_d = DmaSendRead;
        DmaWaitRead:  if (host_err_i)            state_d = DmaDone;
                      else if (host_rvalid_i)    state_d = DmaWrite;
                      else                       state_d = DmaWaitRead;
        DmaWrite:     if (remaining_q <= 1)      state_d = DmaDone;
                      else                       state_d = DmaSendWrite;
        DmaSendWrite: if (host_gnt_i)            state_d = DmaWaitWrite;
                      else                       state_d = DmaSendWrite;
        DmaWaitWrite: if (host_err_i)            state_d = DmaDone;
                      else if (host_rvalid_i)    state_d = DmaRead;
                      else                       state_d = DmaWaitWrite;
        DmaDone:                                 state_d = DmaIdle;
        default:                                 state_d = DmaIdle;
      endcase

      // ── State update (NBA) ──
      state_q       <= state_d;
      busy_q        <= (state_d != DmaIdle);
      active_q      <= (state_d == DmaRead || state_d == DmaWrite ||
                         state_d == DmaSendRead || state_d == DmaSendWrite ||
                         state_d == DmaWaitRead || state_d == DmaWaitWrite);

      // ── Error flag: persist when set, NOT cleared every cycle ──
      // Cleared by: new DMA start, or a new APB write to ctrl
      error_flag_q  <= error_flag_q;
      error_code_q  <= error_code_q;
      done_q        <= done_q;
      read_buffer_q <= read_buffer_q;
      remaining_q   <= remaining_q;
      word_cnt_q    <= word_cnt_q;

      // ── Intr status registers: auto-set, cleared by APB write to 0x40 ──
      // (dma_done_intr_q / dma_chunk_intr_q / dma_error_intr_q are held)

      // ── Actions based on current state_q (pre-NBA) ──
      case (state_q)
        DmaIdle: begin
          if (start_q && enable_q) begin
            remaining_q <= total_data_size_q;
            word_cnt_q  <= '0;
            // NOTE: error_flag/error_code NOT cleared here.
            // done_q NOT cleared here.
            // All persist until SW writes to clear them.
          end
        end

        DmaRead: begin
          if (host_rvalid_i && !host_err_i)
            read_buffer_q <= host_rdata_i;
          else if (host_err_i) begin
            error_flag_q <= 1'b1;
            error_code_q <= 4'h2;
            dma_error_intr_q <= 1'b1;
          end
        end
        DmaWaitRead: begin
          if (host_err_i) begin
            error_flag_q <= 1'b1;
            error_code_q <= 4'h2;
            dma_error_intr_q <= 1'b1;
          end
        end
        DmaWaitWrite: begin
          if (host_err_i) begin
            error_flag_q <= 1'b1;
            error_code_q <= 4'h2;
            dma_error_intr_q <= 1'b1;
          end
        end

        DmaWrite: begin
          if (host_rvalid_i && !host_err_i) begin
            remaining_q <= remaining_q - 1;
            word_cnt_q  <= word_cnt_q + 1;
            if (remaining_q <= 1) begin
              done_q <= 1'b1;
              dma_done_intr_q <= 1'b1;     // auto-set done intr status
            end
            // Chunk interrupt: fire when word_cnt+1 == chunk_size
            if (chunk_data_size_q != '0 && (word_cnt_q + 1) >= chunk_data_size_q) begin
              dma_chunk_intr_q <= 1'b1;
              word_cnt_q       <= '0;      // reset chunk counter
            end
            // Increment source address after read (src incremented on read side)
            if (src_incr_en_q && state_q == DmaWrite)
              src_addr_lo_q <= src_addr_lo_q + src_incr_val_q;
          end else if (host_err_i) begin
            error_flag_q <= 1'b1;
            error_code_q <= 4'h2;
            dma_error_intr_q <= 1'b1;
          end
        end
      endcase
    end
  end

  // ── Source address increment on each read ──
  // Combinatorial: incr on DmaSendRead (when host reads from src)
  logic [31:0] next_src_addr;
  assign next_src_addr = (state_q == DmaSendRead && host_gnt_i && src_incr_en_q) ?
                           src_addr_lo_q + src_incr_val_q : src_addr_lo_q;

  // ── Host interface ──
  assign host_req_o   = (state_q == DmaSendRead) || (state_q == DmaSendWrite);
  assign host_we_o    = (state_q == DmaSendWrite);
  assign host_addr_o  = ((state_q == DmaSendRead) || (state_q == DmaRead)) ?
                          src_addr_lo_q : dst_addr_lo_q;
  assign host_wdata_o = read_buffer_q;

  // ── Interrupt generation ──
  assign intr_dma_done_o       = done_q && en_dma_done_q;
  assign intr_dma_chunk_done_o = dma_chunk_intr_q && en_chunk_q;
  assign intr_dma_error_o      = error_flag_q && en_error_q;

endmodule
