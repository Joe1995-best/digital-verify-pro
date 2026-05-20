"""I2C master 连续多字节 write 压力测试"""
NAME        = "i2c_write_stress"
BASE_SEQ    = "i2c_base_seq"
PRIORITY    = "p1"
STAGE       = "v3_signoff"
DESCRIPTION = "I2C 256 字节连续 write (fast speed)"
PLUSARGS    = ["+UVM_TESTNAME=i2c_write_test", "+I2C_BYTES=256", "+I2C_SPEED=1"]
FEATURE_ID  = "I2C_WRITE_016"
