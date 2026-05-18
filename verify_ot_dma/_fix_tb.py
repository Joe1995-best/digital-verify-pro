import re
with open(r"C:\Users\Administrator\.openclaw\workspace\digital-verify-pro\verify_ot_dma\tb_dma_core.v", "r", encoding="utf-8") as f:
    content = f.read()

# Replace all t_fail(name, $sformatf(...)) -> t_fail(name, plain_string)
def replace_sformatf(m):
    name = m.group(1)
    fmt_str = m.group(2)
    # Extract just the description part from the format string
    # $sformatf("got %h", rd) -> should become something else
    # Just replace with a simple message
    return f't_fail({name}, "FAIL")'

content = re.sub(
    r't_fail\(\s*(\w+)\s*,\s*\$sformatf\([^)]+\)\s*\)',
    replace_sformatf,
    content
)

with open(r"C:\Users\Administrator\.openclaw\workspace\digital-verify-pro\verify_ot_dma\tb_dma_core.v", "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed {content.count('FAIL')} occurrences")
