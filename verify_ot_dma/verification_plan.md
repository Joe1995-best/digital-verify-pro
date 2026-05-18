# Verification Plan: ot_dma_core

**Spec:** OpenTitan DMA Controller with APB interface, 64-bit addressing, interrupt generation

## Design Analysis
- Ports: 1 (1 inputs, 0 outputs)
- FSM States: 6
- Clocks: None
- Resets: None

## Test Scenarios

| # | Name | Type | Priority | Cov Points | Status |
|---|------|------|----------|------------|--------|
| 1 | Reset Sequence | directed | 1 | reset_init, post_reset_state | pending |
| 2 | FSM State Transition Coverage | directed | 2 | fsm_all_states, fsm_transitions | pending |
| 3 | FSM transition: write ¡ú read | directed | 3 | fsm_trans_write_read | pending |
| 4 | FSM transition: read ¡ú Idle | directed | 3 | fsm_trans_read_Idle | pending |
| 5 | FSM transition: Idle ¡ú Read | directed | 3 | fsm_trans_Idle_Read | pending |
| 6 | FSM transition: Read ¡ú Write | directed | 3 | fsm_trans_Read_Write | pending |
| 7 | FSM transition: Write ¡ú Done | directed | 3 | fsm_trans_Write_Done | pending |
| 8 | Constrained Random Test Sequence | constrained_random | 3 | random_all_inputs, random_edge_cases | pending |
| 9 | Error Injection / Resilience | error_injection | 4 | error_injection, x_propagation, unexpected_inputs | pending |

## Coverage Points

| Point | Target | Description | Bins |
|-------|--------|-------------|------|
| [   ] fsm_all_states | fsm_state | All 6 FSM states visited | 6 |
| [   ] fsm_write | fsm_state | FSM state write visited | 1 |
| [   ] fsm_read | fsm_state | FSM state read visited | 1 |
| [   ] fsm_Idle | fsm_state | FSM state Idle visited | 1 |
| [   ] fsm_Read | fsm_state | FSM state Read visited | 1 |
| [   ] fsm_Write | fsm_state | FSM state Write visited | 1 |
| [   ] fsm_Done | fsm_state | FSM state Done visited | 1 |

## Coverage Summary
- **Total:** 7 points
- **Hit:** 0
- **Coverage: 0.0%**
