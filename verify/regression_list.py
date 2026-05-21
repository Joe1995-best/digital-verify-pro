"""回归清单 — tb_gen 自动生成 + 手动追加

auto_cases:  tb_gen 每次运行时覆盖刷新（从 test_plan.yml 重新生成）
manual_cases: 不依赖 tb_gen，手动增删，tb_gen 不覆盖
ALL_CASES:   auto + manual 合并，sim-runner 只读这个
"""
import os

# --- 自动生成部分（tb_gen 覆盖） ---
auto_cases = [
    "i2c_tp_0001",
    "i2c_tp_0002",
    "i2c_tp_0003",
    "i2c_tp_0004",
    "i2c_tp_0005",
    "i2c_tp_0006",
    "i2c_tp_0007",
    "i2c_tp_0008",
    "i2c_tp_0009",
    "i2c_tp_0010",
    "i2c_tp_0011",
    "i2c_tp_0012",
    "i2c_tp_0013",
    "i2c_tp_0014",
    "i2c_tp_0015",
    "i2c_tp_0016",
    "i2c_tp_0017",
    "i2c_tp_0018",
    "i2c_tp_0019",
    "i2c_tp_0020",
    "i2c_tp_0021",
    "i2c_tp_0022",
    "i2c_tp_0023",
    "i2c_tp_0024",
    "i2c_tp_0025",
    "i2c_tp_0026",
    "i2c_tp_0027",
    "i2c_tp_0028",
    "i2c_tp_0029",
    "i2c_tp_0030",
    "i2c_tp_0031",
    "i2c_tp_0032",
    "i2c_tp_0033",
    "i2c_tp_0034",
    "i2c_tp_0035",
    "i2c_tp_0036",
    "i2c_tp_0037",
    "i2c_tp_0038",
    "i2c_tp_0039",
    "i2c_tp_0040",
    "i2c_tp_0041",
    "i2c_tp_0042",
    "i2c_tp_0043",
    "i2c_tp_0044",
    "i2c_tp_0045",
    "i2c_tp_0046",
    "i2c_tp_0047",
    "i2c_tp_0048",
    "i2c_tp_0049",
    "i2c_tp_0050",
    "i2c_tp_0051",
    "i2c_tp_0052",
    "i2c_tp_0053",
    "i2c_tp_0054",
    "i2c_tp_0055",
    "i2c_tp_0056",
    "i2c_tp_0057",
    "i2c_tp_0058",
    "i2c_tp_0059",
    "i2c_tp_0060",
    "i2c_tp_0061",
    "i2c_tp_0062",
    "i2c_tp_0063",
    "i2c_tp_0064",
    "i2c_tp_0065",
    "i2c_tp_0066",
    "i2c_tp_0067",
    "i2c_tp_0068",
    "i2c_tp_0069",
    "i2c_tp_0070",
    "i2c_tp_0071",
    "i2c_tp_0072",
    "i2c_tp_0073",
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
