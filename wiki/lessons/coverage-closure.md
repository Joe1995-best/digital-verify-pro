# Coverage Closure: Lessons from the Field [COMMON]

How to close coverage on RTL blocks efficiently. Covers toggle gap triage,
feedback loops from VCD analysis, and practical strategies for functional closure.

---

## 1. Toggle Gap Classification [COMMON]

Not all uncovered toggles are real coverage holes. Classify gaps before chasing them:

### Tier 1: Real Gaps (must fix)

| Signal Pattern | Typical Cause | Fix |
|---------------|---------------|-----|
| Control FSM state never enters `SomeState` | Missing test scenario | Add directed test |
| `full` flag never high | FIFO depth + writes < threshold | Increase burst length |
| `error` signal never asserted | No error injection in testbench | Add parity/overflow/arbitration error tests |
| Interrupt output never toggles | Missing interrupt assertion test | Add interrupt generation test |
| Register bit `X` stuck at 0/1 | RW bit never exercised | Add register access test |

### Tier 2: Design-Limited (acceptable gaps)

| Signal Pattern | Rationale |
|---------------|-----------|
| Reserved field bits never toggled | Hardwired to 0 — intentional |
| `pslverr` never asserted (APB) | Chip only accesses valid addresses |
| Mode bits that require external pin strapping | Not controllable from software |
| Debug-only signals | Only used in simulation debug mode |
| Bits where reset value matches test stimulus | Bit already at correct value — toggle would break functionality |

### Tier 3: Simulation Artifacts (ignore)

- X/Z propagation through unconnected ports
- Timing assertion failures in gate-level simulation
- Glitches shorter than clock period in RTL sim

### Decision Flowchart

```
Uncovered toggle?
    ├─ Reserved/HW-strapped bit?  → Accept (doc in waiver)
    ├─ Requires specific error injection?
    │   ├─ Already have test for it? → Check test didn't reach condition
    │   └─ No test?                 → Add directed error test
    ├─ RO register bit?
    │   ├─ Has HW driver?   → Check driver not activated
    │   └─ No HW driver?    → Accept (design limitation)
    └─ RW register bit?
        └─ Missing from CSR test → Add to write-set
```

---

## 2. From VCD to Directed Test: Feedback Loop [COMMON]

The most efficient coverage closure workflow:

```
[1] Simulate with random tests
    ↓
[2] Merge coverage databases
    ↓
[3] Identify uncovered bins (gaps.json)
    ↓
[4] Analyze gap type (VCD dump + waveform inspection)
    ↓
[5] Write targeted directed test
    ↓
[6] Re-run, verify bin hit
    ↓
[7] Re-merge coverage, move to next gap
```

### Practical VCD Analysis

```bash
# 1. Run simulation with VCD dump
python run_sim.py --spec i2c_spec.yml --vcd output_i2c/top.vcd

# 2. Generate coverage gap report
python cov_report.py --vcd output_i2c/top.vcd --spec i2c_spec.yml

# 3. Inspect gap signals in waveform
python tools/analyze_waveform.py --vcd output_i2c/top.vcd --signal "i2c_fsm_state"

# 4. Generate targeted test from gap analysis
python pipeline/coverage_to_tests.py --vcd output_i2c/top.vcd --spec i2c_spec.yml
```

### Gap Severity Classification

| Severity | Description | Action |
|----------|-------------|--------|
| **Critical** | Functional coverpoint not hit (protocol transaction, error, interrupt) | Must add test |
| **High** | Cross-coverage bin not hit | Add constrained random or directed test |
| **Medium** | Transition coverage gap (state → state) | Add longer test or specific sequence |
| **Low** | Toggle gap on non-critical signal | Document waiver or add if easy |
| **Accept** | Design-limited or redundant | Disable coverage bin or add waiver |

---

## 3. FSM Coverage Closure [COMMON]

FSM coverage needs three metrics:

1. **State coverage** — every state visited at least once
2. **Transition coverage** — every transition fired at least once
3. **Sequence coverage** — common multi-step paths (optional)

### Common FSM Coverage Gaps

| Gap | Root Cause | Fix |
|-----|-----------|-----|
| Error state unreachable | No error injection mechanism | Add error injection via backdoor or dedicated register |
| Idle → Start never taken | Enable bit not set before command | Add setup sequence to test |
| Mid-transfer abort uncovered | CS never deasserted mid-byte | Add specific test for CS deassertion timing |
| Arbitration loss (I2C) unreachable | Single-master-only tests | Add multi-driver testbench configuration |

### FSM Coverage from Spec

The pipeline auto-generates FSM cover properties in the formal check phase.
Each `states` entry in the spec YAML produces a cover property:

```
cover:  fsm_state == IDLE
cover:  fsm_state == START
cover:  fsm_state == DATA_TX
...
```

These can be checked with either:
- **Formal (SymbiYosys)** — prove each state is reachable
- **Simulation** — track which states were entered during simulation

---

## 4. Register Coverage Closure [COMMON]

### Three-Point Verification

For every register field with `access: rw`:

1. **Write all-1s, read back** → verify expected reset value
2. **Write all-0s, read back** → verify write takes effect
3. **Write alternating pattern** → verify bit independence

For `access: wo` (write-only):

1. **Verify value appears at output** (side-effect check)
2. **Read returns undefined/reserved** → verify read doesn't crash

For `access: ro` (read-only):

1. **Verify reset value**
2. **Attempt write, verify no change**

### Auto-Generated CSR Tests

The pipeline's `run_csr_test_gen.py` generates exhaustive register tests.
Expected coverage from CSR auto-test:

- 100% register address coverage (all regs accessed)
- 100% RW field toggle coverage
- 100% reset value check
- WO fields verified at output
- RO fields verified as read-only

---

## 5. Practical Closure Strategy [ALL]

### For Small Blocks (< 50K gates)

```
1. CSR auto-test (covers register toggles)
2. 10 random tests with different seeds (covers 60-70% functional)
3. VCD-dump analysis → identify gaps
4. 3-5 directed tests for uncovered scenarios
5. Formal verification on FSM (state reachability + illegal transitions)
```

### For Medium Blocks (50-200K gates)

```
1. CSR auto-test
2. 50 random tests → coverage plateau identification
3. Gap analysis → classify Tier 1/2/3
4. 10-20 directed tests for Tier 1 gaps
5. Constrained random with feedback (update constraints per gap)
6. Formal verification on critical control logic
```

### For Protocols (I2C, SPI, UART, DMA)

```
1. Protocol transaction coverage at single-speed (all transaction types)
2. Multi-speed + multi-mode (combinatorial expansion)
3. Error injection at every protocol stage
4. FIFO full/empty/drain/fill
5. Interrupt assertion cross-product with FIFO states
6. Reset behavior in every state
```

---

## 6. Tools Integration [COMMON]

```
Pipeline Stage: coverage-plan
 ├→ Coverage definition from spec YAML
 ├→ Auto-generated cover groups (SystemVerilog)
 └→ Coverage database merge

Pipeline Stage: coverage-converge
 ├→ Read coverage database → identify gaps
 ├→ Classify gaps (Tier 1/2/3)
 ├→ Generate gap report (gaps.json)
 ├→ Map gap → test scenario
 └→ Optionally generate targeted test

Pipeline Stage: formal-check
 ├→ FSM state reachability (cover)
 ├→ FSM illegal transitions (assert)
 ├→ Register reset values (assert)
 ├→ FIFO bounds (assert)
 └→ APB protocol compliance (assert)
```
