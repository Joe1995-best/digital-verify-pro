"""CTRL 寄存器读写测试"""
NAME        = "ctrl_rw"
BASE_SEQ    = "apb_rw_seq"
PRIORITY    = "p0"       # p0:必跑 | p1:回归 | p2:全量
STAGE       = "v1_smoke"
DESCRIPTION = "CTRL 寄存器 enable 域写 1 读回 1"
PLUSARGS    = ["+UVM_TESTNAME=ctrl_rw_test", "+CTRL_ENABLE_INIT=1"]
FEATURE_ID  = "REG_RW_001"
