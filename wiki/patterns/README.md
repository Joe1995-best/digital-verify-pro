# Architectural Patterns for Verification

## Pattern: Layered Sequence
Use when: Protocol has multiple abstraction levels
```
top_seq → protocol_seq → bus_seq → pin_wiggle_seq
```
Benefit: Reusable mid-level sequences, clean separation of concerns.

## Pattern: Configurable Agent
Use when: Same interface needs multiple configurations
```systemverilog
class apb_agent extends uvm_agent;
  apb_config cfg;  // has is_active, coverage_enable, protocol_version
```
Benefit: One agent → different behaviors without subclassing.

## Pattern: Predictive Scoreboard
Use when: Complex data transformations
```
Monitor Input → Predictor → Expected Output Queue → Compare → Monitor Output
```
Benefit: Catches all data integrity issues.

## Pattern: VIP Wrapper
Use when: Reusing third-party verification IP
```
VIP → VIP Wrapper → Standard API → Environment
```
Benefit: Swap VIPs without changing environment.

## Pattern: Automation Register Test
Use when: Many registers
```
For each reg:
  write(addr, test_pattern)
  read(addr) → check == test_pattern
```
Benefit: Scalable, catches address decode bugs.
