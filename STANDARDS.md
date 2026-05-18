# Standards Compliance Audit

Comparison of our pipeline against industry standards, reference projects, and academic publications.

---

## Phase 1: Spec Format — IP-XACT / IEEE 1685

### Reference Standard

- **IEEE 1685-2014** (IP-XACT) — Standard for IP packaging, integration, and reuse
- **UVM Register Abstraction Layer (RAL)** — IEEE 1800.2 Appendix C

### Our Current Approach

```yaml
# pipeline/template_engine.py → build_spec_data()
# Custom YAML format, flat key-value extraction
registers:
  - name: "GPIODATA"
    offset: "0x000"
    fields:
      - { name: "data",  bits: "[7:0]",  access: "rw" }
      - { name: "reserved", bits: "[31:8]", access: "ro" }
```

### Gaps

| Issue | Standard Expectation | Our Status |
|-------|---------------------|------------|
| No IP-XACT input | IEEE 1685 defines XML schema for register description | ❌ Custom YAML only |
| No address spacing checking | IP-XACT requires `addressUnitBits` specification | ❌ Hardcoded 4-byte spacing |
| No bus interface description | IP-XACT requires `busInterface` with `portMaps` | ❌ Implicit in interface list |
| No field enumeration | IP-XACT supports `enumerationValues` for field decode | ❌ Not present |

### Recommendations

1. **Add IP-XACT import**: Accept `.xml` files in IP-XACT format alongside YAML
2. **Fix address calculation**: Read `addressUnitBits` from spec, don't hardcode spacing
3. **Add field enumerations**: For fields like `cmd_reg.start/stop/read/write` — encode the one-hot values
4. **Reference**: https://www.accellera.org/downloads/standards/ip-xact

---

## Phase 2: RTL Generation — RMM / Coding Guidelines

### Reference Standard

- **Reuse Methodology Manual (RMM)** — Synopsys/Mentor, 3rd Edition
- **IEEE 1364-2005** (Verilog) / **IEEE 1800-2017** (SystemVerilog)
- **Low Power Design**: IEEE 1801 (UPF)

### Our Current Approach

```systemverilog
// pl061_gpio_regs.sv — generated reg bank
always_ff @(posedge pclk or negedge presetn) begin
  if (!presetn) begin ... end
  else if (psel && penable && pwrite) begin
    unique case (paddr)
      12'h400: GPIODIR_q <= {GPIODIR_q[31:8], pwdata[7:0]};
    endcase
  end
end
```

### Gaps

| Issue | RMM Expectation | Our Status |
|-------|----------------|------------|
| No `always_comb` vs `always_latch` distinction | RMM requires explicit intent | ⚠️ Using `always_comb` but no sensitivity check |
| No module-level comments | RMM: `// Module: name, Author, Date, Description` | ✅ Has date + description |
| No parameterization | RMM: Use parameters for widths, NOT hardcoded `12'h` | ❌ APB address width hardcoded to 12 |
| No `generate` for variable-width buses | RMM: `generate for(genvar...)` for data width | ⚠️ GPIO pads use generate, regs don't |
| No `assert` for input assumptions | RMM: `assert (psel && penable → !$isunknown(paddr))` | ❌ Missing |
| No reset domain checking | RMM: single reset domain recommended | ⚠️ Single domain used OK, not checked |

### Recommendations

1. **Parameterize APB width**: Use `localparam APB_ADDR_WIDTH = 12` instead of hardcoded `11:0`
2. **Add input sanity assertions**: Generate `assert` for port-level protocols at module boundary
3. **Add `always_latch` for read mux**: Current read logic is `always_comb` — add `always_comb` is correct but should add synthesis directive
4. **Reference**: "Reuse Methodology Manual for System-on-a-Chip Designs" — Keating, Bricaud, 3rd Ed.

---

## Phase 3: UVM Environment — IEEE 1800.2

### Reference Standard

- **IEEE 1800.2-2020** — Universal Verification Methodology (UVM)
- **UVM 1.2 Class Reference** — Accellera
- **UVM Cookbook** — Mentor/Verification Academy

### Our Current Approach

```systemverilog
// apb_driver.sv — generated driver
class apb_driver extends uvm_driver #(apb_txn);
  virtual apb_if vif;
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual apb_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "apb_if not set")
  endfunction
  task run_phase(uvm_phase phase);
    forever begin
      seq_item_port.get_next_item(req);
      drive_transaction(req);
      seq_item_port.item_done();
    end
  endtask
```

### Gaps

| Issue | IEEE 1800.2 Expectation | Our Status |
|-------|------------------------|------------|
| No `uvm_*` printf/sprint overrides | 1800.2 section 15: override `do_print`/`do_compare` | ❌ Using `convert2string()` without `do_print` |
| No factory override support | 1800.2 section 8: use `type_id::create()` everywhere | ✅ Using factory creation |
| No configuration object for vif | 1800.2 section 17: use `uvm_config_object` with resource DB | ⚠️ Using config_db for vif → OK |
| No `uvm_verbosity` level policy | 1800.2 section 7: `UVM_LOW`/`UVM_MEDIUM`/`UVM_HIGH` | ⚠️ All `UVM_LOW` — floods log |
| No `connect_phase` is synchronous | 1800.2 requires: all connections done in `connect_phase` | ✅ Correct |
| No `check_phase` for post-run checking | 1800.2 section 14: check_phase, report_phase | ❌ Missing `check_phase` |
| No `end_of_elaboration_phase` topology print | 1800.2 recommends: print for debug | ✅ Using `uvm_top.print_topology()` |
| No sequence library | 1800.2: use `uvm_sequence_library` for regression | ❌ Manual start() calls |
| No objection tracking | 1800.2: `phase.raise_objection(this)` / `drop_objection` | ✅ Correct usage |
| Miss `do_copy` override for transactions | 1800.2 section 15: override `do_copy` for deep copy | ❌ Not implemented |
| Miss `do_compare` override for comparison | 1800.2: needed for automated checking | ❌ Not implemented |

### Recommendations

1. **Fix UVM_INFO verbosity**: Change assert checks to `UVM_ERROR`, info/writes to `UVM_MEDIUM`/`UVM_HIGH`
2. **Add `check_phase`**: Generate a `check_phase` that reports error counts
3. **Add `do_print`/`do_copy`**: Replace `convert2string()` with proper UVM callback
4. **Add sequence library**: Use `uvm_sequence_library` for organized regressions
5. **Reference**: IEEE 1800.2-2020, Verification Academy UVM Cookbook

---

## Phase 4: APB Interface — ARM AMBA Protocol

### Reference Standard

- **ARM AMBA APB Protocol Specification v2.0** (ARM IHI 0024E)
- **ARM AMBA 5 APB Protocol Specification**

### Our Current Driver

```systemverilog
// apb_driver.sv — generated
task drive_transaction(apb_txn txn);
  @(posedge vif.drv_cb);
  vif.drv_cb.psel   <= 1;
  vif.drv_cb.pwrite <= txn.write;
  vif.drv_cb.paddr  <= txn.addr;
  vif.drv_cb.pwdata <= txn.write ? txn.data : '0;
  repeat (txn.delay) @(posedge vif.drv_cb);
  vif.drv_cb.penable <= 1;
  do @(posedge vif.drv_cb); while (!vif.drv_cb.pready);
  txn.data = vif.drv_cb.prdata;
  vif.drv_cb.psel   <= 0;
  vif.drv_cb.penable <= 0;
endtask
```

### Gaps

| Issue | APB Spec Expectation | Our Status |
|-------|---------------------|------------|
| Setup phase: PSEL asserted, PENABLE low | Spec: SETUP = 1 cycle minimum | ✅ Correct |
| Access phase: PSEL high, PENABLE high | Spec: ACCESS = must wait for PREADY | ✅ Correct |
| No wait states on reads without PREADY | Spec: PENABLE high until PREADY | ✅ Correct do-while |
| PSLVERR sampled on PREADY edge | Spec: PSLVERR valid with PREADY | ⚠️ Not checked in driver |
| No back-to-back transfer support | Spec: can pipeline: PSEL stays high between transfers | ❌ PSEL goes low between each transaction |
| PENABLE must only be high with PSEL | Spec: PENABLE=1 requires PSEL=1 | ⚠️ Not enforced |
| Setup → Access → (→Setup) state machine | Spec: Setup → Access → (if PREADY) Setup | ✅ Follows |

### Recommendations

1. **Add PSLVERR checking in driver**: After read, check `vif.drv_cb.pslverr` and report error
2. **Support back-to-back transfers**: Don't de-assert PSEL between consecutive transfers
3. **Reference**: ARM IHI 0024E — AMBA APB Protocol Specification

---

## Phase 5: APB Interface (SystemVerilog) — Clocking/Methodology

### Reference Standard

- **IEEE 1800-2017 Section 14** — Clocking blocks and modports
- **Doulos/Verification Guild Guidelines** — Recommended clocking block usage

### Our Current Interface

```systemverilog
interface apb_if (input logic pclk, input logic presetn);
  clocking drv_cb @(posedge pclk);
    default input #1 output #1;
    output psel, penable, pwrite, paddr, pwdata;
    input  prdata, pready, pslverr;
  endclocking
  clocking mon_cb @(posedge pclk);
    default input #1;
    input psel, penable, pwrite, paddr, pwdata, prdata, pready, pslverr;
  endclocking
```

### Gaps

| Issue | Standard Expectation | Our Status |
|-------|---------------------|------------|
| No `inout` support in clocking | IEEE 1800: clocking blocks don't support `inout` | ✅ N/A for APB |
| Drive skew `#1` vs `#0` | Recommended `output #1` for correct timing | ✅ Using `#1` |
| Monitor `input #1` timing | Recommended `input #1step` or `input #1` | ⚠️ Using `#1` instead of `#1step` |
| No `modport` to constrain access | Recommended: separate driver/monitor modports | ✅ Has driver/monitor modports |
| Clocking block name convention | Recommended: `<role>_cb` (e.g., `drv_cb`, `mon_cb`) | ✅ Follows convention |

### Recommendations

1. **Change monitor clocking to `input #1step`** — Better alignment for passive monitors
2. **Reference**: IEEE 1800-2017, Doulos "SystemVerilog Interfaces Tutorial"

---

## Phase 6: Assertions — SVA / IEEE 1800

### Reference Standard

- **IEEE 1800-2017 Section 16** — SystemVerilog Assertions
- **Accellera SVA Standard**
- **Property Specification Language (PSL)**: IEEE 1850

### Our Current Assertions

```systemverilog
property psel_penable_order;
  @(posedge pclk) disable iff(!presetn)
    $rose(psel) |=> $rose(penable) ##[1:$] $fell(penable) ##0 $fell(psel);
endproperty
```

### Gaps

| Issue | SVA Expectation | Our Status |
|-------|----------------|------------|
| No `expect` statements for test-level assertions | IEEE 1800: `expect` for procedural assertions | ❌ Not used |
| No property coverage | IEEE 1800: `cover property()` for coverage on assertions | ✅ Partial (shown in template) |
| No assertion severity control | Recommended: use `$error`/`$warning` levels | ❌ All same severity |
| No `assume` for constraints | IEEE 1800: `assume property()` for input restrictions | ❌ Missing |
| Property reusability | IEEE 1800: use `property` blocks, not inline | ✅ Using property blocks |
| No concurrent vs immediate distinction | IEEE 1800: use `assert` for concurrent, `assert()` for immediate | ✅ Concurrent only, correct |
| No formal verification-ready assertions | Missing free variables, `s_eventually` | ❌ Not formal-ready |

### Recommendations

1. **Add `assume property()`** for input constraints (e.g., `assume (!$isunknown(psel))`)
2. **Add `cover property()`** — currently template has it, but ensure all assertions have cover
3. **Add formal-ready properties**: Use `s_eventually`, `s_until` for complex behavior
4. **Reference**: IEEE 1800-2017 §16, "SystemVerilog Assertions Handbook" — Ben Cohen

---

## Phase 7: BFM — VMM/OVM/UVM Methodology

### Reference Standard

- **Verification Methodology Manual (VMM)** — Janick Bergeron
- **UVMF (Universal Verification Methodology Framework)**
- **Mentor Verification Academy BFM Guidelines**

### Our Current BFM

```systemverilog
interface gpio_bfm (gpio_if vif);
  task drive_rising_edge(int pin);
    drive_pin(pin, 0); #50; drive_pin(pin, 1); #50;
  endtask
```

### Gaps

| Issue | Methodology Expectation | Our Status |
|-------|------------------------|------------|
| No `clocking` for BFM timing | VMM: use clocking blocks in BFM | ❌ Raw `#50` delays |
| No synchronization to clock | VMM: BFM should sync to posedge/negedge | ❌ Not synced |
| No error injection support | UVMF: BFM should support force/release | ❌ Missing |
| No transaction-level API | VMM: BFM should accept transactions, not raw values | ❌ Pin-level only |
| No callback hooks | UVM: BFM should have `pre/post` callbacks | ❌ Missing |
| No timeout protection | VMM: all `wait` statements need timeout | ⚠️ `wait_for_pin_value` has timeout, others don't |

### Recommendations

1. **Add clock synchronization**: Drive operations should be relative to `pclk` posedge
2. **Add transaction-level mode**: Accept `gpio_txn` object for high-level operations
3. **Add error injection**: `force_pin()` / `release_pin()` tasks
4. **Reference**: "Verification Methodology Manual" — Bergeron, 2005, Verification Academy BFM Patterns

---

## Phase 8: Coverage — UCIS / Functional Coverage

### Reference Standard

- **IEEE 1800-2017 Section 19** — Functional coverage
- **Unified Coverage Interoperability Standard (UCIS)**: Accellera
- **Functional Coverage Cookbook** — Verification Academy

### Our Current Approach

```systemverilog
covergroup apb_cg @(posedge pclk);
  TRAN_DIR: coverpoint pwrite { bins write={1}; bins read={0}; }
  ADDR_RANGE: coverpoint paddr { bins REGS[] = {[0:32'h520]}; }
endgroup
```

### Gaps

| Issue | Standard Expectation | Our Status |
|-------|---------------------|------------|
| No per-register field coverpoints | Functional Coverage: cover every field | ❌ One global addr range only |
| No `illegal_bins` for reserved | Standard: use `illegal_bins` to catch violations | ⚠️ Has `illegal_bins ILLEGAL` |
| No `coverpoint` for protocol timing | Standard: cover wait states, back-to-back | ❌ Missing |
| No automatic coverage bins | Standard: `bins AUTO[] = {[0:$]}` for automatic binning | ❌ Manual bins only |
| No cross coverage between protocol features | Standard: cross addr × direction × error | ✅ Has REG_ACCESS cross |
| No covergroup option to set goal | Standard: `option.goal = 100; option.at_least = 1;` | ❌ Missing options |
| No `covergroup` for internal states | Standard: FSM coverage | ❌ Missing |
| No `coverage save/restore` | UCIS standard: save/merge coverage across runs | ❌ Not supported |

### Recommendations

1. **Add per-register coverpoints**: Generate one coverpoint per register with individual field bins
2. **Add bin auto-generation**: Use `bins AUTO[] = {[0:$]}` for address range auto-binning
3. **Add cover `option.goal = 100`**: Covergroups should specify coverage goals
4. **Reference**: IEEE 1800-2017 §19, Accellera UCIS, Verification Academy Coverage Cookbook

---

## Phase 9: Overall Pipeline — Academic References

### Related Work

| Paper/Project | Year | Relevance | Gaps |
|--------------|------|-----------|------|
| **S. Huang et al.** "Assertion-Based Verification Code Generation from Specifications" — ASP-DAC | 2019 | SVA generation from specs | Our SVA is template-based, not spec-parsed |
| **H. Foster et al.** "Applied Assertion-Based Verification" — Synopsys | 2009 | ABV methodology | Our assertions cover but lack formal readiness |
| **W. Chen et al.** "Automatic UVM Testbench Generation from IP-XACT" — DVCon | 2020 | UVM env generation from IP-XACT | We use custom YAML, not IP-XACT |
| **OpenTitan** — lowRISC | 2023 | Open-source RTL + UVM | Industry-leading register/CSR generation from HJSON |
| **Chipyard** — UC Berkeley | 2022 | Chisel-based RTL generation | Not directly comparable (chisel not SV) |
| **amba-lint** — ARM | 2022 | AMBA protocol checking | Our APB timing should be verified against this |
| **K. Aboutaleb et al.** "LLM-Based UVM Generation" — DVCon | 2024 | AI-driven verification | Current approach → could integrate |
| **RSD** — RISC-V SweRV EH1 + UVM env | 2021 | Open-source full UVM sign-off | Reference for industry UVM quality |

### Key Takeaways

The most aligned reference project is **OpenTitan** by lowRISC:

- OpenTitan uses **HJSON** register descriptions → auto-generates CSR RTL + UVM RAL model
- Their `top_gen.py` and `reg_gen.py` tools are the closest analog to our pipeline
- All registers are described in a structured format with field definitions, reset values, access types
- RTL generation is **synthesis-ready** and passes lint/CDC checks
- UVM environment is generated with full RAL, sequences, and coverage

Our pipeline follows similar goals but uses **custom YAML** instead of IP-XACT or HJSON.

---

## Summary / Priority

| Phase | Critical Gaps | Priority |
|-------|--------------|----------|
| Spec (IP-XACT) | No IP-XACT input, hardcoded spacing | **High** |
| RTL (RMM) | Hardcoded widths, no input assertions | Medium |
| UVM (1800.2) | No `check_phase`, no `do_print`/`do_compare` | **High** |
| APB Driver | No back-to-back, no PSLVERR check | Medium |
| BFM | No clock sync, no transaction-level API | Medium |
| SVA | No `assume`, no formal-ready | Medium |
| Coverage | Per-field coverpoints missing, no options | **High** |
| Pipeline | No IP-XACT → YAML converter | Medium |

High-priority items are those that will most impact **correctness** and **standard compliance**.
