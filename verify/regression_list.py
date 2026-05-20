"""回归清单 — tb_gen 自动生成 + 手动追加

auto_cases:  tb_gen 每次运行时覆盖刷新（从 test_plan.yml 重新生成）
manual_cases: 不依赖 tb_gen，手动增删，tb_gen 不覆盖
ALL_CASES:   auto + manual 合并，sim-runner 只读这个
"""
import os

# --- 自动生成部分（tb_gen 覆盖） ---
auto_cases = [
    "uart_tp_0001",
    "uart_tp_0002",
    "uart_tp_0003",
    "uart_tp_0004",
    "uart_tp_0005",
    "uart_tp_0006",
    "uart_tp_0007",
    "uart_tp_0008",
    "uart_tp_0009",
    "uart_tp_0010",
    "uart_tp_0011",
    "uart_tp_0012",
    "uart_tp_0013",
    "uart_tp_0014",
    "uart_tp_0015",
    "uart_tp_0016",
    "uart_tp_0017",
    "uart_tp_0018",
    "uart_tp_0019",
    "uart_tp_0020",
    "uart_tp_0021",
    "uart_tp_0022",
    "uart_tp_0023",
    "uart_tp_0024",
    "uart_tp_0025",
    "uart_tp_0026",
    "uart_tp_0027",
    "uart_tp_0028",
    "uart_tp_0029",
    "uart_tp_0030",
    "uart_tp_0031",
    "uart_tp_0032",
    "uart_tp_0033",
    "uart_tp_0034",
    "uart_tp_0035",
    "uart_tp_0036",
    "uart_tp_0037",
    "uart_tp_0038",
    "uart_tp_0039",
    "uart_tp_0040",
    "uart_tp_0041",
    "uart_tp_0042",
    "uart_tp_0043",
    "uart_tp_0044",
    "uart_tp_0045",
    "uart_tp_0046",
    "uart_tp_0047",
    "uart_tp_0048",
    "uart_tp_0049",
    "uart_tp_0050",
    "uart_tp_0051",
    "uart_tp_0052",
    "uart_tp_0053",
    "uart_tp_0054",
    "uart_tp_0055",
    "uart_tp_0056",
    "uart_tp_0057",
    "uart_tp_0058",
    "uart_tp_0059",
    "uart_tp_0060",
    "uart_tp_0061",
    "uart_tp_0062",
    "uart_tp_0063",
    "uart_tp_0064",
    "uart_tp_0065",
    "uart_tp_0066",
    "uart_tp_0067",
    "uart_tp_0068",
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
