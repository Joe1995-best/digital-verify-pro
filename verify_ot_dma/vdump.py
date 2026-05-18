#!/usr/bin/env python3
"""
vdump - VCD waveform CLI analysis tool
Inspired by xwave (github.com/BLANK2077/xwave), for Icarus Verilog VCD files.

Commands:
  signals              List all signals
  value <sig> <ns>     Query signal value
  summary              VCD file summary
  diff <sig1> [sig2..] Find first time signals differ
  find <sig> <val>     Find all times signal equals a value
  search <sig> <range> Search signal for value range
  edge <sig>           Find signal edges
  sample <clk> <sig>   Sample signal at clock edges
  pulse <sig> <ns>     Find pulses (transitions within a window)
  view <sig1> [sig2..] View signal values as table over time
  event <cfg.json>     Transaction extraction (valid/ready handshake)
"""

import sys
import os
import json
import argparse
import io
from vcd.reader import TokenKind, tokenize
from vcd.common import TimescaleUnit

TS_TO_NS = {
    TimescaleUnit.second: 10**9,
    TimescaleUnit.millisecond: 10**6,
    TimescaleUnit.microsecond: 10**3,
    TimescaleUnit.nanosecond: 1,
    TimescaleUnit.picosecond: 10**-3,
    TimescaleUnit.femtosecond: 10**-6,
}


# ── VCD Parser ──────────────────────────────────────────────────

def parse_vcd(vcd_path):
    """Parse VCD file, return (signals, value_history, ts_info)."""
    if not os.path.exists(vcd_path):
        print(f"Error: VCD file not found: {vcd_path}", file=sys.stderr)
        sys.exit(1)

    with open(vcd_path, 'rb') as f:
        raw = f.read()
    
    tokens = tokenize(io.BytesIO(raw))
    
    signals = {}
    hierarchy = []
    ts_mag = 1
    ts_unit = TimescaleUnit.picosecond
    time_to_ns = 0.001
    
    history = {}
    
    for token in tokens:
        kind = token.kind
        
        if kind == TokenKind.TIMESCALE:
            ts = token.data
            ts_mag = ts.magnitude
            ts_unit = ts.unit
            mul = ts_mag.value if hasattr(ts_mag, 'value') else ts_mag
            time_to_ns = mul * TS_TO_NS.get(ts_unit, 0.001)
            
        elif kind == TokenKind.SCOPE:
            hierarchy.append(token.data.ident)
            
        elif kind == TokenKind.UPSCOPE:
            if hierarchy:
                hierarchy.pop()
                
        elif kind == TokenKind.VAR:
            v = token.data
            hier_str = '.'.join(hierarchy)
            name = v.reference
            if v.bit_index is not None:
                if isinstance(v.bit_index, int):
                    name = f"{name}[{v.bit_index}]"
                else:
                    name = f"{name}[{v.bit_index[0]}:{v.bit_index[1]}]"
            fullname = f"{hier_str}.{name}" if hier_str else name
            signals[v.id_code] = {
                'name': name,
                'hier': hier_str,
                'fullname': fullname,
                'size': v.size,
                'type': str(v.type_.value) if hasattr(v.type_, 'value') else str(v.type_),
            }
            history[v.id_code] = []
            
        elif kind == TokenKind.CHANGE_TIME:
            current_time_raw = token.data
            
        elif kind == TokenKind.CHANGE_SCALAR:
            c = token.data
            t_ns = current_time_raw * time_to_ns
            if c.id_code in history:
                history[c.id_code].append((t_ns, c.value))
                
        elif kind == TokenKind.CHANGE_VECTOR:
            c = token.data
            t_ns = current_time_raw * time_to_ns
            if c.id_code in history:
                history[c.id_code].append((t_ns, c.value))
    
    return signals, history, (ts_mag, ts_unit)


# ── Value helpers ───────────────────────────────────────────────

def val_int(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        s = val.strip()
        if any(c in s for c in 'xXzZ'):
            return None
        if all(c in '01' for c in s):
            return int(s, 2)
        return None
    return None


def fmt_val(val, width, fmt='h'):
    if val is None:
        return '?' * width
    if isinstance(val, str) and any(c in s for c in 'xXzZ' for s in [val]):
        return val
    if isinstance(val, str) and all(c in '01' for c in val):
        iv = int(val, 2)
    elif isinstance(val, int):
        iv = val
    else:
        return str(val)
    if fmt == 'b':
        return format(iv, f'0{width}b')
    elif fmt == 'd':
        return str(iv)
    else:
        return format(iv, f'0{max(1, (width + 3) // 4)}x')


def fmt_val_short(val, width):
    if val is None:
        return '?' * min(width, 4)
    if isinstance(val, str):
        if all(c in '01' for c in val):
            iv = int(val, 2)
        else:
            return val[:8]
    elif isinstance(val, int):
        iv = val
    else:
        return '?'
    return format(iv, f'0{max(1, (width + 3) // 4)}x')


def parse_val(target_str, width=32):
    """Parse a value string (0xHEX, 0bBIN, or decimal) to int."""
    if target_str.startswith('0x'):
        return int(target_str, 16)
    elif target_str.startswith('0b'):
        return int(target_str[2:], 2)
    elif target_str.startswith("'"):
        # Verilog-style: 'hFF, 'd10, 'b1010
        base = target_str[1] if len(target_str) > 1 else 'd'
        num = target_str[2:] if base in 'hdb' else target_str[1:]
        base_map = {'h': 16, 'd': 10, 'b': 2}
        return int(num, base_map.get(base, 10))
    else:
        try:
            return int(target_str, 10)
        except ValueError:
            if all(c in '01' for c in target_str):
                return int(target_str, 2)
            raise


# ── Signal resolution (improved) ────────────────────────────────

def resolve_signal(target, signals):
    """Find signal by name. Priority: exact > suffix > component match."""
    # 1. Exact fullname or leaf name
    direct = [(k, v) for k, v in signals.items()
              if target == v['fullname'] or target == v['name']]
    if direct:
        return direct[0]
    # 2. Try without bit-index brackets
    direct2 = [(k, v) for k, v in signals.items()
               if target == _strip_brackets(v['fullname'])
               or target == _strip_brackets(v['name'])]
    if direct2:
        return direct2[0]
    # 3. Hierarchy suffix
    suffix = [(k, v) for k, v in signals.items()
              if v['fullname'].endswith('.' + target)]
    if suffix:
        return suffix[0]
    # 4. Component match (dot-separated, no substring on hierarchy names)
    for k, v in signals.items():
        parts = [p.split('[')[0] for p in v['fullname'].split('.')]
        if target in parts:
            return (k, v)
    return None


def _strip_brackets(name):
    idx = name.find('[')
    return name[:idx] if idx >= 0 else name


def resolve_signals(targets, signals):
    resolved = []
    for t in targets:
        m = resolve_signal(t, signals)
        if m is None:
            print(f"Warning: Signal '{t}' not found.", file=sys.stderr)
        else:
            resolved.append(m)
    return resolved


# ── Command: signals ─────────────────────────────────────────────

def cmd_signals(vcd_path, args):
    signals, _, ts = parse_vcd(vcd_path)
    mag = ts[0].value if hasattr(ts[0], 'value') else ts[0]
    unit = ts[1].value if hasattr(ts[1], 'value') else ts[1]
    print(f"Signals in {os.path.basename(vcd_path)}  (timescale: {mag} {unit})")
    print(f"{'ID':>4} {'Name':<55} {'Bits':>5} {'Type':<10}")
    print("-" * 80)
    for id_code, info in sorted(signals.items(), key=lambda x: x[1]['fullname']):
        print(f"{id_code:>4} {info['fullname']:<55} {info['size']:>5} {info['type']:<10}")
    print(f"\nTotal: {len(signals)} signals")


# ── Command: value ───────────────────────────────────────────────

def cmd_value(vcd_path, args):
    signals, history, _ = parse_vcd(vcd_path)
    m = resolve_signal(args.signal, signals)
    if not m:
        print(f"Error: '{args.signal}' not found.", file=sys.stderr)
        sys.exit(1)
    id_code, info = m
    hist = history.get(id_code, [])
    fmt = args.format
    
    if args.all:
        print(f"All transitions for {info['fullname']}:")
        print(f"{'Time (ns)':<14} {'Value':<30}")
        print("-" * 50)
        last = None
        for t, val in hist:
            if val != last:
                print(f"{t:<14.1f} {fmt_val(val, info['size'], fmt):<30}")
                last = val
        print(f"\nTotal transitions: {len(hist)}")
        return
    
    t_target = args.time
    found_val, found_t = None, 0
    for t, val in hist:
        if t <= t_target:
            found_val, found_t = val, t
        else:
            break
    
    if found_val is not None:
        print(f"Signal: {info['fullname']}  ({info['size']} bits)")
        print(f"Time:   {t_target} ns  (last change at {found_t:.1f} ns)")
        print(f"Value:  {fmt_val(found_val, info['size'], fmt)}")
        if args.json:
            print(json.dumps({'signal': info['fullname'], 'time_ns': t_target,
                              'last_change_ns': found_t,
                              'value': fmt_val(found_val, info['size'], fmt),
                              'format': fmt, 'width': info['size']}))
    else:
        print(f"No data for {info['fullname']} at {t_target} ns")


# ── Command: summary ─────────────────────────────────────────────

def cmd_summary(vcd_path, args):
    signals, history, ts = parse_vcd(vcd_path)
    mag = ts[0].value if hasattr(ts[0], 'value') else ts[0]
    unit = ts[1].value if hasattr(ts[1], 'value') else ts[1]
    min_t, max_t = float('inf'), float('-inf')
    total_trans = 0
    sig_counts = {}
    for id_code in signals:
        hist = history.get(id_code, [])
        n = len(hist)
        total_trans += n
        sig_counts[id_code] = n
        if hist:
            if hist[0][0] < min_t: min_t = hist[0][0]
            if hist[-1][0] > max_t: max_t = hist[-1][0]
    print(f"VCD Summary: {os.path.basename(vcd_path)}")
    print(f"{'Timescale:':<30} {mag} {unit}")
    print(f"{'Total signals:':<30} {len(signals)}")
    print(f"{'Total transitions:':<30} {total_trans}")
    if min_t != float('inf'):
        print(f"{'Time range:':<30} {min_t:.1f} ns ~ {max_t:.1f} ns")
        print(f"{'Duration:':<30} {max_t - min_t:.1f} ns")
    print()
    if sig_counts:
        top_n = sorted(sig_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        print("Top 10 most active signals:")
        print(f"{'Signal':<55} {'Transitions':<12}")
        print("-" * 70)
        for id_code, count in top_n:
            if id_code in signals:
                print(f"{signals[id_code]['fullname']:<55} {count:<12}")


# ── Command: diff ────────────────────────────────────────────────

def cmd_diff(vcd_path, args):
    signals, history, _ = parse_vcd(vcd_path)
    resolved = resolve_signals(args.signals, signals)
    if len(resolved) < 2:
        print("Error: Need at least 2 valid signals.", file=sys.stderr)
        sys.exit(1)
    all_changes = []
    for id_code, _ in resolved:
        for t, val in history.get(id_code, []):
            all_changes.append((t, id_code, val))
    all_changes.sort(key=lambda x: x[0])
    
    vals = {}
    start = args.begin or 0
    end = args.end or float('inf')
    for t, id_code, val in all_changes:
        if t < start: continue
        if t > end: break
        vals[id_code] = val
        if not all(rid in vals for rid, _ in resolved):
            continue
        ref_id = resolved[0][0]
        ref_v = vals[ref_id]
        diffing = [(info, vals[rid]) for rid, info in resolved[1:] if vals[rid] != ref_v]
        if diffing:
            print(f"\n=== First difference at {t:.1f} ns ===")
            print(f"{'Signal':<55} {'Value'}")
            print("-" * 70)
            print(f"{resolved[0][1]['fullname']:<55} {fmt_val(ref_v, resolved[0][1]['size'])}")
            for info, dv in diffing:
                print(f"{info['fullname']:<55} {fmt_val(dv, info['size'])}")
            print()
            return
    print("No differences found.")


# ── Command: find ────────────────────────────────────────────────

def cmd_find(vcd_path, args):
    """Find all times when a signal equals a specific value."""
    signals, history, _ = parse_vcd(vcd_path)
    m = resolve_signal(args.signal, signals)
    if not m:
        print(f"Error: '{args.signal}' not found.", file=sys.stderr)
        sys.exit(1)
    id_code, info = m
    hist = history.get(id_code, [])
    try:
        target_int = parse_val(args.value, info['size'])
    except Exception as e:
        print(f"Error: Can't parse value '{args.value}': {e}", file=sys.stderr)
        sys.exit(1)
    
    start = args.begin or 0
    end = args.end or float('inf')
    
    results = []
    last_diff = None
    for t, val in hist:
        if t < start: continue
        if t > end: break
        v = val_int(val)
        if v is not None:
            this_diff = (v == target_int)
            if this_diff and (this_diff != last_diff):
                results.append((t, v))
            last_diff = this_diff
    
    if args.count:
        print(f"{info['fullname']} == 0x{target_int:x}: {len(results)} time(s)")
        return
    
    print(f"Searching: {info['fullname']} == {fmt_val(target_int, info['size'], 'h')}")
    if results:
        print(f"{'#':>4} {'Time (ns)':<14} {'Value':<20}")
        print("-" * 45)
        for i, (t, v) in enumerate(results):
            print(f"{i+1:>4} {t:<14.1f} {fmt_val(v, info['size'], 'h'):<20}")
    print(f"\nTotal matches: {len(results)}")


# ── Command: search (range) ──────────────────────────────────────

def cmd_search(vcd_path, args):
    """Search for signal values in a range [lo, hi]."""
    signals, history, _ = parse_vcd(vcd_path)
    m = resolve_signal(args.signal, signals)
    if not m:
        print(f"Error: '{args.signal}' not found.", file=sys.stderr)
        sys.exit(1)
    id_code, info = m
    hist = history.get(id_code, [])
    
    range_str = args.range
    if '-' in range_str and range_str.count('-') == 1:
        lo = parse_val(range_str.split('-')[0], info['size'])
        hi = parse_val(range_str.split('-')[1], info['size'])
    else:
        lo = hi = parse_val(range_str, info['size'])
    
    results = []
    active = False
    for t, val in hist:
        v = val_int(val)
        if v is not None:
            in_range = (lo <= v <= hi)
            if in_range and not active:
                results.append(('enter', t, v))
            elif not in_range and active:
                results.append(('exit', t, v))
            active = in_range
    
    if args.count:
        entries = [r for r in results if r[0] == 'enter']
        print(f"{info['fullname']} in [{fmt_val(lo, info['size'])}-{fmt_val(hi, info['size'])}]: {len(entries)} occurrence(s)")
        return
    
    print(f"Searching: {info['fullname']} in [{fmt_val(lo, info['size'])} - {fmt_val(hi, info['size'])}]")
    if results:
        print(f"{'Type':>6} {'Time (ns)':<14} {'Value':<20}")
        print("-" * 45)
        for typ, t, v in results:
            tag = "ENTER" if typ == 'enter' else "EXIT "
            print(f"{tag:>6} {t:<14.1f} {fmt_val(v, info['size'], 'h'):<20}")
    
    entries = [r for r in results if r[0] == 'enter']
    print(f"\n{len(entries)} occurrences")
    for i in range(min(len(entries), 10)):
        entry_t = entries[i][1]
        exits = [r for r in results if r[0] == 'exit' and r[1] > entry_t]
        exit_t = exits[i].__getitem__(1) if i < len(exits) else (hist[-1][0] if hist else entry_t)
        dur = exit_t - entry_t
        print(f"  #{i+1}: {entry_t:.1f} ns - {exit_t:.1f} ns  ({dur:.1f} ns)")


# ── Command: edge ────────────────────────────────────────────────

def cmd_edge(vcd_path, args):
    signals, history, _ = parse_vcd(vcd_path)
    m = resolve_signal(args.signal, signals)
    if not m:
        print(f"Error: '{args.signal}' not found.", file=sys.stderr)
        sys.exit(1)
    id_code, info = m
    hist = history.get(id_code, [])
    edge_type = args.type
    start = args.begin or 0
    end = args.end or float('inf')
    
    edges = []
    prev = None
    for t, val in hist:
        if t < start:
            prev = val; continue
        if t > end: break
        v, pv = val_int(val), val_int(prev)
        if prev is not None and v is not None and pv is not None:
            if edge_type in ('rise', 'both') and pv == 0 and v == 1:
                edges.append(('rise', t))
            if edge_type in ('fall', 'both') and pv == 1 and v == 0:
                edges.append(('fall', t))
        prev = val
    
    if args.count:
        rises = sum(1 for e in edges if e[0] == 'rise')
        falls = sum(1 for e in edges if e[0] == 'fall')
        parts = []
        if edge_type in ('rise', 'both'): parts.append(f"rising={rises}")
        if edge_type in ('fall', 'both'): parts.append(f"falling={falls}")
        print(f"{info['fullname']}: {', '.join(parts)}")
        return
    
    print(f"Edges for {info['fullname']} ({edge_type})")
    if edges:
        print(f"{'Time (ns)':<14} {'Edge':<8}")
        print("-" * 30)
        for etype, t in edges:
            print(f"{t:<14.1f} {etype:<8}")
    print(f"\nTotal edges: {len(edges)}")


# ── Command: sample ──────────────────────────────────────────────

def cmd_sample(vcd_path, args):
    signals, history, _ = parse_vcd(vcd_path)
    m_clk = resolve_signal(args.clk, signals)
    if not m_clk:
        print(f"Error: Clock '{args.clk}' not found.", file=sys.stderr)
        sys.exit(1)
    m_sig = resolve_signal(args.signal, signals)
    if not m_sig:
        print(f"Error: Signal '{args.signal}' not found.", file=sys.stderr)
        sys.exit(1)
    
    id_clk, info_clk = m_clk
    id_sig, info_sig = m_sig
    hist_clk = history.get(id_clk, [])
    hist_sig = history.get(id_sig, [])
    edge = args.edge
    start = args.begin or 0
    end = args.end or float('inf')
    
    clk_edges = []
    prev = None
    for t, val in hist_clk:
        if t < start: prev = val; continue
        if t > end: break
        v, pv = val_int(val), val_int(prev)
        if prev is not None and v is not None and pv is not None:
            if edge == 'rise' and pv == 0 and v == 1:
                clk_edges.append(t)
            elif edge == 'fall' and pv == 1 and v == 0:
                clk_edges.append(t)
            elif edge == 'both' and pv != v:
                clk_edges.append(t)
        prev = val
    
    results = []
    for ct in clk_edges:
        sig_val = None
        for t, val in hist_sig:
            if t <= ct:
                sig_val = val
            else:
                break
        results.append((ct, sig_val))
    
    if args.count:
        print(f"Sampled {info_sig['fullname']} @ {info_clk['fullname']} {edge}: {len(results)} samples")
        return
    
    print(f"Sampling: {info_sig['fullname']} @ {info_clk['fullname']} ({edge})")
    if results:
        print(f"{'Cycle':>6} {'Time (ns)':<14} {'Value':<20}")
        print("-" * 45)
        for i, (ct, sv) in enumerate(results):
            print(f"{i+1:>6} {ct:<14.1f} {fmt_val_short(sv, info_sig['size']):<20}")
    print(f"\nTotal samples: {len(results)}")
    
    if args.json and results:
        data = [{'cycle': i+1, 'time_ns': ct,
                 'value': fmt_val_short(sv, info_sig['size'])}
                for i, (ct, sv) in enumerate(results)]
        print(json.dumps(data))


# ── Command: pulse ────────────────────────────────────────────────

def cmd_pulse(vcd_path, args):
    signals, history, _ = parse_vcd(vcd_path)
    m = resolve_signal(args.signal, signals)
    if not m:
        print(f"Error: '{args.signal}' not found.", file=sys.stderr)
        sys.exit(1)
    id_code, info = m
    hist = history.get(id_code, [])
    max_width = args.max_width
    min_width = args.min_width or 0
    polarity = args.polarity
    
    if len(hist) < 3:
        print("Not enough transitions.")
        return
    
    pulses = []
    for i in range(1, len(hist) - 1):
        t0, v0 = hist[i-1]
        t1, v1 = hist[i]
        t2, v2 = hist[i+1]
        t0i, t1i, t2i = val_int(v0), val_int(v1), val_int(v2)
        if t0i is None or t1i is None or t2i is None:
            continue
        width = t2 - t0
        if width > max_width or width < min_width:
            continue
        
        if polarity == 'high' and t0i == 0 and t1i == 1 and t2i == 0:
            pulses.append(('high', t1, width))
        elif polarity == 'low' and t0i == 1 and t1i == 0 and t2i == 1:
            pulses.append(('low', t1, width))
        elif polarity == 'both' and t0i != t1i and t1i != t2i and t0i == t2i:
            typ = 'high' if t1i == 1 else 'low'
            pulses.append((typ, t1, width))
    
    if args.count:
        print(f"{info['fullname']}: {len(pulses)} pulse(s) (width <= {max_width} ns)")
        return
    
    print(f"Pulses on {info['fullname']} (width <= {max_width:.1f} ns, >= {min_width:.1f} ns, {polarity})")
    if pulses:
        print(f"{'#':>4} {'Type':>6} {'Time (ns)':<14} {'Width (ns)':<12}")
        print("-" * 45)
        for i, (typ, t, w) in enumerate(pulses):
            print(f"{i+1:>4} {typ:>6} {t:<14.1f} {w:<12.1f}")
    print(f"\nTotal: {len(pulses)} pulses")


# ── Command: view ────────────────────────────────────────────────

def cmd_view(vcd_path, args):
    signals, history, _ = parse_vcd(vcd_path)
    resolved = resolve_signals(args.signals, signals)
    if not resolved:
        print("Error: No valid signals.", file=sys.stderr)
        sys.exit(1)
    start = args.begin or 0
    end = args.end or float('inf')
    step = args.step or 1.0
    
    print(f"Waveform view: {os.path.basename(vcd_path)}")
    print(f"Range: {start:.1f} - {end if end != float('inf') else 'end'} ns, step: {step} ns")
    print()
    
    header = f"{'Time (ns)':<12}"
    widths = []
    for _, info in resolved:
        w = max(len(info['fullname']), 16)
        widths.append(w)
        header += f" {info['fullname']:<{w}}"
    print(header)
    print("-" * len(header))
    
    t = start
    while t <= (end if end != float('inf') else
               max((history.get(rid, []) or [(0, None)])[-1][0] for rid, _ in resolved)):
        row = f"{t:<12.1f}"
        for (id_code, info), w in zip(resolved, widths):
            val = None
            for ht, hv in history.get(id_code, []):
                if ht <= t:
                    val = hv
                else:
                    break
            row += f" {fmt_val_short(val, info['size']):<{w}}"
        print(row)
        t += step


# ── Command: event ────────────────────────────────────────────────

def cmd_event(vcd_path, args):
    """Extract transactions from valid/ready handshake interfaces."""
    signals, history, _ = parse_vcd(vcd_path)
    
    if not args.config:
        print("Error: Event command requires a JSON config file.", file=sys.stderr)
        sys.exit(1)
    
    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            cfg = json.load(f)
    else:
        try:
            cfg = json.loads(args.config)
        except:
            print(f"Error: Can't parse config '{args.config}'", file=sys.stderr)
            sys.exit(1)
    
    clk = resolve_signal(cfg['clk'], signals)
    vld = resolve_signal(cfg['signals'].get('vld', ''), signals) if 'signals' in cfg else None
    if not vld and 'vld' in cfg:
        vld = resolve_signal(cfg['vld'], signals)
    rdy = resolve_signal(cfg['signals'].get('rdy', ''), signals) if 'signals' in cfg else None
    if not rdy and 'rdy' in cfg:
        rdy = resolve_signal(cfg['rdy'], signals)
    data_sig = resolve_signal(cfg['signals'].get('data', ''), signals) if 'signals' in cfg else None
    if not data_sig and 'data' in cfg:
        data_sig = resolve_signal(cfg['data'], signals)
    
    if not clk:
        print(f"Error: Clock '{cfg['clk']}' not found.", file=sys.stderr)
        sys.exit(1)
    
    edge = 'rise' if cfg.get('edge', 'posedge') == 'posedge' else 'fall'
    
    def get_hist(name):
        m = resolve_signal(name, signals)
        if m:
            return history.get(m[0], [])
        return []
    
    hist_clk = history.get(clk[0], [])
    hist_vld = history.get(vld[0], []) if vld else []
    hist_rdy = history.get(rdy[0], []) if rdy else []
    hist_data = history.get(data_sig[0], []) if data_sig else []
    
    start = args.begin or 0
    end = args.end or float('inf')
    
    # Find clock edges
    clk_edges = []
    prev = None
    for t, val in hist_clk:
        if t < start: prev = val; continue
        if t > end: break
        v, pv = val_int(val), val_int(prev)
        if prev is not None and v is not None and pv is not None:
            if edge == 'rise' and pv == 0 and v == 1:
                clk_edges.append(t)
            elif edge == 'fall' and pv == 1 and v == 0:
                clk_edges.append(t)
        prev = val
    
    def sample_at(edges, hist):
        samples = []
        idx = 0
        for et in edges:
            v = None
            for j in range(len(hist) - 1, -1, -1):
                if hist[j][0] <= et:
                    v = hist[j][1]
                    break
            samples.append((et, v))
        return samples
    
    vld_samples = sample_at(clk_edges, hist_vld)
    rdy_samples = sample_at(clk_edges, hist_rdy) if rdy else [(t, 1) for t in clk_edges]
    data_samples = sample_at(clk_edges, hist_data) if data_sig else []
    
    transactions = []
    for i, t in enumerate(clk_edges):
        vld_v = val_int(vld_samples[i][1]) if vld_samples and i < len(vld_samples) else 1
        if vld is None:
            vld_v = 1
        rdy_v = val_int(rdy_samples[i][1]) if i < len(rdy_samples) else 1
        
        if vld_v == 1 and rdy_v == 1:
            dv = val_int(data_samples[i][1]) if data_sig and i < len(data_samples) else None
            transactions.append({
                'cycle': len(transactions) + 1,
                'time_ns': t,
                'data': dv,
                'data_str': fmt_val_short(dv, data_sig[1]['size']) if dv is not None and data_sig else '-'
            })
    
    print(f"Transaction extraction: @ {cfg['clk']} {cfg.get('edge', 'posedge')}")
    if vld: print(f"  Valid:  {vld[1]['fullname']}")
    if rdy: print(f"  Ready:  {rdy[1]['fullname']}")
    if data_sig: print(f"  Data:   {data_sig[1]['fullname']}")
    print(f"  Clk edges: {len(clk_edges)}, Transactions: {len(transactions)}")
    print()
    if transactions:
        print(f"{'#':>4} {'Time (ns)':<14} {'Data':<20}")
        print("-" * 45)
        for tx in transactions:
            print(f"{tx['cycle']:>4} {tx['time_ns']:<14.1f} {tx['data_str']:<20}")
    if args.json:
        print(json.dumps(transactions))


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='vdump - VCD waveform CLI tool (xwave-style for VCD)',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('vcd', help='Path to VCD file')
    sub = parser.add_subparsers(dest='command')
    
    sub.add_parser('signals', help='List all signals')
    sub.add_parser('summary', help='VCD file summary')
    
    p = sub.add_parser('value', help='Query signal value at time')
    p.add_argument('signal', help='Signal name')
    p.add_argument('time', type=float, help='Time in ns')
    p.add_argument('-b', '--binary', action='store_true')
    p.add_argument('-d', '--decimal', action='store_true')
    p.add_argument('--all', action='store_true')
    p.add_argument('--json', action='store_true')
    
    p = sub.add_parser('diff', help='Find first time signals differ')
    p.add_argument('signals', nargs='+')
    p.add_argument('-b', '--begin', type=float)
    p.add_argument('-e', '--end', type=float)
    
    p = sub.add_parser('find', help='Find all times signal equals a value')
    p.add_argument('signal')
    p.add_argument('value', help='Value (0xHEX, 0bBIN, decimal)')
    p.add_argument('--count', action='store_true')
    p.add_argument('-b', '--begin', type=float, default=0)
    p.add_argument('-e', '--end', type=float)
    
    p = sub.add_parser('search', help='Search signal in value range')
    p.add_argument('signal')
    p.add_argument('range', help='Value or range "lo-hi"')
    p.add_argument('--count', action='store_true')
    
    p = sub.add_parser('edge', help='Find signal edges')
    p.add_argument('signal')
    p.add_argument('--type', choices=['rise', 'fall', 'both'], default='both')
    p.add_argument('-b', '--begin', type=float, default=0)
    p.add_argument('-e', '--end', type=float)
    p.add_argument('--count', action='store_true')
    
    p = sub.add_parser('sample', help='Sample signal at clock edges')
    p.add_argument('clk', help='Clock signal')
    p.add_argument('signal', help='Signal to sample')
    p.add_argument('--edge', choices=['rise', 'fall', 'both'], default='rise')
    p.add_argument('-b', '--begin', type=float, default=0)
    p.add_argument('-e', '--end', type=float)
    p.add_argument('--count', action='store_true')
    p.add_argument('--json', action='store_true')
    
    p = sub.add_parser('pulse', help='Find narrow pulses')
    p.add_argument('signal')
    p.add_argument('max_width', type=float, help='Max pulse width (ns)')
    p.add_argument('--min', type=float, default=0, dest='min_width')
    p.add_argument('--polarity', choices=['high', 'low', 'both'], default='both')
    p.add_argument('--count', action='store_true')
    
    p = sub.add_parser('view', help='View signal values as table over time')
    p.add_argument('signals', nargs='+')
    p.add_argument('-b', '--begin', type=float, default=0)
    p.add_argument('-e', '--end', type=float)
    p.add_argument('-s', '--step', type=float, default=1.0)
    
    p = sub.add_parser('event', help='Extract valid/ready transactions')
    p.add_argument('config', help='JSON config file or inline JSON')
    p.add_argument('-b', '--begin', type=float, default=0)
    p.add_argument('-e', '--end', type=float)
    p.add_argument('--json', action='store_true')
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    
    fmt = 'h'
    if hasattr(args, 'binary') and args.binary: fmt = 'b'
    if hasattr(args, 'decimal') and args.decimal: fmt = 'd'
    args.format = fmt
    
    cmds = {
        'signals': cmd_signals, 'value': cmd_value, 'summary': cmd_summary,
        'diff': cmd_diff, 'find': cmd_find, 'search': cmd_search,
        'edge': cmd_edge, 'sample': cmd_sample, 'pulse': cmd_pulse,
        'view': cmd_view, 'event': cmd_event,
    }
    cmds[args.command](args.vcd, args)


if __name__ == '__main__':
    main()
