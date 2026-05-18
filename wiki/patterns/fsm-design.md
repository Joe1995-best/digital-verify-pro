# FSM Design Patterns for Verification

This guide covers best practices for FSM design, auto-generation from spec YAML,
error flag persistence patterns, and interrupt management with W1C (write-1-to-clear).

---

## 1. FSM Auto-Generation from Spec

The Digital Verify Pro pipeline generates synthesizable FSM RTL from the `fsm:`
section in spec YAML files. The generator produces:

- State encoding (binary, one-hot, gray-code)
- State transition logic
- Output decode logic
- Verilator/synthesis-friendly always_comb + always_ff separation

### Spec Structure

```yaml
fsm:
  type: "spi"    # Used by template_engine to select FSM template
  name: "spi_fsm"
  description: "SPI slave FSM — sclk edge detection, bit shift"
  clocks: ["clk"]
  resets: ["rstn"]
  states:
    - { name: "Idle",       value: 0, desc: "CS deasserted" }
    - { name: "ShiftTx",    value: 1, desc: "Shifting data" }
  transitions:
    - { from: "Idle",    to: "ShiftTx", cond: "!cs_i && spi_en" }
    - { from: "ShiftTx",  to: "Idle",   cond: "cs_i"  }
  interrupts:
    - { name: "tx_done", desc: "Transfer complete", field: "tx_done", enable_field: "en_tx_done" }
```

### Template Mapping

| FSM Type | Template File | Style |
|----------|-------------|-------|
| `i2c` | `pipeline/templates/fsm/i2c_fsm.sv.tpl` | Binary-encoded, SCL counter-based |
| `spi` | `pipeline/templates/fsm/spi_fsm.sv.tpl` | Edge-detected, 1-FF per state |
| `uart` | `pipeline/templates/fsm/uart_fsm.sv.tpl` | Binary, baud-rate clock divider |
| `dma` | `pipeline/templates/fsm/dma_fsm.sv.tpl` | One-hot, pipeline stages |

### Best Practices for Auto-Generated FSMs

1. **Name all states explicitly** — never use `default` as a valid state in generated code
2. **Keep value assignments sequential** — gaps confuse coverage tools
3. **Use consistent reset states** — always make the first state in the list the reset target
4. **Document transition conditions** — add `desc:` to each transition for traceability
5. **Provide default transition** — include an `else -> Idle` fallback in the spec
6. **Separate combinatorial vs sequential** — generated code should use:
   ```systemverilog
   always_ff @(posedge clk or negedge rstn)   // state register
   always_comb                                 // next-state decode
   always_comb                                 // output decode
   ```

---

## 2. Error Flag Persistence Pattern

Protocol controllers often capture error conditions (overflows, underflows, framing errors)
that must persist until explicitly acknowledged. Three patterns:

### Pattern A: Sticky Flag (Recommended)

```systemverilog
always_ff @(posedge clk or negedge rstn) begin
  if (!rstn)
    rx_overflow <= 1'b0;
  else if (overflow_condition)
    rx_overflow <= 1'b1;       // Set — stays set
  else if (clear_overflow)      // Explicit clear
    rx_overflow <= 1'b0;
end
```

**Pros:** Simple, explicit control. **Cons:** Needs clear signal from bus interface.

### Pattern B: Read-to-Clear (RTC)

```systemverilog
assign rx_overflow = overflow_raw & !read_rx_status;
```

**Pros:** No register needed for RO status. **Cons:** Narrow window — overflow missed if not read.

### Pattern C: W1C (Write-1-to-Clear) with Persistence Latch

The W1C pattern lets software write `1` to a status bit to clear it:

```systemverilog
always_ff @(posedge clk or negedge rstn) begin
  if (!rstn)
    rx_overflow_q <= 1'b0;
  else if (overflow_condition)
    rx_overflow_q <= 1'b1;
  else if (w1c_active && pwdata[bit_pos])
    rx_overflow_q <= 1'b0;
end
```

**Where W1C activation:**

```systemverilog
assign w1c_active = psel && penable && pwrite && (paddr == STATUS_OFFSET);
```

### Choosing the Right Pattern

| Pattern | Use Case |
|---------|----------|
| Sticky + dedicated clear bit | Firmware wants explicit control |
| Read-to-clear | Polling mode, no interrupt usage |
| W1C (status reg) | Standard AMBA/ARM peripheral style |
| W1C with separate enable | Interrupt flags with masking |

---

## 3. Interrupt Management — W1C Pattern

W1C is the dominant pattern for interrupt status registers in real-world controllers
(ARM PrimeCell, Synopsys DW_apb_uart, etc.).

### Standard W1C Implementation

```systemverilog
// Interrupt status register — W1C
// Writing 1 to a bit clears it; writing 0 is a no-op
//
// Priority: raw_event > w1c_clear > hold
always_ff @(posedge clk or negedge rstn) begin
  if (!rstn)
    intr_status <= '0;
  else begin
    for (int i = 0; i < N_INTR; i++) begin
      if (raw_event[i])
        intr_status[i] <= 1'b1;               // New event sets the bit
      else if (w1c_write && pwdata[i])
        intr_status[i] <= 1'b0;               // SW writes 1 to clear
      // else: hold current value
    end
  end
end
```

### Combined Status → Interrupt Output

```systemverilog
assign intr = |(intr_status & intr_enable);
```

### W1C Timing

```
CLK      ████░░████░░████░░████░░████
raw_event     ████
intr_status ░░████░░░░░░░░░░░░░░░░░░  ← latched on posedge
pwdata[i]=1                ████████
intr_status ░░████████████░░░░░░░░░░  ← cleared
intr       ░░████████████░░░░░░░░░░  ← follows intr_status
```

### Golden Rule for W1C

> **Always check raw_event BEFORE w1c_clear.**  
> This ensures an event that arrives on the same cycle as a W1C write is not lost.

### Verification Checklist for W1C Interrupts

- [ ] Interrupt is level-sensitive (not edge/one-shot)
- [ ] Writing `0` to a W1C bit does **not** clear it
- [ ] Writing `1` to a cleared W1C bit is a no-op
- [ ] A new event on the same cycle as W1C write sets the bit (event priority)
- [ ] Multiple pending interrupts are OR'd to `intr`
- [ ] Disabled interrupts (`intr_enable = 0`) still latch status — they just don't assert `intr`

---

## 4. Protocol-Specific FSM Patterns

### I2C FSM

- Counter-based SCL generation (not edge-triggered)
- START: SDA goes low while SCL is high
- STOP: SDA goes high while SCL is high
- Arbitration: monitor SDA during transmission, if mismatch → arb_lost

### SPI Slave FSM

- Edge-triggered by SCLK (synchronized to local clk domain)
- 2-cycle synchronization + edge detection for SCLK
- MISO driven on one edge, MOSI sampled on the other (per CPOL/CPHA)
- CS active-low: deassertion mid-transfer = abort

### UART FSM

- Dual FSM: TX state machine + RX state machine (or interleaved)
- Based on baud-rate clock tick, not data edges
- RX uses 16x oversampling to find mid-bit sample point
- START bit detection: falling edge on RX, verify low at mid-point
- Frame error: stop bit sampled as 0 instead of 1
- Break: RX held low for full frame + stop bit time
