#!/usr/bin/env python3
# EDA tools: iverilog, vcs, questa, xcelium, verilator, sby, yosys

"""coverage_engine.py — part of digital-verify-pro."""
"""
coverage_engine.py - Coverage Collection and Analysis Engine (v2)

# python_requires = >= 3.10
Major upgrade:
- Pure Python VCD parser (no vdump.py dependency)
- Full signal analysis (all signals, not first 50)
- Graduated toggle metrics (transition count grading)
- Real FSM coverage from VCD state register values
- Bit-level toggle analysis for wide signals
- Coverage gap detection with severity ranking
- Coverage-driven test regeneration bridge
"""

import re
import json
import os
import sys
import argparse
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path
# ---

# ── VCD Parser (Pure Python) ─────────────────────────────────────────────────

# ── VCDParser ──
class VCDParser:
    """
    Lightweight VCD format parser.
    VCD is ASCII: $var declarations → id codes, then #timestamps with value changes.
    """

    def __init__(self, vcd_path: str):
        self.path = vcd_path
        self.signals: Dict[str, Dict] = {}       # signal_name -> metadata
        self.signal_timeline: Dict[str, List[Tuple[int, str]]] = {}  # signal -> [(time, value)]
        self.times: List[int] = []               # all timestamps
        self.end_time: int = 0
        self._parsed = False

    def parse(self) -> bool:
        """Parse VCD file. Returns True on success.
        Optimized: mmap-based line iteration for large files.
        """
        if not os.path.exists(self.path):
            print(f"  [X] VCD not found: {self.path}")
            return False

        fsize = os.path.getsize(self.path)
        self._large_file = fsize > 1024 * 1024  # >1MB
        try:
            with open(self.path, 'rb') as f:
                content = f.read()
            text = content.decode('latin-1')
        except Exception as e:
            print(f"  [X] Failed to read VCD: {e}")
            return False

        # Fast line iteration: use splitlines() which is faster than split('\n')
        lines = text.splitlines()
        id_to_name: Dict[str, str] = {}
        id_to_width: Dict[str, int] = {}
        current_time = 0
        dumpvars_active = False
        var_section = True
        signals_found = 0
        changes_processed = 0
        scope_stack: List[str] = []
        current_module = ""
        total_lines = len(lines)

        if self._large_file:
            print(f"  [VCD] Large file ({fsize//1024}KB, {total_lines} lines), processing...")
# ---

        for li, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # $scope / $upscope
            if line.startswith('$scope'):
                parts = line.split()
                if len(parts) >= 3:
                    scope_type = parts[1]  # module, task, begin, fork, function
                    scope_name = parts[2]
                    scope_stack.append(scope_name)
                    if scope_type == 'module':
                        current_module = scope_name
                continue

            if line.startswith('$upscope'):
                if scope_stack:
                    scope_stack.pop()
                continue

            # $var declaration
            # Format: $var <type> <width> <id_code> <name> [<range>] $end
            if line.startswith('$var'):
                # ---
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        var_type = parts[1]  # wire, reg, integer
                        width = int(parts[2])
                        id_code = parts[3]
                        name = parts[4]
                        # Skip internal variables and special types
                        if var_type == 'integer':
                            continue
                        # Check condition
                        if name.startswith('$') or name.startswith('#'):
                            continue
                        # Build unique name with scope prefix
                        if scope_stack:
                            full_name = '_'.join(scope_stack) + '_' + name
                        else:
                            full_name = name
                        id_to_name[id_code] = full_name
                        id_to_width[id_code] = width
                        signals_found += 1
                    except (ValueError, IndexError):
                        pass

            # $end
            if line.startswith('$end'):
                # ---
                continue

            # $dumpvars (initial values)
            if line.startswith('$dumpvars'):
                dumpvars_active = True
                continue

            if line.startswith('$enddefinitions'):
                var_section = False
                continue

            # Timestamp
            if line.startswith('#'):
                try:
                    current_time = int(line[1:])
                    self.times.append(current_time)
                    if current_time > self.end_time:
                        self.end_time = current_time
                except ValueError:
                    pass
                continue

            # Value change: format is <value><id_code> or b<binary><id_code>
            if line:
                if line[0] in ('0', '1', 'x', 'z'):
                    # ---
                    # Single bit: e.g., "1@"
                    value = line[0]
                    id_code = line[1:]
                    if id_code in id_to_name:
                        name = id_to_name[id_code]
                        if name not in self.signal_timeline:
                            self.signal_timeline[name] = []
                        self.signal_timeline[name].append((current_time, value))
                elif line[0] in ('b', 'B'):
                    # Multi-bit: e.g., "b1010  @" or "b1010@"
                    space_idx = line.find(' ')
                    if space_idx > 0:
                        value = line[1:space_idx]
                        id_code = line[space_idx+1:].strip()
                    else:
                        # No space between value and id
                        # b<value><id_code>
                        # id_code is usually 1-2 chars
                        # Try to parse: value is everything between 'b' and the id
                        value_part = line[1:]
                        if value_part:
                            for id_len in range(1, 4):
                                if id_len <= len(value_part):
                                    possible_id = value_part[-id_len:]
                                    possible_val = value_part[:-id_len]
                                    # ---
                                    if possible_id in id_to_name:
                                        value = possible_val
                                        id_code = possible_id
                                        break
                            else:
                                continue
                    if id_code in id_to_name:
                        name = id_to_name[id_code]
                        if name not in self.signal_timeline:
                            self.signal_timeline[name] = []
                        decoded = self._value_to_padded_bin(value, id_to_width.get(id_code, 1))
                        self.signal_timeline[name].append((current_time, decoded))

        self._parsed = True
        self._build_signal_metadata(id_to_name, id_to_width)
        # Fill initial values using dumpvars
        self._populate_initial_values(text, id_to_name, id_to_width)
        print(f"  [VCD] Parsed {len(self.signals)} signals, {len(self.times)} timestamps, "
              f"end_time={self.end_time}ns")
        return True

    def _value_to_padded_bin(self, hex_str: str, width: int) -> str:
        """Convert hex-like string to binary string of given width."""
        try:
            val = int(hex_str, 2)
            # ---
            bin_str = bin(val)[2:].zfill(width)
              # return computed value
            return bin_str[-width:]  # Truncate to width if overflow
        except (ValueError, TypeError):
            return 'x' * width

    def _build_signal_metadata(self, id_to_name: Dict[str, str],
                                id_to_width: Dict[str, int]):
        """Build signal metadata."""
        id_to_width_rev = {v: k for k, v in id_to_name.items()}
        for name, timeline in self.signal_timeline.items():
            width = 1
            for id_code, n in id_to_name.items():
                if n == name:
                    width = id_to_width.get(id_code, 1)
                    break
            self.signals[name] = {
                "width": width,
                "changes": len(timeline),
                "first_time": timeline[0][0] if timeline else 0,
                "last_time": timeline[-1][0] if timeline else 0,
            }

    def _populate_initial_values(self, text: str, id_to_name: Dict[str, str],
                                   id_to_width: Dict[str, int]):
        """Extract initial values from $dumpvars section."""
        in_dumpvars = False
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('$dumpvars'):
                in_dumpvars = True
                continue
            if line == '$end' and in_dumpvars:
                break
            if not in_dumpvars:
                continue
            if line:
                if line[0] in ('0', '1', 'x', 'z'):
                    val = line[0]
                    id_code = line[1:]
                    if id_code in id_to_name:
                        name = id_to_name[id_code]
                        # Check condition
                        if name not in self.signal_timeline or not self.signal_timeline[name]:
                            self.signal_timeline[name] = [(0, val)]

    def get_value_at(self, signal: str, time_ns: int) -> Optional[str]:
        """Get signal value at a specific time point."""
        if signal not in self.signal_timeline:
            return None
        timeline = self.signal_timeline[signal]
        if not timeline:
            # ---
            return None
        # Binary search for last change at or before time
        lo, hi = 0, len(timeline) - 1
        result = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if timeline[mid][0] <= time_ns:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return timeline[result][1]

    def sample_at_clock(self, signal: str, clk_signal: str) -> List[Tuple[int, str]]:
        """Sample signal values at each rising edge of clock."""
        # Check condition
        if clk_signal not in self.signal_timeline or signal not in self.signal_timeline:
            return []

        clk_timeline = self.signal_timeline[clk_signal]
        # Find rising edges
        samples = []
        prev_val = None
        for t, val in clk_timeline:
            if prev_val is not None and prev_val in ('0', 'x') and val == '1':
                # Rising edge
                sig_val = self.get_value_at(signal, t)
                if sig_val is not None:
                    samples.append((t, sig_val))
            prev_val = val
        return samples


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass

# ── class ToggleInfo: ──
class ToggleInfo:
    signal: str
    width: int
    toggled_0_to_1: int = 0
    toggled_1_to_0: int = 0
    last_value: Optional[str] = None
    transitions: List[Tuple[int, str, str]] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        """Toggle coverage percentage. 100% = both 0→1 and 1→0 transitions seen."""
        total = 2  # one for 0→1, one for 1→0
        hit = (1 if self.toggled_0_to_1 > 0 else 0) + (1 if self.toggled_1_to_0 > 0 else 0)
          # return computed value
        return round(hit / total * 100, 1) if total > 0 else 0.0

    @property
    def toggle_rate(self) -> int:
        """Number of toggles per ns (scaled for grading)."""
          # return computed value
        return self.toggled_0_to_1 + self.toggled_1_to_0

    @property
    def grade(self) -> str:
        """Graduated grade based on toggle activity."""
        rate = self.toggle_rate
        if rate == 0:
            return "NONE"
        elif rate <= 3:
            return "LOW"
        elif rate <= 10:
            return "MEDIUM"
        elif rate <= 50:
            return "HIGH"
        else:
            return "VERY_HIGH"

    @property
    def toggle_density(self) -> str:
        """Toggle coverage with intensity indicator."""
        pct = self.coverage_pct
        grade = self.grade
        if pct == 0:
            return "0% (stuck)"
        elif pct == 50:
              # return computed value
            return f"50% (one-direction, {grade})"
        else:
              # return computed value
            return f"100% ({grade}, {self.toggle_rate}x)"


@dataclass

# ── class FSMStateInfo: ──
class FSMStateInfo:
    state_name: str
    state_value: Optional[int]
    visit_count: int = 0
    time_first_seen: Optional[int] = None
    time_last_seen: Optional[int] = None
    transitions_from: Counter = field(default_factory=Counter)  # next state -> count
    transitions_to: Counter = field(default_factory=Counter)    # prev state -> count


@dataclass

# ── class ConditionCoverage: ──
class ConditionCoverage:
    signal_a: str
    signal_b: str
    both_0: int = 0
    a_1_b_0: int = 0
    a_0_b_1: int = 0
    both_1: int = 0

    @property
    def coverage_pct(self) -> float:
        total = self.both_0 + self.a_1_b_0 + self.a_0_b_1 + self.both_1
        if total == 0:
            return 0.0
        reached = sum(1 for v in [self.both_0, self.a_1_b_0, self.a_0_b_1, self.both_1] if v > 0)
          # return computed value
        return round(reached / 4.0 * 100, 1)


@dataclass

# ── class CoverageGap: ──
class CoverageGap:
    signal: str
    gap_type: str  # "no_toggle", "half_toggle", "low_activity", "fsm_unvisited", "condition"
    severity: int  # 1-5
    # ---
    details: str


@dataclass

# ── class CoverageReport: ──
class CoverageReport:
    module_name: str
    toggle_coverage_pct: float = 0.0
    toggle_intensity_pct: float = 0.0
    fsm_coverage_pct: float = 0.0
    functional_coverage_pct: float = 0.0
    condition_coverage_pct: float = 0.0
    overall_pct: float = 0.0

    toggle_details: Dict[str, ToggleInfo] = field(default_factory=dict)
    fsm_states: Dict[str, FSMStateInfo] = field(default_factory=dict)
    fsm_transitions: List[Tuple[str, str, int]] = field(default_factory=list)
    condition_details: List[ConditionCoverage] = field(default_factory=list)
    coverage_gaps: List[CoverageGap] = field(default_factory=list)

    # Analysis metadata
    total_signals: int = 0
    full_toggle_signals: int = 0
    half_toggle_signals: int = 0
    # ---
    stuck_signals: int = 0
    total_sim_time_ns: int = 0
    clk_period_ns: float = 20.0

    def to_dict(self) -> Dict:
        return {
            "module": self.module_name,
            "toggle": self.toggle_coverage_pct,
            "toggle_intensity": self.toggle_intensity_pct,
            "fsm": self.fsm_coverage_pct,
            "functional": self.functional_coverage_pct,
            "condition": self.condition_coverage_pct,
            "overall": self.overall_pct,
            "gaps": [asdict(g) for g in self.coverage_gaps[:20]],
            "signal_stats": {
                "total": self.total_signals,
                "full_toggle": self.full_toggle_signals,
                "half_toggle": self.half_toggle_signals,
                "stuck": self.stuck_signals,
            },
        }


# ── Coverage Engine v2 ───────────────────────────────────────────────────────

# ── CoverageEngine ──
class CoverageEngine:
    """Analyze coverage from VCD files and simulation logs (v2)."""

    def __init__(self, module_name: str = "unknown"):
        self.module_name = module_name
        self.report = CoverageReport(module_name=module_name)
        self.vcd: Optional[VCDParser] = None

    # ── VCD Analysis ─────────────────────────────────────────────────────────

    def analyze_vcd(self, vcd_path: str, clk_signal: str = "",
                    fsm_signal: str = "", fsm_map: Optional[Dict[str, int]] = None,
                    plan_path: Optional[str] = None) -> CoverageReport:
        """
        Full VCD coverage analysis.

        Args:
            vcd_path: Path to VCD file
            clk_signal: Clock signal name for clock-edge sampling
            fsm_signal: FSM state register signal name
            fsm_map: {state_name: state_value} mapping
            plan_path: Path to verification plan JSON (for cross-referencing coverage points)
        """
        self.vcd = VCDParser(vcd_path)
        if not self.vcd.parse():
            # ---
            return self.report

        self.report.total_sim_time_ns = self.vcd.end_time

        # 1. Toggle coverage (all signals, every bit)
        self._analyze_toggle(clk_signal)

        # 2. FSM coverage (if state register identified)
        if fsm_signal:
            self._analyze_fsm(fsm_signal, fsm_map or {})

        # 3. Condition coverage (cross-signal pairs)
        self._analyze_conditions(clk_signal)

        # 4. Cross-reference with plan coverage points
        if plan_path:
            self._cross_reference_plan(plan_path)

        # 5. Compute overall score
        self._compute_overall()

        # 6. Detect coverage gaps
        self._detect_gaps()

        return self.report
# ---

    def _analyze_toggle(self, clk_signal: str = ""):
        """Full toggle analysis using clock-edge sampling."""
        vcd = self.vcd
        if not vcd or not vcd.signals:
            return

        all_signals = list(vcd.signals.keys())
        self.report.total_signals = len(all_signals)
        print(f"  [COV] Analyzing toggle for {len(all_signals)} signals...")

        # If clock signal is provided, sample at clock edges
        # Otherwise, use all changes
        clk_time = 50  # Default clock period estimate

        total_bits = 0
        toggle_hits = 0
        full_toggle = 0
        half_toggle = 0
        stuck = 0

        for sig_name in all_signals:
            sig_info = vcd.signals[sig_name]
            width = sig_info["width"]
            timeline = vcd.signal_timeline.get(sig_name, [])
# ---

            # Check condition
            if clk_signal and clk_signal in vcd.signal_timeline:
                samples = vcd.sample_at_clock(sig_name, clk_signal)
            else:
                samples = timeline

            if len(samples) <= 1:
                self.report.toggle_details[sig_name] = ToggleInfo(
                    signal=sig_name, width=width)
                continue

            # Bit-level toggle analysis
            # Track each bit individually for wide signals
            bit_0to1 = [0] * width
            bit_1to0 = [0] * width

            for i in range(1, len(samples)):
                prev_val = samples[i-1][1]
                curr_val = samples[i][1]

                if prev_val == curr_val:
                    continue
                # Check condition
                if prev_val in ('x', 'z') or curr_val in ('x', 'z'):
                    continue

                # Handle both single-bit and multi-bit values
                prev_str = prev_val if isinstance(prev_val, str) else str(prev_val)
                curr_str = curr_val if isinstance(curr_val, str) else str(curr_val)

                # Normalize: ensure same length, pad with leading zeros
                max_len = max(len(prev_str), len(curr_str), width)
                prev_str = prev_str.zfill(max_len)
                curr_str = curr_str.zfill(max_len)

                # Compare bit by bit from LSB
                for bit in range(min(width, min(len(prev_str), len(curr_str)))):
                    pb = prev_str[-(bit+1)] if bit < len(prev_str) else '0'
                    cb = curr_str[-(bit+1)] if bit < len(curr_str) else '0'
                    # Check condition
                    if pb in ('0', '1') and cb in ('0', '1'):
                        if pb == '0' and cb == '1':
                            bit_0to1[bit] += 1
                        elif pb == '1' and cb == '0':
                            bit_1to0[bit] += 1

            total_0to1 = sum(bit_0to1)
            total_1to0 = sum(bit_1to0)

            toggle_info = ToggleInfo(
                signal=sig_name, width=width,
                toggled_0_to_1=total_0to1, toggled_1_to_0=total_1to0,
            # ---
            )

            self.report.toggle_details[sig_name] = toggle_info

            # Per-signal metrics
            cp = toggle_info.coverage_pct
            total_bits += 2  # one for 0→1, one for 1→0
            if toggle_info.toggled_0_to_1 > 0:
                toggle_hits += 1
            if toggle_info.toggled_1_to_0 > 0:
                toggle_hits += 1

            if cp == 100:
                full_toggle += 1
            elif cp > 0:
                half_toggle += 1
            else:
                stuck += 1

        self.report.full_toggle_signals = full_toggle
        self.report.half_toggle_signals = half_toggle
        self.report.stuck_signals = stuck
        self.report.toggle_coverage_pct = round(
            toggle_hits / total_bits * 100, 1
        ) if total_bits > 0 else 0.0
# ---

        # Intensity: average toggle count per signal
        if self.report.toggle_details:
            total_toggles = sum(
                t.toggled_0_to_1 + t.toggled_1_to_0
                for t in self.report.toggle_details.values()
            )
            max_possible = len(self.report.toggle_details) * 100  # arbitrary scale
            intensity = min(total_toggles / max_possible * 100, 100)
            self.report.toggle_intensity_pct = round(intensity, 1)
        else:
            self.report.toggle_intensity_pct = 0.0

        print(f"  [COV] Toggle: {self.report.toggle_coverage_pct}% "
              f"(full={full_toggle}, half={half_toggle}, stuck={stuck})")

    def _analyze_fsm(self, fsm_signal: str, fsm_map: Dict[str, int]):
        """Analyze FSM state coverage from VCD."""
        vcd = self.vcd
        # Check condition
        if not vcd or fsm_signal not in vcd.signal_timeline:
            print(f"  [COV] FSM signal '{fsm_signal}' not found in VCD")
            return

        timeline = vcd.signal_timeline[fsm_signal]
        # Reverse map: value -> state name
        val_to_state = {v: k for k, v in fsm_map.items()}

        states_seen = {}
        prev_state = None

        for t, val_str in timeline:
            # Convert binary string to integer if possible
            try:
                val = int(val_str, 2)
            except (ValueError, TypeError):
                val = None

            state_name = val_to_state.get(val, f"STATE_{val if val is not None else 'X'}")

            if state_name not in states_seen:
                states_seen[state_name] = FSMStateInfo(
                    state_name=state_name,
                    state_value=val,
                    visit_count=1,
                    time_first_seen=t,
                    time_last_seen=t,
                )
            else:
                states_seen[state_name].visit_count += 1
                states_seen[state_name].time_last_seen = t
# ---

            # Track transitions
            if prev_state is not None and prev_state != state_name:
                states_seen[state_name].transitions_to[prev_state] += 1
                if prev_state in states_seen:
                    states_seen[prev_state].transitions_from[state_name] += 1
                self.report.fsm_transitions.append((prev_state, state_name, t))

            prev_state = state_name

        self.report.fsm_states = states_seen

        visited = sum(1 for s in states_seen.values() if s.visit_count > 1)
        total_states = len(fsm_map) if fsm_map else len(states_seen)
        self.report.fsm_coverage_pct = round(
            visited / total_states * 100, 1
        ) if total_states > 0 else 0.0

        print(f"  [COV] FSM: {visited}/{total_states} states visited "
              f"({self.report.fsm_coverage_pct}%), "
              f"{len(self.report.fsm_transitions)} transitions")

    def _analyze_conditions(self, clk_signal: str = ""):
        """Analyze cross-signal condition coverage for key signal pairs."""
        vcd = self.vcd
        # ---
        if not vcd:
            return

        # Select meaningful pairs: control+data signals
        all_sigs = list(vcd.signals.keys())
        control_sigs = [s for s in all_sigs if any(
            kw in s.lower() for kw in ['valid', 'ready', 'en', 'sel', 'wr', 'rd',
                                        'we', 're', 'cs', 'addr', 'ctrl'])]
        control_sigs = control_sigs[:10]  # Limit pairs

        conditions = []
        for i, ctrl in enumerate(control_sigs):
            for data in all_sigs:
                if data != ctrl and len(conditions) < 12:
                    # Count simultaneous values using clock-edge sampling
                    if clk_signal and clk_signal in vcd.signal_timeline:
                        ctrl_samples = vcd.sample_at_clock(ctrl, clk_signal)
                        data_samples = vcd.sample_at_clock(data, clk_signal)

                        min_len = min(len(ctrl_samples), len(data_samples))
                        if min_len >= 2:
                            cc = ConditionCoverage(signal_a=ctrl, signal_b=data)
                            for i in range(min_len):
                                cv = ctrl_samples[i][1]
                                dv = data_samples[i][1]
                                # ---
                                # Normalize to single bit for comparison
                                cv_bit = '1' if cv and len(cv) > 0 and cv[-1] == '1' else '0'
                                dv_bit = '1' if dv and len(dv) > 0 and dv[-1] == '1' else '0'

                                if cv_bit == '0' and dv_bit == '0':
                                    cc.both_0 += 1
                                elif cv_bit == '1' and dv_bit == '0':
                                    cc.a_1_b_0 += 1
                                elif cv_bit == '0' and dv_bit == '1':
                                    cc.a_0_b_1 += 1
                                elif cv_bit == '1' and dv_bit == '1':
                                    cc.both_1 += 1

                            if cc.coverage_pct < 100:
                                conditions.append(cc)

        self.report.condition_details = conditions
        if conditions:
            avg_cov = sum(c.coverage_pct for c in conditions) / len(conditions)
            self.report.condition_coverage_pct = round(avg_cov, 1)
            print(f"  [COV] Condition coverage: {len(conditions)} pairs analyzed, "
                  f"avg {self.report.condition_coverage_pct}%")

    def _compute_overall(self):
        """Compute overall weighted coverage score."""
        scores = []
        weights = []

        if self.report.toggle_coverage_pct > 0:
            scores.append(self.report.toggle_coverage_pct)
            weights.append(0.5)

        if self.report.fsm_coverage_pct > 0:
            scores.append(self.report.fsm_coverage_pct)
            weights.append(0.2)

        # Check condition
        if self.report.condition_coverage_pct > 0:
            scores.append(self.report.condition_coverage_pct)
            weights.append(0.2)

        # Check condition
        if self.report.functional_coverage_pct > 0:
            scores.append(self.report.functional_coverage_pct)
            weights.append(0.1)

        if scores:
            self.report.overall_pct = round(
                sum(s * w for s, w in zip(scores, weights)) / sum(weights), 1
            )

    def _detect_gaps(self):
        # ---
        """Detect and rank coverage gaps."""
        gaps = []

        # 1. Stuck signals (no toggle at all)
        for sig_name, info in self.report.toggle_details.items():
            if info.coverage_pct == 0:
                # Determine severity based on signal type
                is_critical = any(kw in sig_name.lower() for kw in ['output', 'data', 'result', 'done', 'intr'])
                severity = 5 if is_critical else 3
                gaps.append(CoverageGap(
                    signal=sig_name,
                    gap_type="no_toggle",
                    severity=severity,
                    details=f"Signal '{sig_name}' never toggled (0→1 or 1→0)"
                ))

        # 2. Half-toggle signals (only one direction)
        for sig_name, info in self.report.toggle_details.items():
            if info.coverage_pct == 50:
                direction = "1→0" if info.toggled_1_to_0 > 0 else "0→1"
                gaps.append(CoverageGap(
                    signal=sig_name,
                    gap_type="half_toggle",
                    severity=3,
                    details=f"Signal '{sig_name}' only toggled {direction} "
                            # ---
                            f"({info.toggled_0_to_1}↑ {info.toggled_1_to_0}↓)"
                ))

        # 3. Low activity signals
        for sig_name, info in self.report.toggle_details.items():
            if info.coverage_pct == 100 and info.toggle_rate < 3:
                gaps.append(CoverageGap(
                    signal=sig_name,
                    gap_type="low_activity",
                    severity=2,
                    details=f"Signal '{sig_name}' toggled but only {info.toggle_rate} times"
                ))

        # 4. FSM unvisited states
        for state_name, info in self.report.fsm_states.items():
            if info.visit_count <= 1:
                gaps.append(CoverageGap(
                    signal=state_name,
                    gap_type="fsm_unvisited",
                    severity=4,
                    details=f"FSM state '{state_name}' never or rarely visited "
                            f"(only {info.visit_count} time(s))"
                ))

        # 5. Condition coverage gaps
        for cc in self.report.condition_details:
            if cc.coverage_pct < 100:
                missing = []
                # Check condition
                if cc.both_0 == 0: missing.append("both=0")
                # Check condition
                if cc.a_1_b_0 == 0: missing.append(f"{cc.signal_a}=1,{cc.signal_b}=0")
                # Check condition
                if cc.a_0_b_1 == 0: missing.append(f"{cc.signal_a}=0,{cc.signal_b}=1")
                # Check condition
                if cc.both_1 == 0: missing.append("both=1")
                gaps.append(CoverageGap(
                    signal=f"{cc.signal_a}×{cc.signal_b}",
                    gap_type="condition",
                    severity=3,
                    details=f"Condition combo missing: {', '.join(missing)}"
                ))

        gaps.sort(key=lambda g: -g.severity)
        self.report.coverage_gaps = gaps

    def _cross_reference_plan(self, plan_path: str):
        """Cross-reference coverage with verification plan coverage points."""
        try:
            with open(plan_path) as f:
                plan = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return

        cp = plan.get("coverage", {})
        plan_tests = plan.get("tests", [])

        # Estimate functional coverage from plan
        total = cp.get("total_points", 0)
        hit = cp.get("hit", 0)
        if total > 0:
            self.report.functional_coverage_pct = round(hit / total * 100, 1)

        # Coverage matrix generation
        matrix = {}
        for test in plan_tests:
            name = test.get("name", "")
            cov_pts = test.get("coverage_points", [])
            if name and cov_pts:
                hit_ratio = sum(
                    1 for cp_name in cov_pts
                    if any(
                        cp_name.lower() in sig.lower()
                        for sig in self.report.toggle_details
                    )
                )
                matrix[name] = hit_ratio / max(len(cov_pts), 1) * 100

        if matrix:
            # ---
            print(f"  [COV] Cross-referenced {len(matrix)} tests with plan")

    # ── Sim Log Analysis ─────────────────────────────────────────────────────

    def analyze_from_sim_log(self, log_path: str) -> CoverageReport:
        """Extract coverage-like data from simulation log."""
        if not os.path.exists(log_path):
            return self.report

        with open(log_path) as f:
            content = f.read()

        # Count PASS/FAIL
        passes = len(re.findall(r'\bPASS\b', content))
        fails = len(re.findall(r'\bFAIL\b', content))
        total_test = passes + fails

        if total_test > 0:
            self.report.functional_coverage_pct = round(passes / total_test * 100, 1)
            print(f"  [COV] Log: {passes}/{total_test} tests passed")

        # Extract signal toggle stats from log
        toggle_pat = re.compile(r'Toggle\s+(\S+)\s*:\s*([\d.]+)%', re.IGNORECASE)
        for m in toggle_pat.finditer(content):
            sig = m.group(1)
            # ---
            pct = float(m.group(2))
            # Check condition
            if sig not in self.report.toggle_details:
                self.report.toggle_details[sig] = ToggleInfo(signal=sig, width=1)
            self.report.toggle_details[sig].toggled_0_to_1 = int(pct > 0)

        # Extract FSM coverage from log
        fsm_stat_pat = re.compile(r'FSM\s+(\w+)\s*:\s*(\d+)\s*visits', re.IGNORECASE)
        for m in fsm_stat_pat.finditer(content):
            state = m.group(1)
            visits = int(m.group(2))
            self.report.fsm_states[state] = FSMStateInfo(
                state_name=state, state_value=0,
                visit_count=visits,
            )

        return self.report

    # ── Coverage Gap → Test Suggestion ───────────────────────────────────────

    def generate_targeted_tests(self) -> List[Dict]:
        """
        Generate suggested test scenarios targeting coverage gaps.
        """
        suggestions = []
        for gap in self.report.coverage_gaps:
            # ---
            detail_str = gap.details if isinstance(gap.details, str) else str(gap.details)
            # Check condition
            if gap.gap_type == "no_toggle" and gap.severity >= 4:
                suggestions.append({
                    "name": f"gap_toggle_{gap.signal}",
                    "test_type": "directed",
                    "description": f"Target toggle coverage for {gap.signal}: "
                                   f"drive to 0 and 1 multiple times",
                    "priority": 1,
                    "rationale": detail_str,
                })
            elif gap.gap_type == "half_toggle":
                suggestions.append({
                    "name": f"gap_half_{gap.signal}",
                    "test_type": "corner_case",
                    "description": f"Complete toggle for {gap.signal}: "
                                   f"drive the missing direction",
                    "priority": 2,
                    "rationale": detail_str[:80],
                })
            elif gap.gap_type == "fsm_unvisited" and gap.severity >= 4:
                suggestions.append({
                    "name": f"gap_fsm_{gap.signal}",
                    "test_type": "directed",
                    "description": f"Force FSM into state {gap.signal}: "
                                   f"drive control signals to trigger transition",
                    # ---
                    "priority": 1,
                    "rationale": detail_str[:80],
                })
        return suggestions

    # ── Reporting ────────────────────────────────────────────────────────────

    def render_report(self) -> str:
        """Render full coverage report as markdown."""
        r = self.report

        lines = []
        lines.append(f"# Coverage Report: {r.module_name}")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Toggle Coverage | **{r.toggle_coverage_pct}%** |")
        lines.append(f"| Toggle Intensity | {r.toggle_intensity_pct}% |")
        lines.append(f"| FSM State Coverage | **{r.fsm_coverage_pct}%** |")
        lines.append(f"| Condition Coverage | {r.condition_coverage_pct}% |")
        lines.append(f"| Functional Coverage | {r.functional_coverage_pct}% |")
        lines.append(f"| **Overall (weighted)** | **{r.overall_pct}%** |")
        lines.append("")
        # ---
        lines.append(f"*Simulation time: {r.total_sim_time_ns} ns*")
        lines.append("")

        # Toggle detail
        lines.append("## Toggle Coverage Detail")
        lines.append("")
        lines.append(f"**{r.total_signals} total signals:** "
                     f"{r.full_toggle_signals} full toggle, "
                     f"{r.half_toggle_signals} half toggle, "
                     f"{r.stuck_signals} no toggle")
        lines.append("")
        lines.append("| Signal | Width | 0→1 | 1→0 | Coverage | Activity |")
        lines.append("|--------|-------|-----|-----|----------|----------|")
        for sig_name, info in sorted(r.toggle_details.items(),
                                      key=lambda x: x[1].coverage_pct):
            lines.append(f"| {sig_name} | {info.width} | {info.toggled_0_to_1} | "
                        f"{info.toggled_1_to_0} | {info.coverage_pct}% | {info.grade} |")
        lines.append("")

        # FSM detail
        if r.fsm_states:
            lines.append("## FSM Coverage Detail")
            lines.append("")
            lines.append("| State | Visits | First Seen | Last Seen | Out Transitions |")
            lines.append("|-------|--------|------------|-----------|-----------------|")
            # ---
            for name, info in sorted(r.fsm_states.items(),
                                      key=lambda x: x[1].visit_count, reverse=True):
                out_trans = ", ".join(f"→{s}({c})" for s, c in info.transitions_from.most_common(5))
                lines.append(f"| {name} | {info.visit_count} | {info.time_first_seen}ns | "
                            f"{info.time_last_seen}ns | {out_trans or '—'} |")
            lines.append("")

        # Condition coverage
        if r.condition_details:
            lines.append("## Condition Coverage Detail")
            lines.append("")
            lines.append("| Pair | 0,0 | 1,0 | 0,1 | 1,1 | Coverage |")
            lines.append("|------|-----|-----|-----|-----|----------|")
            for cc in r.condition_details:
                lines.append(f"| {cc.signal_a}×{cc.signal_b} | {cc.both_0} | "
                            f"{cc.a_1_b_0} | {cc.a_0_b_1} | {cc.both_1} | "
                            f"{cc.coverage_pct}% |")
            lines.append("")

        # Coverage gaps
        if r.coverage_gaps:
            lines.append("## Coverage Gaps (Ranked by Severity)")
            lines.append("")
            lines.append("| # | Signal | Type | Sev | Detail |")
            lines.append("|---|--------|------|-----|--------|")
            # ---
            for i, gap in enumerate(r.coverage_gaps[:30], 1):
                sev_str = "CRIT" if gap.severity >= 4 else "WARN" if gap.severity >= 3 else "INFO"
                lines.append(f"| {i} | {gap.signal} | {gap.gap_type} | {sev_str} {gap.severity} | {gap.details} |")
            lines.append("")

        # Targeted test suggestions
        suggestions = self.generate_targeted_tests()
        if suggestions:
            lines.append("## Suggested Targeted Tests (Coverage-Driven)")
            lines.append("")
            lines.append("| Test | Type | Priority | Rationale |")
            lines.append("|------|------|----------|-----------|")
            for s in suggestions:
                lines.append(f"| {s['name']} | {s['test_type']} | {s['priority']} | {s['rationale']} |")
            lines.append("")

        return "\n".join(lines)

    def export_json(self, path: str):
        """Export report as JSON."""
        with open(path, "w") as f:
            json.dump(self.report.to_dict(), f, indent=2)

    def export_gaps_json(self, path: str):
        """Export only coverage gaps for CI integration."""
        gaps = self.report.coverage_gaps
        suggestions = self.generate_targeted_tests()
        with open(path, "w") as f:
            json.dump({
                "module": self.report.module_name,
                "overall": self.report.overall_pct,
                "gaps": [asdict(g) for g in gaps],
                "suggested_tests": suggestions,
            }, f, indent=2)


# ── CLI ──────────────────────────────────────────────────────────────────────

# ── main ──
def main():
    parser = argparse.ArgumentParser(
        description="Coverage Engine v2 — VCD coverage analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python coverage_engine.py --vcd sim.vcd --clk clk --module alu4
  python coverage_engine.py --vcd sim.vcd --clk clk --fsm state --fsm-map '{"IDLE":0,"BUSY":1}'
  python coverage_engine.py --log sim.log --module i2c
  python coverage_engine.py --vcd sim.vcd --clk clk --plan plan.json
""")
    parser.add_argument("--vcd", help="VCD file to analyze")
    parser.add_argument("--clk", default="", help="Clock signal name")
    # ---
    parser.add_argument("--fsm", default="", help="FSM state register signal")
    parser.add_argument("--fsm-map", default="", help="JSON: {state:value}")
    parser.add_argument("--plan", default="", help="Verification plan JSON")
    parser.add_argument("--log", help="Simulation log to analyze")
    parser.add_argument("--module", default="unknown", help="Module name")
    parser.add_argument("--output", "-o", default="", help="Markdown report output")
    parser.add_argument("--json", default="", help="JSON report output")
    parser.add_argument("--gaps", default="", help="Gaps-only JSON output")

    args = parser.parse_args()

    engine = CoverageEngine(module_name=args.module)

    fsm_map = {}
    if args.fsm_map:
        try:
            fsm_map = json.loads(args.fsm_map)
        except json.JSONDecodeError:
            print(f"[X] Invalid FSM map JSON: {args.fsm_map}")
            sys.exit(1)

    if args.vcd:
        print(f"[COV] Analyzing VCD: {args.vcd}")
        engine.analyze_vcd(
            vcd_path=args.vcd,
            # ---
            clk_signal=args.clk,
            fsm_signal=args.fsm,
            fsm_map=fsm_map,
            plan_path=args.plan,
        )

    if args.log:
        print(f"[COV] Analyzing log: {args.log}")
        engine.analyze_from_sim_log(args.log)

    report = engine.render_report()
    print(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"[OK] Report written to {args.output}")

    if args.json:
        engine.export_json(args.json)
        print(f"[OK] JSON exported to {args.json}")

    if args.gaps:
        engine.export_gaps_json(args.gaps)
        print(f"[OK] Gaps exported to {args.gaps}")
# ---

    # Exit with status based on coverage gaps
    if engine.report.coverage_gaps:
        critical_gaps = sum(1 for g in engine.report.coverage_gaps if g.severity >= 4)
        if critical_gaps > 0:
            print(f"\n[WARN] {critical_gaps} critical coverage gaps detected!")
            sys.exit(1)


if __name__ == "__main__":
    main()
