"""Parse Verilator coverage annotations and generate report."""
import os, glob

def parse_cov(dirname, label):
    files = {}
    for f in glob.glob(os.path.join(dirname, '*.sv')):
        with open(f, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
        total = 0; covered = 0; missed = 0; toggle = 0
        for l in lines:
            # Verilator format: %000001 = missed, %000101 = covered, ~000094 = toggle
            l = l.rstrip('\n')
            if len(l) < 7:
                continue
            prefix = l[:7]
            total += 1
            if prefix.startswith('%'):
                try:
                    cnt = int(prefix[1:7])
                    if cnt > 0:
                        covered += 1
                    else:
                        missed += 1
                except:
                    pass
            elif prefix.startswith('~'):
                toggle += 1
                covered += 1
            elif prefix.startswith('  '):
                # Regular line with hit count
                stripped = l.strip()
                if stripped.startswith(('[', '//', '`')) or len(stripped) == 0:
                    pass
                else:
                    try:
                        cnt = int(l[:6])
                        if cnt > 0:
                            covered += 1
                    except:
                        pass
        name = os.path.basename(f)
        files[name] = {'total': total, 'covered': covered, 'missed': missed, 'toggle': toggle}
    return files

print("=" * 55)
print("  VERILATOR CODE COVERAGE REPORT")
print("=" * 55)

for label, covdir in [("DMA (66 tests)", "dma_cov_ann"), ("AES (108 tests)", "aes_cov_ann")]:
    if not os.path.exists(covdir):
        print(f"\n{label} - NO DATA")
        continue
    files = parse_cov(covdir, label)
    total_lines = sum(f['total'] for f in files.values())
    total_cov = sum(f['covered'] for f in files.values())
    total_miss = sum(f['missed'] for f in files.values())
    total_pct = total_cov * 100 / total_lines if total_lines else 0

    print(f"\n{label}")
    print(f"  {'File':<25s} {'Total':>5s} {'Cov':>5s} {'Miss':>5s} {'%Cov':>5s} {'Toggle':>6s}")
    print(f"  {'-'*25} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*6}")
    for name in sorted(files.keys()):
        f = files[name]
        pct = f['covered'] * 100 / f['total'] if f['total'] else 0
        print(f"  {name:<25s} {f['total']:5d} {f['covered']:5d} {f['missed']:5d} {pct:4.0f}%  {f['toggle']:5d}")
    print(f"  {'-'*25} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*6}")
    print(f"  {'TOTAL':<25s} {total_lines:5d} {total_cov:5d} {total_miss:5d} {total_pct:3.0f}%  ")

# Check toggle coverage from design files (RTL only)
print("\n" + "=" * 55)
print("  TOGGLE COVERAGE (RTL only)")
print("=" * 55)
for label, covdir in [("DMA (66 tests)", "dma_cov_ann"), ("AES (108 tests)", "aes_cov_ann")]:
    if not os.path.exists(covdir):
        continue
    files = parse_cov(covdir, label)
    rtl_toggle = sum(f['toggle'] for name, f in files.items() if 'tb' not in name and 'testbench' not in name)
    rtl_lines = sum(f['total'] for name, f in files.items() if 'tb' not in name and 'testbench' not in name)
    rtl_cov = sum(f['covered'] for name, f in files.items() if 'tb' not in name and 'testbench' not in name)
    rtl_pct = rtl_cov * 100 / rtl_lines if rtl_lines else 0
    print(f"  {label}:")
    print(f"    RTL lines:    {rtl_lines}")
    print(f"    RTL covered:  {rtl_cov} ({rtl_pct:.0f}%)")
    print(f"    RTL toggle:   {rtl_toggle}")

# Compare with functional coverage
print("\n" + "=" * 55)
print("  FUNCTIONAL COVERAGE (estimated from test types)")
print("=" * 55)

def func_cov(module, total_tests, pass_count, fail_count, test_breakdown):
    # Functional coverage = tests that actually verified a functional behavior
    print(f"  {module}:")
    for cat, val, total in test_breakdown:
        pct = val * 100 / total if total else 0
        print(f"    {cat:<20s}: {val}/{total} ({pct:.0f}%)")
    print(f"    {'Total PASS':<20s}: {pass_count}/{total_tests} ({pass_count*100/total_tests:.0f}%)")
    print(f"    {'Estimated func cov':<20s}: {pass_count}/{total_tests} ({pass_count*100/total_tests:.0f}%)")

print()
func_cov("DMA", 66, 41, 25, [
    ("User scenarios", 9, 9),
    ("RW tests", 11, 16),
    ("RO tests", 2, 4),
    ("Reset tests", 8, 20),
    ("Bit-bash", 10, 14),
    ("Stress", 2, 2),
    ("Back-to-back", 1, 1),
    ("PSLVERR", 1, 1),
])

print()
func_cov("AES", 108, 90, 18, [
    ("User scenarios", 9, 9),
    ("RW tests", 18, 28),
    ("RO tests", 6, 6),
    ("Reset tests", 34, 34),
    ("Bit-bash", 28, 28),
    ("Stress", 2, 2),
    ("Back-to-back", 1, 1),
])
