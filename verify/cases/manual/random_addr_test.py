"""I2C 随机地址校验测试 — 手动添加"""
NAME        = "random_addr_test"
BASE_SEQ    = "i2c_base_seq"
PRIORITY    = "p1"           # p0:必跑 | p1:回归 | p2:全量
STAGE       = "v3_signoff"
DESCRIPTION = "I2C 随机地址读写校验，覆盖地址碰撞场景"
PLUSARGS    = ["+UVM_TESTNAME=random_addr_test", "+I2C_RAND_ADDR=1", "+I2C_LOOP=1000"]
FEATURE_ID  = "MANUAL_RAND_ADDR"
