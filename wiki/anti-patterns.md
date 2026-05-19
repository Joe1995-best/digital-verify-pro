# Verification Anti-Patterns [COMMON]

## 1. Scoreboard with no timing check
Just comparing data values isn't enough — verify the data arrived at the right cycle.

## 2. Coverage on the wrong abstraction
Cover transactions, not pin-level toggles for functional coverage. Toggle coverage is for gate-level.

## 3. Register model / RTL / spec mismatch
Always cross-check the generated RTL reset values against the spec. Use CSR auto-test.

## 4. One-shot verification
Running one test at one seed covers very little. Use multiple random seeds.

## 5. UVM when you don't need it
For simple blocks, the overhead of UVM (sequencer/driver/monitor/scoreboard) isn't worth it. Use `--gen-tb`.

## 6. Ignoring RO/WO register behavior
Not all registers read back what you write. Read-only and write-only registers are valid design choices. The testbench should know about them.
