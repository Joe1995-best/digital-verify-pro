---
name: review
description: >
  Cross-model review of generated verification code. Dispatches UVM/SystemVerilog
  code audits to external LLMs for independent verification.
---

# review

**Reviewer Agent**: cross-model code review.

Dispatches generated verification code to multiple LLM models for independent review. Catches bugs, style issues, protocol violations, and coverage gaps before simulation.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| All generated code | pipeline | yes |
| `reviewers.yml` | Config | yes (or defaults) |

## Default Reviewers

| Model | Role | Specialty |
|-------|------|-----------|
| GPT-4o | Primary reviewer | SystemVerilog/UVM correctness |
| Claude | Secondary reviewer | Test completeness, edge cases |
| Kimi/K2 | Protocol specialist | Protocol compliance |

## Review Checklist

### 1. Structural Checks
- [ ] All UVM component constructors call super.new()
- [ ] All build_phases call super.build_phase()
- [ ] Phasing is correct (build → connect → run → check → report)
- [ ] No missing `uvm_*_utils macros
- [ ] Factory type registration correct

### 2. Functional Checks
- [ ] Driver correctly translates sequences to pin wiggles
- [ ] Monitor correctly translates pin wiggles to transactions
- [ ] Scoreboard comparison logic matches spec
- [ ] Coverage bins cover all spec features
- [ ] Register model addresses match spec

### 3. Protocol Checks
- [ ] Timing diagrams followed correctly
- [ ] All protocol states handled
- [ ] Error injection covers spec-defined errors
- [ ] X/Z propagation handling correct

### 4. Simulation Checks
- [ ] No infinite loops
- [ ] Timeouts on all wait statements
- [ ] All TLMs are sized correctly
- [ ] No race conditions (NBA + blocking assignments)

### 5. UVM Best Practices
- [ ] Config DB used correctly
- [ ] Sequences use `uvm_do` / `uvm_send` macros
- [ ] Objections raised correctly
- [ ] No global variables in verification components

## Output

| File | Description |
|------|-------------|
| `review-report.md` | Per-file review with issues, severity, recommendations |
| `review-scores.yml` | Quality scores per file per model |
