"""I2C master 单字节 write 测试"""
NAME        = "i2c_write_1"
BASE_SEQ    = "i2c_base_seq"
PRIORITY    = "p0"
STAGE       = "v2_stress"
DESCRIPTION = "I2C 单字节 write (standard speed)"
PLUSARGS    = ["+UVM_TESTNAME=i2c_write_test", "+I2C_BYTES=1", "+I2C_SPEED=0"]
FEATURE_ID  = "I2C_WRITE_001"
