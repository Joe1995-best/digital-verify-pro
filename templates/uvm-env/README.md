# UVM Environment Template

Place in `templates/uvm-env/` — used by env-builder skill.

## Files

```
├── tb_top.sv.tpl
├── <iface>_if.sv.tpl
├── <iface>_agent.sv.tpl
├── <iface>_driver.sv.tpl
├── <iface>_monitor.sv.tpl
├── <iface>_sequencer.sv.tpl
├── env_pkg.sv.tpl
├── env.sv.tpl
├── base_test.sv.tpl
└── sim/Makefile.tpl
```

## Template Variables

| Variable | Description |
|----------|-------------|
| `{{MODULE_NAME}}` | Top-level module name |
| `{{INTERFACES}}` | List of interfaces from interface-list.yml |
| `{{CLOCK_FREQ}}` | Clock frequency in MHz |
| `{{RESET_POLARITY}}` | active_low / active_high |
| `{{DATA_WIDTH}}` | Data bus width |
| `{{ADDR_WIDTH}}` | Address bus width |
| `{{TIMEOUT_CYCLES}}` | Default timeout in clock cycles |
