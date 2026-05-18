"""Coverage Closure Pipeline — Gap → Targeted Test Generation

Reads coverage gaps from VCD analysis and generates targeted test scenarios
to close the gaps.

Usage:
    python pipeline/run_coverage_closure.py --spec i2c_spec.yml --vcd output_i2c/tb_i2c_full.vcd
"""
import os, sys, argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, 'pipeline'))

from template_engine import build_spec_data


def analyze_gaps(coverage_result, spec_data):
    """Match coverage gap signals to spec registers/fields.
    Returns list of gap_actions.
    """
    gaps = []
    stats = coverage_result.to_dict() if hasattr(coverage_result, 'to_dict') else {}
    gap_list = stats.get('gaps', [])

    # Known register prefixes for gap matching
    known_regs = {r['name'].lower() for r in spec_data.get('registers', [])}

    for g in gap_list:
        sig = g.get('signal', '')
        sev = g.get('severity', 5)
        
        # Skip env/testbench signals
        if any(x in sig.lower() for x in ['env_', 'tb_', 'assert', 'pullup',
                                            'gpio', 'raw_irq', 'irq_clear', 'pready']):
            continue
        
        # Match signal to register/field
        matched = False
        for reg_name in known_regs:
            if reg_name in sig.lower():
                gaps.append({
                    'signal': sig,
                    'severity': sev,
                    'register': reg_name,
                    'gap_type': 'toggle_cross' if 'half' in g.get('type', '') else 'missing_toggle'
                })
                matched = True
                break
        
        if not matched:
            # FSM signal
            if '_fsm_' in sig or '_q$' in sig or '_d$' in sig:
                gaps.append({
                    'signal': sig,
                    'severity': sev,
                    'register': 'fsm',
                    'gap_type': 'fsm_coverage'
                })

    return gaps


def generate_targeted_tests(gaps, spec_data, out_dir):
    """Generate SV test sequences for coverage gaps."""
    from run_test_generator import generate_test_sequence

    regs = {r['name'].lower(): r for r in spec_data.get('registers', [])}
    produced = []

    for gap in gaps:
        reg_name = gap.get('register', '')
        if reg_name == 'fsm':
            continue  # FSM gaps need different treatment
        
        reg = regs.get(reg_name)
        if not reg:
            continue
        
        # Determine what test to generate based on gap type and field access
        fields = reg.get('fields', [])
        ro_fields = [f for f in fields if f.get('access', '') == 'ro']
        rw_fields = [f for f in fields if f.get('access', '') == 'rw']
        
        test_name = f'{reg_name}_cov_close_seq'
        test_path = os.path.join(out_dir, test_name)
        
        if ro_fields:
            # RO register: test all-RO write-ignored + read
            seq = f"""// Auto-generated coverage closure test for {reg_name}
class {spec_data['module_name']}_{test_name} extends uvm_sequence #(apb_txn);
  `uvm_object_utils({spec_data['module_name']}_{test_name})
  
  function new(string name = "{test_name}");
    super.new(name);
  endfunction

  task body();
    apb_txn txn;
    `uvm_info(get_type_name(), "Starting coverage closure test", UVM_LOW)
    
    // Write + read {reg_name} to exercise all bits
    txn = apb_txn::type_id::create("txn");
    txn.addr = {reg.get('offset', '0')};
    txn.write = 1;
    txn.data = 32'hFFFFFFFF;
    start_item(txn); finish_item(txn);
    
    txn.write = 0;
    start_item(txn); finish_item(txn);
    `uvm_info(get_type_name(), $sformatf("Read %s = %h", "{reg_name}", txn.data), UVM_LOW)
  endtask
endclass
"""
            with open(test_path + '.sv', 'w', encoding='utf-8') as f:
                f.write(seq)
            produced.append(test_name)
    
    return produced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--vcd', required=True)
    ap.add_argument('--outdir', default='output')
    args = ap.parse_args()

    spec_data = build_spec_data(args.spec)
    module = spec_data['module_name']
    out_dir = os.path.join(BASE, args.outdir, 'coverage_closure')
    os.makedirs(out_dir, exist_ok=True)

    # Run coverage
    from engines.coverage_engine import CoverageEngine
    engine = CoverageEngine()
    result = engine.analyze_vcd(args.vcd)

    # Analyze gaps
    gaps = analyze_gaps(result, spec_data)

    print(f'Coverage: {result.toggle_coverage_pct:.1f}% ({result.full_toggle_signals}/{result.total_signals})')
    print(f'Stuck signals: {result.stuck_signals}')
    print(f'Analyzed gaps: {len(gaps)}')

    high_prio = [g for g in gaps if g['severity'] >= 4]
    print(f'High priority gaps: {len(high_prio)}')
    for g in high_prio:
        print(f'  [{g["severity"]}] {g["register"]:20s} {g["signal"]}')

    # Generate targeted tests
    tests = generate_targeted_tests(gaps, spec_data, out_dir)
    print(f'Generated {len(tests)} closure test sequences')

    # Save gap analysis
    import json
    with open(os.path.join(out_dir, 'gap_analysis.json'), 'w', encoding='utf-8') as f:
        json.dump(gaps, f, indent=2, ensure_ascii=False)

    print(f'Saved to {out_dir}/')


if __name__ == '__main__':
    main()
