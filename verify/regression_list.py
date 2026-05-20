"""回归清单 — tb_gen 自动生成 + 手动追加

auto_cases:  tb_gen 每次运行时覆盖刷新（从 test_plan.yml 重新生成）
manual_cases: 不依赖 tb_gen，手动增删，tb_gen 不覆盖
ALL_CASES:   auto + manual 合并，sim-runner 只读这个
"""
import os

# --- 自动生成部分（tb_gen 覆盖） ---
auto_cases = [
    "i2c_reg_rw_001",
    "i2c_reg_rw_002",
    "i2c_reg_rw_003",
    "i2c_i2c_write_001",
    "i2c_i2c_write_016",
    "i2c_i2c_write_256",
    "i2c_i2c_read_001",
    "i2c_i2c_read_016",
    "i2c_i2c_speed_001",
    "i2c_i2c_arb_001",
    "i2c_i2c_stretch_001",
    "i2c_intr_001",
    "i2c_err_001",
]

# --- 手动追加部分（tb_gen 不覆盖） ---
manual_cases = [
    "verify.cases.manual.long_write_stress",
    "verify.cases.manual.random_addr_test",  # ← 加一行
]

# 合并
ALL_CASES = auto_cases + manual_cases

# disabled 列表（临时跳过，不用删）
DISABLED = []


def active_cases():
    return [c for c in ALL_CASES
            if c not in DISABLED and not c.startswith("#")]


def case_names():
    import importlib
    names = []
    for path in active_cases():
        try:
            mod = importlib.import_module(path)
            names.append(mod.NAME)
        except (ImportError, AttributeError):
            names.append(path.split(".")[-1])
    return names
