# digital-verify-pro — 验证示例

## I2C 完整验证

`examples/i2c/` 包含 I2C 主控制器的完整验证环境：

| 文件 | 说明 |
|---|---|
| `i2c_slave_model.sv` | I2C 从机仿真模型 (7-bit地址, ACK/NACK, 读写) |
| `tb_i2c_full.sv` | 完整验证 TB (reg测试 + I2C读写 + 多速度 + 中断) |
| `tb_i2c_full.vcd` | 仿真 VCD (127信号, 7064时间戳, 70ms仿真) |

### 运行方法

```bash
# 1. 先跑 pipeline 生成 RTL
python pro_verify.py --pipeline i2c_spec.yml --outdir ./output_i2c

# 2. 编译 + 仿真
cd output_i2c
iverilog -g2012 -s tb_i2c_full -o sim_full ^
  .\rtl\rtl\*.sv ^
  ..\examples\i2c\i2c_slave_model.sv ^
  ..\examples\i2c\tb_i2c_full.sv
vvp sim_full

# 3. 收覆盖率
python -c "from engines.coverage_engine import CoverageEngine; ..."
```

### I2C 测试项

1. 寄存器复位值 / RW 测试 / PSLVERR
2. I2C 写传输 (START + addr(W) + data + STOP)
3. I2C 读传输 (START + addr(R) + NACK + STOP)
4. 多速度切换 (100kHz → 400kHz → 1MHz)
5. TX 中断生成

### I2C FSM 覆盖率

- 总信号: 127, Full toggle: 82/127, Stuck: 5
- Toggle: **88.9%**
- 缺口: rx_data_reg (读返回0, 需修slave读模型), arb_intr (仲裁丢失未测)
