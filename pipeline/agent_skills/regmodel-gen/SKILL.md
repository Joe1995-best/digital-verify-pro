---
name: regmodel-gen
description: >
  Generate UVM register model from register map. Creates reg_block, reg_map,
  register and field classes with all access methods.
---

# regmodel-gen

**Verifier Agent**: UVM register model generation.

Generates a complete UVM register model from the register map extracted by spec-analyzer.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `register-map.yml` | spec-analyzer | yes |
| Interface protocol | interface-list.yml | yes |

## Outputs (into `rtl/verification/env/regmodel/`)

| File | Description |
|------|-------------|
| `<module>_reg_block.sv` | Top-level register block |
| `reg/<reg_name>_reg.sv` | Individual register class per register |

## Generated Register Model

```systemverilog
// Register Field
class ctrl_en_field extends uvm_reg_field;
  `<uvm_object_utils(ctrl_en_field)

  function new(string name = "ctrl_en_field");
    super.new(name);
  endfunction
endclass

// Register
class ctrl_reg extends uvm_reg;
  `<uvm_object_utils(ctrl_reg)

  rand uvm_reg_field tx_en;
  rand uvm_reg_field rx_en;
  rand uvm_reg_field mode;
  rand uvm_reg_field reserved;

  function new(string name = "ctrl_reg");
    super.new(name, 32, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    tx_en     = ctrl_en_field::type_id::create("tx_en", , get_full_name());
    tx_en.configure(this, 1, 0, "RW", 1, 1'b0, 1, 1, 1);

    rx_en     = ctrl_en_field::type_id::create("rx_en", , get_full_name());
    rx_en.configure(this, 1, 1, "RW", 1, 1'b0, 1, 1, 1);

    mode      = uvm_reg_field::type_id::create("mode", , get_full_name());
    mode.configure(this, 2, 2, "RW", 0, 2'b00, 1, 1, 1);

    reserved  = uvm_reg_field::type_id::create("reserved", , get_full_name());
    reserved.configure(this, 28, 4, "RO", 0, 28'h0, 1, 0, 0);
  endfunction
endclass

// Register Block
class uart_reg_block extends uvm_reg_block;
  `<uvm_object_utils(uart_reg_block)

  rand ctrl_reg   ctrl;
  rand status_reg status;
  rand data_reg   tx_data;
  rand data_reg   rx_data;

  function new(string name = "uart_reg_block");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    // Create registers
    ctrl   = ctrl_reg::type_id::create("ctrl", , get_full_name());
    ctrl.configure(this, null, "");
    ctrl.build();
    ctrl.add_hdl_path_slice("ctrl_reg", 0, 32);

    status = status_reg::type_id::create("status", , get_full_name());
    status.configure(this, null, "");
    status.build();
    status.add_hdl_path_slice("status_reg", 32'h04, 32);

    // Default map
    default_map = create_map("default_map", 0, 4, UVM_LITTLE_ENDIAN, 1);
    default_map.add_reg(ctrl,   32'h00, "RW");
    default_map.add_reg(status, 32'h04, "RO");
  endfunction
endclass
```

## Adapter Generation

Also generates a protocol adapter for the register model:

```systemverilog
class apb_reg_adapter extends uvm_reg_adapter;
  `<uvm_object_utils(apb_reg_adapter)

  function uvm_sequence_item reg2bus(const ref uvm_reg_bus_op rw);
    apb_txn txn = apb_txn::type_id::create("txn");
    txn.addr = rw.addr;
    txn.data = rw.data;
    txn.write = (rw.kind == UVM_WRITE);
    return txn;
  endfunction

  function void bus2reg(uvm_sequence_item bus_item, ref uvm_reg_bus_op rw);
    apb_txn txn;
    if (!$cast(txn, bus_item)) return;
    rw.kind = txn.write ? UVM_WRITE : UVM_READ;
    rw.addr = txn.addr;
    rw.data = txn.data;
    rw.status = txn.pslverr ? UVM_NOT_OK : UVM_IS_OK;
  endfunction
endclass
```
