---
name: cdc-checker
version: 1.0.0
lifecycle: alpha
---

# cdc-checker v1.0.0

**Cross-Domain Clocking (CDC) Static Analysis** for SystemVerilog RTL.

Scans RTL for:
1. Multi-clock domain declarations (`always_ff @(posedge clk_X)`)
2. Asynchronous signal paths (signal driven in `clk_a`, sampled in `clk_b`)
3. Missing/insufficient synchronization (2-stage FF)

## Usage

```bash
python engines/cdc_checker.py --rtl rtl/*.sv --out cdc_report.json
python engines/cdc_checker.py --rtl rtl/ --clk-names pclk,clk_i
```

## Output

```json
{
  "status": "PASS",
  "clock_domains": ["pclk", "clk_i"],
  "total_crossings": 3,
  "unsynchronized": 0,
  "crossings": [
    {"signal": "ctrl_reg", "from": "pclk", "to": "clk_i", "synced": true}
  ],
  "issues": [...]
}
```

## Known Limitations

### Synchronizer Detection: Naming Convention Only ⚠️

Synchronizer detection (`check_synchronizers()`) currently relies on **signal
name pattern matching** (`sync_`, `cdc_`, `sync2ff`, `double_sync`). This is
a heuristic — it does **not** perform structural analysis to verify that a
2-stage flip-flop cascade actually exists in the target clock domain.

**What this misses:**
- Engineers naming synchronizers unconventionally (e.g., `q1_q2_delay`)
- Structural synchronization (e.g., handshake-based, FIFO-based)
- Clock gating synchronizers
- Reset synchronizers

**Expected improvement:** A structural fallback that parses `always_ff` blocks
in the target clock domain to verify two consecutive flip-flops on the
crossing signal. This requires SV AST parsing and is tracked as a
future enhancement.

### Other Limitations

- **No glitch detection:** Does not detect combinational paths crossing
  clock domains (only register-to-register).
- **No reconvergence analysis:** Multiple paths from the same source domain
  are flagged independently.
- **Single-file scope:** Each file is parsed independently; cross-module
  hierarchical analysis is not yet supported.
- **No clock relationship inference:** Assumes all named clocks are
  asynchronous unless specified.

## Dependencies

- **Python**: >= 3.10 (standard library only)
