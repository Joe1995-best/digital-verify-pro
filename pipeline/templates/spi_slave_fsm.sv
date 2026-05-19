// SPI Slave FSM — 4-wire SPI slave controller
// Auto-generated template for digital-verify-pro
// Compatible with iverilog 11 (no unique case, no inside, no always_comb)

module spi_slave_spi_slave_fsm (
  input  logic       clk,
  input  logic       rstn,

  // Register interface
  input  logic       spi_en_q,
  input  logic       lsb_first_q,
  input  logic       loopback_q,
  input  logic [1:0] cpol_cpha_q,

  // TX data (from TX FIFO)
  input  logic [7:0] tx_fifo_rdata_i,
  input  logic       tx_fifo_empty_i,
  output logic       tx_fifo_rd_en_o,

  // RX data (to RX FIFO)
  output logic [7:0] rx_fifo_wdata_o,
  output logic       rx_fifo_wr_en_o,

  // SPI bus
  input  logic       sclk_i,
  input  logic       mosi_i,
  output logic       miso_o,
  input  logic       cs_i,

  // Status outputs
  output logic       busy_o,
  output logic       rx_ready_o,
  output logic       rx_overflow_o,
  output logic       tx_underflow_o,

  // Interrupt outputs
  output logic       rx_full_intr_o,
  output logic       tx_empty_intr_o,
  output logic       rx_overflow_intr_o,
  output logic       tx_underflow_intr_o
);

  typedef enum logic [2:0] {
    SpiIdle,        // 0: Waiting for CS low
    SpiLeading,     // 1: Capture leading edge
    SpiShiftTx,     // 2: Shift out TX bit on trailing edge
    SpiCapture,     // 3: Capture RX bit on leading edge
    SpiBitDone,     // 4: Byte complete
    SpiFifoPush,    // 5: Push received byte to RX FIFO
    SpiCsDeassert   // 6: CS deasserted mid-transfer
  } spi_state_e;

  spi_state_e state_q, state_d;
  logic [7:0] shift_q;           // shift register
  logic [3:0] bit_cnt_q;         // 0..7 = bits remaining
  logic       sclk_d1, sclk_d2;  // SCLK synchronizer (2-flop)
  logic       cs_d1, cs_d2;      // CS synchronizer
  wire sclk_posedge = sclk_d1 && !sclk_d2;  // rising edge
  wire sclk_negedge = !sclk_d1 && sclk_d2;  // falling edge
  wire cs_active = !cs_d1;  // CS is active low
  logic       cpha;            // clock phase (0=leading sample, 1=trailing sample)
  logic       bit_done;
  logic [7:0] rx_byte_q;
  logic       tx_fifo_empty_d1;

  assign cpha = cpol_cpha_q[1];
  assign bit_done = (bit_cnt_q == 4'd0);

  // Synchronize SCLK and CS (2-flop CDC)
  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      sclk_d1 <= 1'b0; sclk_d2 <= 1'b0;
      cs_d1   <= 1'b1; cs_d2   <= 1'b1;
    end else begin
      sclk_d1 <= sclk_i; sclk_d2 <= sclk_d1;
      cs_d1   <= cs_i;   cs_d2   <= cs_d1;
    end
  end

  // Unified always_ff: next-state + actions
  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      state_q       <= SpiIdle;
      shift_q       <= '0;
      bit_cnt_q     <= '0;
      rx_byte_q     <= '0;
      miso_o        <= 1'b0;
      tx_fifo_rd_en_o <= 1'b0;
      rx_fifo_wr_en_o <= 1'b0;
      rx_ready_o     <= 1'b0;
      rx_overflow_o  <= 1'b0;
      tx_underflow_o <= 1'b0;
      rx_full_intr_o      <= 1'b0;
      tx_empty_intr_o     <= 1'b0;
      rx_overflow_intr_o  <= 1'b0;
      tx_underflow_intr_o <= 1'b0;
    end else begin
      // Defaults
      shift_q       <= shift_q;
      bit_cnt_q     <= bit_cnt_q;
      rx_byte_q     <= rx_byte_q;
      miso_o        <= miso_o;
      tx_fifo_rd_en_o <= 1'b0;
      rx_fifo_wr_en_o <= 1'b0;
      rx_ready_o     <= 1'b0;
      rx_overflow_o  <= rx_overflow_o;
      tx_underflow_o <= tx_underflow_o;
      rx_full_intr_o      <= rx_full_intr_o;
      tx_empty_intr_o     <= tx_empty_intr_o;
      rx_overflow_intr_o  <= rx_overflow_intr_o;
      tx_underflow_intr_o <= tx_underflow_intr_o;
      tx_fifo_empty_d1 <= tx_fifo_empty_i;

      // Track TX FIFO empty edge (for underflow detection)
      if (tx_fifo_rd_en_o) tx_fifo_empty_d1 <= 1'b1;

      // Next state (blocking)
      state_d = state_q;
      case (state_q)
        SpiIdle: begin
          miso_o <= 1'b0;
          if (cs_active && spi_en_q) begin
            // CS asserted: load shift reg from TX FIFO
            if (!tx_fifo_empty_i) begin
              tx_fifo_rd_en_o <= 1'b1;
              shift_q   <= lsb_first_q ? tx_fifo_rdata_i : tx_fifo_rdata_i;
              bit_cnt_q <= 4'd7;
              state_d   = cpha ? SpiCapture : SpiShiftTx;
            end else begin
              // No TX data: send 0xFF and flag underflow
              shift_q   <= 8'hFF;
              bit_cnt_q <= 4'd7;
              tx_underflow_o <= 1'b1;
              tx_underflow_intr_o <= 1'b1;
              state_d   = cpha ? SpiCapture : SpiShiftTx;
            end
          end else begin
            state_d = SpiIdle;
          end
        end

        SpiShiftTx: begin
          // Shift out MSB/LSB on SCLK trailing edge
          if (sclk_negedge) begin
            if (loopback_q)
              miso_o <= mosi_i;  // loopback
            else
              miso_o <= lsb_first_q ? shift_q[0] : shift_q[7];
          end
          if (sclk_posedge) begin
            // Capture on leading edge
            shift_q <= lsb_first_q ? {mosi_i, shift_q[7:1]} : {shift_q[6:0], mosi_i};
            if (bit_cnt_q > 0) bit_cnt_q <= bit_cnt_q - 1'b1;
            if (bit_done) begin
              rx_byte_q <= shift_q;
              state_d = SpiFifoPush;
            end else begin
              state_d = SpiCapture;
            end
          end else if (!cs_active) begin
            state_d = SpiCsDeassert;
          end else begin
            state_d = SpiShiftTx;
          end
        end

        SpiCapture: begin
          if (sclk_posedge) begin
            // Capture on leading edge
            shift_q <= lsb_first_q ? {mosi_i, shift_q[7:1]} : {shift_q[6:0], mosi_i};
            if (bit_cnt_q > 0) bit_cnt_q <= bit_cnt_q - 1'b1;
          end
          if (sclk_negedge) begin
            // Drive MISO on trailing edge
            if (loopback_q) miso_o <= mosi_i;
            else miso_o <= lsb_first_q ? shift_q[0] : shift_q[7];
            if (bit_done) begin
              rx_byte_q <= shift_q;
              state_d = SpiFifoPush;
            end else begin
              state_d = SpiShiftTx;
            end
          end else if (!cs_active) begin
            state_d = SpiCsDeassert;
          end else begin
            state_d = SpiCapture;
          end
        end

        SpiFifoPush: begin
          // Push received byte to RX FIFO
          rx_fifo_wdata_o <= rx_byte_q;
          rx_fifo_wr_en_o <= 1'b1;
          rx_ready_o       <= 1'b1;
          rx_full_intr_o   <= 1'b1;
          // Load next TX byte
          if (!tx_fifo_empty_i) begin
            tx_fifo_rd_en_o <= 1'b1;
            shift_q   <= lsb_first_q ? tx_fifo_rdata_i : tx_fifo_rdata_i;
            bit_cnt_q <= 4'd7;
            state_d   = cpha ? SpiCapture : SpiShiftTx;
          end else begin
            shift_q   <= 8'hFF;
            bit_cnt_q <= 4'd7;
            tx_underflow_o <= 1'b1;
            tx_underflow_intr_o <= 1'b1;
            state_d   = cpha ? SpiCapture : SpiShiftTx;
          end
        end

        SpiCsDeassert: begin
          // CS deasserted mid-transfer: return to Idle
          // rx_byte_q holds partial data (discard or keep as-is)
          state_d = SpiIdle;
        end

        default: state_d = SpiIdle;
      endcase

      // State update (NBA)
      state_q <= state_d;

      // Busy output
      busy_o <= cs_active && spi_en_q;
    end
  end

endmodule
