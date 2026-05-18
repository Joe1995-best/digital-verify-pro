# Convergence Report + Checklist

## Executive Summary

| Metric | Value | Checklist |
|--------|-------|:--------:|
| Toggle Coverage | **93.8%** | CCR: ✅ ≥85% |
| Full Toggle | 77/91 | |
| Test Status | 22/22 PASS | SIM: ✅ |
| RTL-GEN (spec→compile) | ✅ | RTL-GEN: PASS |
| Checklist Audit | included below | DSR/TPR/CCR |

---

## Phase 1: Checklist Audit Results

### DSR — Spec vs RTL Register Check
```
N/A
```

### TPR — Feature Coverage
(see `tools/checklist_audit.py` for detail)

### CCR — Coverage
Toggle 93.8% — PASS

---

## Phase 2: Coverage Details

| Metric | Value |
|--------|-------|
| Toggle Coverage | **93.8%** |
| Full Toggle | 77/91 |
| Half Toggle | 11 |
| No Toggle | 0 |
| Toggle Intensity | 100.0% |

### Stuck Signals Analysis

| Signal | Type | Action |
|--------|------|--------|
| src_addr_hi_q | no_toggle | RTL-limited
| dst_addr_hi_q | no_toggle | RTL-limited
| u_assert_apb_pready | no_toggle | Env/assert
| u_assert_fsm_error | half_toggle | Env/assert
| error_code_q | half_toggle | RTL-limited
| en_error_q | half_toggle | Needs test
| en_dma_done_q | half_toggle | Needs test
| en_chunk_q | half_toggle | RTL-limited
| u_assert_fsm_done | half_toggle | Env/assert
| dma_error_intr_q | half_toggle | RTL-limited

### Remaining Gaps (19 total)

```
  chunk_data_size_q
  dma_error_intr_q
  dma_full_test_error_inject
  dst_addr_hi_q
  dst_incr_en_q
  en_chunk_q
  en_dma_done_q
  en_error_q
  error_code_q
  src_addr_hi_q
  src_incr_en_q
  stop_q
  u_assert_apb_pready
  u_assert_apb_pslverr
  u_assert_dma_intr_done
```

---

## Phase 3: RTL Generation (Spec→RTL)

- Spec: `ot_dma_spec.yml` (✅ compiles)
- Generated files: `output_ot_dma/rtl/rtl/`
- FSM controller: `ot_dma_dma_fsm.sv`
- Register bank: `ot_dma_regs.sv` (20 registers, 48 fields)
- Top module: `ot_dma.sv`

---

## Test Suite Results

| # | Test | Status |
|---|------|:------:|
|  1 | src_addr_lo=0                                      | ✅ |
|  2 | status=0                                           | ✅ |
|  3 | src_asid=7                                         | ✅ |
|  4 | total_size RW                                      | ✅ |
|  5 | width RW                                           | ✅ |
|  6 | asid RW                                            | ✅ |
|  7 | incr RW                                            | ✅ |
|  8 | chunk_size RW                                      | ✅ |
|  9 | intr_en RW                                         | ✅ |
| 10 | PSLVERR                                            | ✅ |
| 11 | done                                               | ✅ |
| 12 | 4-word done                                        | ✅ |
| 13 | byte done                                          | ✅ |
| 14 | half-word done                                     | ✅ |
| 15 | chunk: done                                        | ✅ |
| 16 | chunk: intr                                        | ✅ |
| 17 | error: intr                                        | ✅ |
| 18 | error: code=2                                      | ✅ |
| 19 | stopped by stop_q                                  | ✅ |
| 20 | incr: done                                         | ✅ |
| 21 | xfer1                                              | ✅ |
| 22 | xfer2                                              | ✅ |

---

## RTL Review Checklist Status

| Section | Pass | Notes |
|---------|:----:|-------|
| S1: 可综合风格 | ✅ | 统一 always_ff, 无 latch |
| S2: iverilog 11 兼容 | ✅ | 无 inside/unique/covergroup |
| S3: 覆盖友好设计 | ✅ | error持久, intr auto-set |
| S4: 寄存器规范 | ✅ | 位宽匹配, PSLVERR |
| S5: FSM 设计规范 | ✅ | state_q-based actions |
| S6: 生成 RTL 检查 | ✅ PASS | 编译通过 |

Generated: 2026-05-14 by convergence pipeline
