#!/usr/bin/env python3
"""
plan_generator.py - Advanced Verification Plan Generator (v2)

Major upgrade:
- Deep RTL analysis: FSM extraction, data path analysis, control complexity,
  protocol interface detection, condition/expression coverage analysis
- Differentiated test generation based on actual design topology
- Richer coverage point types (condition, branch, path, toggle, transition pairs)
- Priority scoring based on design complexity
"""

import re
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum
from collections import defaultdict


# ── Type Enums ───────────────────────────────────────────────────────────────

class TestType(Enum):
    DIRECTED = "directed"
    RANDOM = "random"
    CONSTRAINED_RANDOM = "constrained_random"
    CORNER = "corner_case"
    ERROR = "error_injection"
    PROTOCOL = "protocol"
    FORMAL = "formal_property"
    SEQUENTIAL = "sequential"
    PIPELINE = "pipeline"
    RESET_DOMAIN = "reset_domain"
    CONCURRENT = "concurrent"
    FIFO = "fifo"
    TIMING = "timing"


class CoverageTarget(Enum):
    LINE = "line"
    TOGGLE = "toggle"
    FSM = "fsm_state"
    FSM_TRANSITION = "fsm_transition"
    FUNCTIONAL = "functional"
    CROSS = "cross"
    ASSERTION = "assertion"
    CONDITION = "condition"
    EXPRESSION = "expression"
    BRANCH = "branch"
    PATH = "path"
    COVER_POINT = "cover_point"


class FSMEncoding(Enum):
    ONE_HOT = "one_hot"
    BINARY = "binary"
    GRAY = "gray"
    UNKNOWN = "unknown"


class AlwaysBlockType(Enum):
    SEQUENTIAL = "sequential"
    COMBINATIONAL = "combinational"
    LATCH = "latch"


class ProtocolType(Enum):
    NONE = "none"
    VALID_READY = "valid_ready"
    APB = "APB"
    AXI = "AXI"
    AXI_STREAM = "axi_stream"
    I2C = "I2C"
    SPI = "SPI"
    UART = "UART"
    GPIO = "GPIO"
    HANDSHAKE = "handshake"


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class CoveragePoint:
    name: str
    target: CoverageTarget
    description: str
    weight: int = 1
    hit: bool = False
    bin_count: int = 1
    cross_with: Optional[str] = None
    rtl_context: str = ""  # Which RTL construct this point targets


@dataclass
class TestScenario:
    id: int
    name: str
    test_type: TestType
    description: str
    priority: int = 1  # 1-5
    code: str = ""
    expected_result: str = ""
    coverage_points: List[str] = field(default_factory=list)
    dependencies: List[int] = field(default_factory=list)
    status: str = "pending"
    iteration_count: int = 0
    max_iterations: int = 3
    rationale: str = ""  # WHY this test exists


@dataclass
class FSMInfo:
    state_reg_name: str = ""
    state_vars: List[str] = field(default_factory=list)
    encoding: FSMEncoding = FSMEncoding.UNKNOWN
    states: List[str] = field(default_factory=list)
    transitions: List[Tuple[str, str, str]] = field(default_factory=list)  # (from, to, condition)
    width: int = 0


@dataclass
class DataPathInfo:
    largest_width: int = 0
    widths: Dict[int, int] = field(default_factory=dict)  # width -> count
    has_mux: bool = False
    mux_inputs: int = 0
    has_adder: bool = False
    has_shifter: bool = False
    has_comparator: bool = False
    has_multiplier: bool = False
    has_memory: bool = False


@dataclass
class ControlInfo:
    always_blocks_total: int = 0
    sequential_blocks: int = 0
    combinational_blocks: int = 0
    nested_ifs: int = 0
    case_statements: int = 0
    case_items: int = 0
    condition_complexity: int = 0  # average conditions per decision
    has_pipeline: bool = False
    pipeline_stages: int = 0
    has_counter: bool = False
    counter_bits: int = 0
    has_fsm: bool = False


@dataclass
class VerificationPlan:
    module_name: str
    spec_summary: str
    test_scenarios: List[TestScenario] = field(default_factory=list)
    coverage_points: List[CoveragePoint] = field(default_factory=list)
    fsm_states: List[str] = field(default_factory=list)
    signals_under_test: List[str] = field(default_factory=list)
    clocks: List[str] = field(default_factory=list)
    resets: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    cross_coverage: List[tuple] = field(default_factory=list)

    # Deep analysis results
    fsm_info: Optional[FSMInfo] = None
    datapath_info: Optional[DataPathInfo] = None
    control_info: Optional[ControlInfo] = None
    protocols: List[ProtocolType] = field(default_factory=list)
    design_complexity_score: int = 0  # 1-10

    def compute_coverage(self) -> Dict:
        total = len(self.coverage_points)
        hit = sum(1 for cp in self.coverage_points if cp.hit)
        return {
            "total_points": total,
            "hit": hit,
            "coverage_pct": round(hit / total * 100, 1) if total > 0 else 0,
        }

    def add_test(self, scenario: TestScenario):
        self.test_scenarios.append(scenario)

    def to_dict(self) -> Dict:
        def _convert(obj):
            if isinstance(obj, Enum):
                return obj.value
            if hasattr(obj, '__dict__'):
                return {k: _convert(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
            if isinstance(obj, list):
                return [_convert(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            return obj
        return _convert({
            "module": self.module_name,
            "spec": self.spec_summary,
            "tests": [asdict(t) for t in self.test_scenarios],
            "coverage": self.compute_coverage(),
            "analysis": {
                "fsm": asdict(self.fsm_info) if self.fsm_info else None,
                "datapath": asdict(self.datapath_info) if self.datapath_info else None,
                "control": asdict(self.control_info) if self.control_info else None,
                "protocols": [p.value for p in self.protocols],
                "complexity": self.design_complexity_score,
            }
        })


# ── Deep RTL Analyzer ────────────────────────────────────────────────────────

class DeepRTLAnalyzer:
    """
    Performs semantic-level RTL analysis:
    - FSM extraction (state register, encoding, transitions)
    - Data path analysis (widths, operators, muxes)
    - Control complexity (nested conditions, case density)
    - Protocol interface detection
    - Signal dependency graph
    """

    # Protocol detection patterns
    PROTOCOL_PATTERNS = {
        ProtocolType.VALID_READY: [r'\bvalid\b', r'\bready\b'],
        ProtocolType.APB: [r'\bpsel\b', r'\bpenable\b', r'\bpaddr\b', r'\bpwdata\b', r'\bprdata\b'],
        ProtocolType.AXI: [r'\bawvalid\b', r'\bawready\b', r'\bwvalid\b', r'\bwready\b',
                          r'\barvalid\b', r'\barready\b', r'\brvalid\b', r'\brready\b'],
        ProtocolType.AXI_STREAM: [r'\btvalid\b', r'\btready\b', r'\btdata\b', r'\btlast\b'],
        ProtocolType.I2C: [r'\bscl\b', r'\bsda\b'],
        ProtocolType.SPI: [r'\bmosi\b', r'\bmiso\b', r'\bcs\b', r'\bsclk\b'],
        ProtocolType.UART: [r'\brx\b', r'\btx\b', r'\buart\b'],
        ProtocolType.GPIO: [r'\bgpio\b', r'\bpindir\b'],
        ProtocolType.HANDSHAKE: [r'\bhandshake\b', r'\back\b', r'\bnack\b'],
    }

    def __init__(self, rtl_content: str):
        self.raw_content = rtl_content
        # Strip comments for analysis
        self.content = re.sub(r'//.*', '', rtl_content)
        self.content = re.sub(r'/\*.*?\*/', '', self.content, flags=re.DOTALL)
        self.ports: Dict[str, Dict] = {}

        # Analysis results
        self.fsm_info: Optional[FSMInfo] = None
        self.datapath_info: DataPathInfo = DataPathInfo()
        self.control_info: ControlInfo = ControlInfo()
        self.protocols: List[ProtocolType] = []
        self.state_names: List[str] = []
        self.clocks: List[str] = []
        self.resets: List[str] = []
        self.always_blocks: List[Dict] = []
        self.parameters: Dict[str, int] = {}

    def analyze(self) -> Tuple[Dict[str, Dict], List[str], List[str]]:
        """Run all analysis passes. Returns (ports, clocks, resets)."""
        self._parse_ports()
        self._parse_parameters()
        self._parse_always_blocks()
        self._detect_protocols()
        self._extract_fsm()
        self._analyze_datapath()
        self._analyze_control_complexity()
        return self.ports, self.clocks, self.resets

    def _parse_ports(self):
        """Extract module ports with improved parsing."""
        content = self.content
        m_mod = re.search(r'module\s+\w+\s*\((.*?)\);', content, re.IGNORECASE | re.DOTALL)
        if not m_mod:
            return
        port_area = m_mod.group(1)

        for part in port_area.split(','):
            part = part.strip()
            if not part:
                continue
            # Parse both Verilog-1995/2001 port styles:
            # Style 1: input reg [3:0] a  (width after type)
            # Style 2: input [3:0] a      (width before type, Verilog 2001)
            port_pat_v1 = re.compile(
                r'(input|output|inout)\s+(?:signed\s+)?(reg|wire)?\s*(?:\[(\d+:\d+)\])?\s*(\w+)',
                re.IGNORECASE
            )
            port_pat_v2 = re.compile(
                r'(input|output|inout)\s+(?:\[(\d+:\d+)\])?\s*(?:signed\s+)?(reg|wire)?\s*(\w+)',
                re.IGNORECASE
            )
            m = port_pat_v1.match(part)
            uses_v2 = False
            if not m:
                m = port_pat_v2.match(part)
                uses_v2 = True
            if m:
                direction = m.group(1).lower()
                if uses_v2:
                    sig_type = (m.group(3) or "wire").strip()
                    width = (m.group(2) or "").strip()
                    name = m.group(4).strip()
                else:
                    sig_type = (m.group(2) or "wire").strip()
                    width = (m.group(3) or "").strip()
                    name = m.group(4).strip()
                self.ports[name] = {
                    "direction": direction,
                    "type": sig_type,
                    "width": width,
                    "width_bits": self._parse_width(width),
                }
                if direction == "input" and ("clk" in name.lower() or "clock" in name.lower()):
                    self.clocks.append(name)
                if direction == "input" and ("rst" in name.lower() or "reset" in name.lower()):
                    self.resets.append(name)

    def _parse_width(self, width_str: str) -> int:
        """Parse width like [31:0] -> 32, 3:0 -> 4, '' -> 1."""
        if not width_str:
            return 1
        # Strip optional brackets
        clean = width_str.strip().lstrip('[').rstrip(']')
        m = re.match(r'(\d+):(\d+)', clean)
        if m:
            return abs(int(m.group(1)) - int(m.group(2))) + 1
        return 1

    def _parse_parameters(self):
        """Extract parameters with numeric values."""
        param_pat = re.compile(
            r'parameter\s+(?:logic\s+)?(?:int\s+)?(\w+)\s*=\s*(\d+|\'[hdb][0-9a-fA-F]+)',
            re.IGNORECASE
        )
        for m in param_pat.finditer(self.content):
            val_str = m.group(2)
            if val_str.startswith("'"):
                # Verilog literal: 'hXX, 'dXX, 'bXX
                base = val_str[1].lower()
                num_str = val_str[2:]
                if base == 'h':
                    try:
                        self.parameters[m.group(1)] = int(num_str, 16)
                    except ValueError:
                        self.parameters[m.group(1)] = 0
                elif base == 'd':
                    try:
                        self.parameters[m.group(1)] = int(num_str)
                    except ValueError:
                        self.parameters[m.group(1)] = 0
                elif base == 'b':
                    try:
                        self.parameters[m.group(1)] = int(num_str, 2)
                    except ValueError:
                        self.parameters[m.group(1)] = 0
            else:
                try:
                    self.parameters[m.group(1)] = int(val_str)
                except ValueError:
                    pass

    def _parse_always_blocks(self):
        """Extract always blocks with type classification."""
        # Match always blocks more robustly
        block_pat = re.compile(
            r'always\s*(?:_comb|_ff|_latch)?\s*@\s*\((.*?)\)\s*',
            re.IGNORECASE | re.DOTALL
        )

        pos = 0
        while True:
            m = block_pat.search(self.content, pos)
            if not m:
                break
            sensitivity = m.group(1).strip()
            block_start = m.end()

            # Find matching begin..end or single statement
            brace_depth = 0
            block_end = block_start
            in_begin = False
            content_after = self.content[block_start:]

            # Check if there's a 'begin'
            begin_m = re.match(r'\s*begin\b', content_after)
            if begin_m:
                in_begin = True
                idx = begin_m.end()
            else:
                idx = 0

            # Find matching end
            while idx < len(content_after):
                ch = content_after[idx]
                if ch == ';' and not in_begin:
                    idx += 1
                    break
                if ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth -= 1
                if in_begin:
                    # Look for 'end' at word boundary
                    end_m = re.match(r'\bend\b', content_after[idx:])
                    if end_m and brace_depth == 0:
                        idx = idx + end_m.end()
                        break
                if not in_begin:
                    # For non-begin blocks, semicolon or key words terminate
                    if re.match(r'\b(always|endmodule|initial)\b', content_after[idx:]):
                        break
                idx += 1

            block_text = content_after[:idx].strip()
            block_end = block_start + idx

            # Classify block type
            block_type = AlwaysBlockType.SEQUENTIAL
            sens_has_clk = any(c in sensitivity.lower() for c in ['posedge', 'negedge'])
            if sens_has_clk:
                block_type = AlwaysBlockType.SEQUENTIAL
            elif '*' in sensitivity or ',' in sensitivity or len(sensitivity.split()) > 1:
                block_type = AlwaysBlockType.COMBINATIONAL
            else:
                block_type = AlwaysBlockType.LATCH

            self.always_blocks.append({
                "sensitivity": sensitivity,
                "text": block_text[:500],  # Truncate for memory
                "type": block_type,
                "full_match": m.group()[:50],  # First 50 chars for reference
            })

            pos = block_end

    def _detect_protocols(self):
        """Detect protocol interfaces from signal names."""
        all_signal_names = list(self.ports.keys())
        all_text = " ".join(all_signal_names)

        for proto, patterns in self.PROTOCOL_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, all_text, re.IGNORECASE))
            if matches >= len(patterns) * 0.5:  # At least 50% of patterns match
                self.protocols.append(proto)

        # Also check always block content for protocol patterns
        for block in self.always_blocks:
            text = block["text"]
            for proto, patterns in self.PROTOCOL_PATTERNS.items():
                if proto in self.protocols:
                    continue
                matches = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
                if matches >= len(patterns) * 0.5:
                    self.protocols.append(proto)

    def _extract_fsm(self):
        """Extract FSM: state register, states, encoding type, transitions."""

        fsm = FSMInfo()

        # 1. Find state register declaration
        state_reg_pat = re.compile(
            r'(reg|logic)\s*(?:\[(\d+:\d+)\])?\s*(state|cs|ns|current_state|next_state)\b',
            re.IGNORECASE
        )
        state_reg_m = state_reg_pat.search(self.content)
        if state_reg_m:
            fsm.state_reg_name = state_reg_m.group(3)
            width_str = state_reg_m.group(2) or ""
            fsm.width = self._parse_width(width_str)
        else:
            # Try to infer: look for assignments to state-like signals
            for name in ['state', 'cs', 'ns', 'current_state', 'next_state',
                         'state_r', 'state_next', 'fsm_state']:
                if re.search(rf'\b{name}\b', self.content):
                    fsm.state_reg_name = name
                    break

        # 2. Extract state names from localparams/parameters and case items
        localparam_pat = re.compile(
            r'localparam\s+(\w+)\s*=\s*(\d+|\'[hdb][0-9a-fA-F]+)\s*[;,]',
            re.IGNORECASE
        )
        for m in localparam_pat.finditer(self.content):
            val_str = m.group(2)
            # Decode value
            decoded = 0
            if val_str.startswith("'"):
                base = val_str[1].lower()
                num_str = val_str[2:]
                if base == 'h':
                    try:
                        decoded = int(num_str, 16)
                    except ValueError:
                        continue
                elif base == 'd':
                    try:
                        decoded = int(num_str)
                    except ValueError:
                        continue
                elif base == 'b':
                    try:
                        decoded = int(num_str, 2)
                    except ValueError:
                        continue
            else:
                try:
                    decoded = int(val_str)
                except ValueError:
                    continue
            self.parameters[m.group(1)] = decoded

        # 3. Find case statements with state-like names and extract state names
        if fsm.state_reg_name:
            case_pat = re.compile(
                rf'case\s*\(\s*{fsm.state_reg_name}\s*\)(.*?)\bendcase\b',
                re.IGNORECASE | re.DOTALL
            )
            case_m = case_pat.search(self.content)
            if case_m:
                case_body = case_m.group(1)
                # Extract case items (state names or parameter names)
                item_pat = re.compile(r'(\w+)\s*:', re.IGNORECASE)
                for item_m in item_pat.finditer(case_body):
                    candidate = item_m.group(1)
                    if candidate.upper() != "DEFAULT" and candidate not in fsm.states:
                        fsm.states.append(candidate)

        # Fallback: scan for FSM-like state names anywhere
        if not fsm.states:
            fsm_keywords = ['IDLE', 'WAIT', 'READ', 'WRITE', 'DONE', 'ERROR', 'BUSY',
                           'SEND', 'RECV', 'START', 'STOP', 'ADDR', 'DATA', 'ACK',
                           'INIT', 'HOLD', 'SETUP', 'ACCESS', 'TRANSFER']
            for kw in fsm_keywords:
                if re.search(rf'\b{kw}\b', self.content):
                    fsm.states.append(kw)

        # 4. Detect encoding type from state names and width
        if fsm.states:
            num_states = len(fsm.states)
            if fsm.width > 0 and fsm.width == num_states:
                fsm.encoding = FSMEncoding.ONE_HOT
            elif fsm.width > 0 and fsm.width >= (num_states.bit_length()):
                fsm.encoding = FSMEncoding.BINARY
            else:
                fsm.encoding = FSMEncoding.UNKNOWN

            # Check for gray encoding pattern in assignments
            if re.search(r'\bgray\b', self.content, re.IGNORECASE):
                fsm.encoding = FSMEncoding.GRAY

            self.state_names = fsm.states

        # 5. Extract transitions (from case statement or if-else chains)
        if fsm.state_reg_name and fsm.states:
            self._extract_fsm_transitions(fsm)

        self.fsm_info = fsm if fsm.states else None

    def _extract_fsm_transitions(self, fsm: FSMInfo):
        """Extract FSM transition conditions."""
        # Look for next_state assignments in always blocks
        ns_names = ['next_state', 'ns', f'next_{fsm.state_reg_name}']
        for ns in ns_names:
            ns_pat = re.compile(
                rf'{ns}\s*<=\s*(\w+)\s*;',
                re.IGNORECASE
            )
            for m in ns_pat.finditer(self.content):
                target = m.group(1)
                if target in self.parameters:
                    # Find the parameter value to map to state name
                    val = self.parameters[target]
                    # Reverse map: find which state has this value
                    for s_name, s_val in self.parameters.items():
                        if s_val == val and s_name in fsm.states:
                            fsm.transitions.append(("?", s_name, "?"))
                elif target in fsm.states:
                    fsm.transitions.append(("?", target, "?"))

    def _analyze_datapath(self):
        """Analyze data path: widths, operators, muxes, etc."""
        dp = self.datapath_info

        # Width distribution from ports
        for name, info in self.ports.items():
            w = info.get("width_bits", 1)
            dp.widths[w] = dp.widths.get(w, 0) + 1
            if w > dp.largest_width:
                dp.largest_width = w

        # Detect muxes
        mux_count = len(re.findall(r'\bcase\b', self.content))
        ternary_count = len(re.findall(r'\?\s*:', self.content))
        dp.has_mux = (mux_count + ternary_count) > 2
        dp.mux_inputs = mux_count + ternary_count

        # Detect arithmetic operators
        dp.has_adder = bool(re.search(r'[+\-]', self.content))
        dp.has_shifter = bool(re.search(r'[<>][<>=]', self.content))
        dp.has_comparator = bool(re.search(r'(>=?|<=?|==?!=)', self.content))
        dp.has_multiplier = bool(re.search(r'\*', self.content))

        # Detect memory (reg arrays)
        mem_pat = re.compile(r'(reg|logic)\s*\[.*?\]\s*\w+\s*\[.*?\]\s*;', re.IGNORECASE)
        dp.has_memory = bool(mem_pat.search(self.content))

    def _analyze_control_complexity(self):
        """Analyze control logic complexity."""
        ci = self.control_info
        content = self.content

        ci.always_blocks_total = len(self.always_blocks)
        for b in self.always_blocks:
            if b["type"] == AlwaysBlockType.SEQUENTIAL:
                ci.sequential_blocks += 1
            elif b["type"] == AlwaysBlockType.COMBINATIONAL:
                ci.combinational_blocks += 1
            else:
                pass  # latch

        # Count nested if statements
        if_count = len(re.findall(r'\bif\s*\(', content))
        ci.nested_ifs = if_count

        # Count case statements and items
        case_m = re.findall(r'\bcase\b', content)
        ci.case_statements = len(case_m)

        # Count case items (lines with ':')
        case_items = len(re.findall(r'^\s*\w+\s*:', content, re.MULTILINE))
        ci.case_items = case_items

        # Count condition complexity (average conditions per if statement)
        cond_count = len(re.findall(r'(&&|\|\|)', content))
        ci.condition_complexity = cond_count // max(if_count, 1)

        # Pipeline detection
        pipe_pat = re.compile(r'(pipeline|pipe_stage|stage\d)', re.IGNORECASE)
        ci.has_pipeline = bool(pipe_pat.search(content))
        if ci.has_pipeline:
            stages_m = re.findall(r'stage(\d+)', content)
            if stages_m:
                ci.pipeline_stages = max(int(s) for s in stages_m)

        # Counter detection
        cnt_pat = re.compile(r'(counter|cnt)\s*(<=|=)\s*\w+\s*[+\-]\s*1', re.IGNORECASE)
        ci.has_counter = bool(cnt_pat.search(content))
        if ci.has_counter:
            cnt_width_m = re.search(r'(reg|logic)\s*\[(\d+):\d+\]\s*(counter|cnt)\b', content, re.IGNORECASE)
            if cnt_width_m:
                ci.counter_bits = int(cnt_width_m.group(2)) + 1

        ci.has_fsm = self.fsm_info is not None

        self.control_info = ci

    def compute_complexity_score(self) -> int:
        """Compute overall design complexity (1-10)."""
        score = 1
        ci = self.control_info
        dp = self.datapath_info

        # FSM complexity
        if self.fsm_info and len(self.fsm_info.states) >= 3:
            score += 1
        if self.fsm_info and len(self.fsm_info.states) >= 6:
            score += 1

        # Data path complexity
        if dp.largest_width > 16:
            score += 1
        if dp.largest_width > 32:
            score += 1
        if dp.has_multiplier:
            score += 1
        if dp.has_memory:
            score += 1

        # Control complexity
        if ci.sequential_blocks >= 3:
            score += 1
        if ci.nested_ifs >= 10:
            score += 1
        if ci.case_statements > 2:
            score += 1
        if ci.has_pipeline:
            score += 1
        if ci.has_counter:
            score += 1

        # Protocol complexity
        if len(self.protocols) >= 2:
            score += 1
        if ProtocolType.AXI in self.protocols or ProtocolType.I2C in self.protocols:
            score += 1

        # Port count
        if len(self.ports) >= 20:
            score += 1

        return min(score, 10)


# ── Differentiated Test Generator ────────────────────────────────────────────

class DifferentiatedTestGenerator:
    """
    Generates verification tests tailored to the specific design topology.
    No more "one-per-output" generic tests.
    """

    def __init__(self, analyzer: DeepRTLAnalyzer, spec_text: str = ""):
        self.analyzer = analyzer
        self.spec_text = spec_text
        self.test_id = 0

    def generate(self) -> VerificationPlan:
        """Generate a complete verification plan with differentiated tests."""
        # Run analysis if not already done
        ports, clocks, resets = self.analyzer.analyze()
        complexity = self.analyzer.compute_complexity_score()

        module_name = self._get_module_name()

        plan = VerificationPlan(
            module_name=module_name,
            spec_summary=self.spec_text or f"Auto-generated from RTL analysis",
            clocks=clocks,
            resets=resets,
            signals_under_test=list(ports.keys()),
            fsm_states=self.analyzer.state_names,
            fsm_info=self.analyzer.fsm_info,
            datapath_info=self.analyzer.datapath_info,
            control_info=self.analyzer.control_info,
            protocols=self.analyzer.protocols,
            design_complexity_score=complexity,
        )

        # ── Generate tests based on actual design topology ──
        ci = self.analyzer.control_info
        dp = self.analyzer.datapath_info
        fsm = self.analyzer.fsm_info
        protocols = self.analyzer.protocols

        # 1. Reset test (always present)
        self._add_reset_test(plan)

        # 2. FSM tests (only if FSM detected - different granularity based on complexity)
        if fsm and fsm.states:
            self._add_fsm_tests(plan, fsm)

        # 3. Protocol-specific tests (based on detected protocols)
        self._add_protocol_tests(plan, protocols, ports)

        # 4. Data path tests (based on actual data path topology)
        self._add_datapath_tests(plan, dp, ports)

        # 5. Control logic tests (based on control complexity)
        self._add_control_tests(plan, ci)

        # 6. Interface handshake tests (if valid/ready detected)
        if self._has_handshake(ports):
            self._add_handshake_tests(plan, ports)

        # 7. Pipeline tests (if pipeline detected)
        if ci and ci.has_pipeline:
            self._add_pipeline_tests(plan, ci)

        # 8. Concurrent access / conflict tests (for designs with multiple interfaces)
        if len(protocols) >= 2 or len(self.analyzer.always_blocks) >= 5:
            self._add_concurrent_tests(plan)

        # 9. Error injection (scaled by complexity)
        self._add_error_tests(plan, complexity)

        # 10. Coverage-driven random tests (scaled by complexity)
        self._add_random_tests(plan, complexity)

        # ── Generate differentiated coverage points ──
        self._add_coverage_points(plan, ports, fsm, dp, ci)

        return plan

    def _get_module_name(self) -> str:
        m = re.search(r'module\s+(\w+)', self.analyzer.raw_content)
        return m.group(1) if m else "unknown"

    def _has_handshake(self, ports: Dict) -> bool:
        names = list(ports.keys())
        text = " ".join(names)
        return any(kw in text.lower() for kw in ['valid', 'ready', 'handshake'])

    # ── Test adders ──────────────────────────────────────────────────────────

    def _add_test(self, plan: VerificationPlan, name: str, test_type: TestType,
                  desc: str, priority: int, cov_points: List[str],
                  deps: Optional[List[int]] = None, rationale: str = ""):
        self.test_id += 1
        plan.add_test(TestScenario(
            id=self.test_id,
            name=name,
            test_type=test_type,
            description=desc,
            priority=priority,
            coverage_points=cov_points,
            dependencies=deps or [],
            rationale=rationale,
        ))

    def _add_reset_test(self, plan: VerificationPlan):
        rst = plan.resets[0] if plan.resets else "rst_n"
        plan.constraints.append(f"Reset: {rst} active low")
        self._add_test(plan,
            name="Reset Sequence",
            test_type=TestType.DIRECTED,
            desc=f"Assert and de-assert {rst}, verify all registers reach reset values, FSM enters IDLE",
            priority=1,
            cov_points=["reset_assert", "post_reset_registers", "post_reset_fsm"],
            rationale="Foundation test: every verification starts with reset correctness")

        # If we have FSM and resets, add reset-while-in-state test
        if plan.fsm_states and len(plan.fsm_states) >= 2:
            self._add_test(plan,
                name="Reset While Active",
                test_type=TestType.RESET_DOMAIN,
                desc=f"Assert {rst} while FSM is in non-IDLE state, verify clean recovery",
                priority=2,
                cov_points=["reset_active_mid_state", "reset_recovery"],
                deps=[1],
                rationale="Reset while active is a common real-world scenario")

    def _add_fsm_tests(self, plan: VerificationPlan, fsm: FSMInfo):
        n = len(fsm.states)
        # Different behavior based on FSM size:
        if n <= 3:
            # Simple FSM: exhaustive transition test
            for s in fsm.states:
                self._add_test(plan,
                    name=f"FSM State: {s}",
                    test_type=TestType.DIRECTED,
                    desc=f"Verify FSM reaches and operates correctly in {s} state",
                    priority=2,
                    cov_points=[f"fsm_{s}_reached", f"fsm_{s}_outputs"],
                    rationale=f"State {s} must be reachable and produce correct outputs")
            # All transitions
            for i in range(n - 1):
                self._add_test(plan,
                    name=f"FSM Transition: {fsm.states[i]} -> {fsm.states[i+1]}",
                    test_type=TestType.SEQUENTIAL,
                    desc=f"Verify FSM transitions from {fsm.states[i]} to {fsm.states[i+1]}",
                    priority=2,
                    cov_points=[f"fsm_trans_{fsm.states[i]}_{fsm.states[i+1]}"],
                    rationale="Each state transition is a verification point")
        else:
            # Complex FSM: group and prioritize
            critical_states = [s for s in fsm.states if s.upper() in ('IDLE', 'ERROR', 'DONE', 'BUSY')]
            for s in critical_states:
                self._add_test(plan,
                    name=f"FSM Critical State: {s}",
                    test_type=TestType.DIRECTED,
                    desc=f"Verify FSM {s} state entry/exit conditions and outputs",
                    priority=1,
                    cov_points=[f"fsm_{s}_entry", f"fsm_{s}_exit", f"fsm_{s}_outputs"],
                    rationale=f"{s} is a critical state in the FSM")

            # Full state coverage
            self._add_test(plan,
                name="FSM All States Reachable",
                test_type=TestType.DIRECTED,
                desc=f"Verify all {n} FSM states are reachable through legal transitions",
                priority=1,
                cov_points=["fsm_all_states", "fsm_no_deadlock"],
                rationale="All FSM states must be reachable; unreachable states indicate dead code")

            # Transition pairs (not just adjacent)
            trans_tested = set()
            for i in range(n):
                for j in range(n):
                    if i != j and (i, j) not in trans_tested:
                        # Test at most n*2 transition pairs (not all n^2)
                        if len(trans_tested) >= min(n * 2, n * 3 // 2):
                            break
                        self._add_test(plan,
                            name=f"FSM Transition: {fsm.states[i]} -> {fsm.states[j]}",
                            test_type=TestType.SEQUENTIAL,
                            desc=f"Verify FSM transitions from {fsm.states[i]} to {fsm.states[j]}",
                            priority=3,
                            cov_points=[f"fsm_trans_{fsm.states[i]}_{fsm.states[j]}"],
                            rationale="Non-adjacent state transitions test FSM correctness")
                        trans_tested.add((i, j))

        # FSM safety test (if error state exists)
        if 'ERROR' in [s.upper() for s in fsm.states]:
            self._add_test(plan,
                name="FSM Error State Recovery",
                test_type=TestType.ERROR,
                desc="Force FSM into ERROR state, verify recovery to IDLE",
                priority=2,
                cov_points=["fsm_error_entry", "fsm_error_recovery"],
                rationale="Error state recovery is critical for robust designs")

        # Formal property for FSM (for complex FSMs)
        if n >= 4 or fsm.encoding == FSMEncoding.ONE_HOT:
            self._add_test(plan,
                name="FSM One-Hot Safety Check",
                test_type=TestType.FORMAL,
                desc=f"Verify one-hot FSM safety: exactly one state active, no illegal states",
                priority=3,
                cov_points=["fsm_one_hot_safe", "fsm_no_illegal"],
                rationale="One-hot FSMs must never have 0 or 2+ states active simultaneously")

    def _add_protocol_tests(self, plan: VerificationPlan, protocols: List[ProtocolType], ports: Dict):
        for proto in protocols:
            if proto == ProtocolType.VALID_READY:
                self._add_test(plan,
                    name="Valid/Ready Handshake Basic",
                    test_type=TestType.PROTOCOL,
                    desc="Single-beat valid/ready handshake: valid asserted, wait for ready, data transferred",
                    priority=1,
                    cov_points=["handshake_basic", "valid_assert", "ready_assert"],
                    rationale="Valid/ready is the foundation of most bus protocols")

                self._add_test(plan,
                    name="Valid/Ready Backpressure",
                    test_type=TestType.PROTOCOL,
                    desc="Ready de-asserted while valid asserted, verify data held correctly",
                    priority=2,
                    cov_points=["handshake_backpressure", "valid_wait", "data_hold"],
                    rationale="Backpressure is the most common scenario for valid/ready interfaces")

                self._add_test(plan,
                    name="Valid/Ready Pipeline",
                    test_type=TestType.PROTOCOL,
                    desc="Pipelined valid/ready: multiple transfers without bubbles",
                    priority=2,
                    cov_points=["handshake_pipeline", "pipeline_throughput"],
                    rationale="Pipelined operation is critical for performance verification")

            elif proto == ProtocolType.I2C:
                self._add_i2c_tests(plan)

            elif proto == ProtocolType.SPI:
                self._add_test(plan,
                    name="SPI Basic Transfer",
                    test_type=TestType.PROTOCOL,
                    desc="Single SPI transfer: CS assert, clock data, CS de-assert",
                    priority=1,
                    cov_points=["spi_basic", "spi_cs", "spi_clk"],
                    rationale="SPI basic transfer verification")

                self._add_test(plan,
                    name="SPI Multiple Transfers",
                    test_type=TestType.SEQUENTIAL,
                    desc="Back-to-back SPI transfers with minimal CS high time",
                    priority=2,
                    cov_points=["spi_back_to_back"],
                    rationale="Multiple transfers test SPI controller robustness")

            elif proto == ProtocolType.GPIO:
                self._add_test(plan,
                    name="GPIO Output Toggle",
                    test_type=TestType.DIRECTED,
                    desc="Toggle all GPIO output pins through all possible values",
                    priority=2,
                    cov_points=["gpio_output_toggle"],
                    rationale="GPIO output functionality verification")

                self._add_test(plan,
                    name="GPIO Input Capture",
                    test_type=TestType.DIRECTED,
                    desc="Apply external GPIO inputs, verify capture in status register",
                    priority=2,
                    cov_points=["gpio_input_capture"],
                    rationale="GPIO input must be correctly sampled and readable")

                self._add_test(plan,
                    name="GPIO Interrupt Edge Detect",
                    test_type=TestType.PROTOCOL,
                    desc="Configure GPIO for rising/falling edge interrupt, toggle input, verify interrupt",
                    priority=1,
                    cov_points=["gpio_intr_rising", "gpio_intr_falling"],
                    rationale="GPIO interrupt edge detection is a common use case")

            elif proto in (ProtocolType.AXI, ProtocolType.AXI_STREAM):
                self._add_test(plan,
                    name="AXI Basic Write/Read",
                    test_type=TestType.PROTOCOL,
                    desc="AXI single-beat write and read with full handshake",
                    priority=1,
                    cov_points=["axi_write", "axi_read"],
                    rationale="AXI basic transaction verification")

                self._add_test(plan,
                    name="AXI Burst Transfer",
                    test_type=TestType.SEQUENTIAL,
                    desc="AXI burst write and read of various lengths (2,4,8,16 beats)",
                    priority=1,
                    cov_points=["axi_burst_write", "axi_burst_read"],
                    rationale="AXI burst mode is the primary data transfer mechanism")

                self._add_test(plan,
                    name="AXI Out-of-Order Completion",
                    test_type=TestType.PROTOCOL,
                    desc="Multiple outstanding AXI transactions with out-of-order responses",
                    priority=3,
                    cov_points=["axi_ooo"],
                    rationale="Out-of-order completion is a key AXI feature that must be verified")

    def _add_i2c_tests(self, plan: VerificationPlan):
        """I2C-specific protocol tests."""
        i2c_tests = [
            ("I2C START Condition", TestType.PROTOCOL, 1,
             "Generate START condition (SDA falling while SCL high), verify on bus",
             ["i2c_start", "i2c_start_timing"]),
            ("I2C STOP Condition", TestType.PROTOCOL, 1,
             "Generate STOP condition (SDA rising while SCL high), verify on bus",
             ["i2c_stop", "i2c_stop_timing"]),
            ("I2C Write Byte", TestType.PROTOCOL, 1,
             "Master write: START + addr(W) + ACK + data + ACK + STOP, verify ACK received",
             ["i2c_write_byte", "i2c_ack_rx", "i2c_scl_toggle"]),
            ("I2C Read Byte", TestType.PROTOCOL, 1,
             "Master read: START + addr(R) + ACK + data(NACK) + STOP, verify rx data",
             ["i2c_read_byte", "i2c_nack_tx", "i2c_rx_data"]),
            ("I2C Repeated START", TestType.PROTOCOL, 2,
             "Combined transaction: RSTART + addr(W) + data + RSTART + addr(R) + data + STOP",
             ["i2c_repeated_start", "i2c_combined_transaction"]),
            ("I2C Multi-Byte Transfer", TestType.SEQUENTIAL, 2,
             "Multi-byte write/read: 8 bytes with auto-increment addressing",
             ["i2c_multibyte_write", "i2c_multibyte_read", "i2c_addr_increment"]),
            ("I2C NACK Handling", TestType.PROTOCOL, 2,
             "Master receives NACK from slave, verify correct stop generation and status",
             ["i2c_nack_handling", "i2c_nack_stop"]),
            ("I2C Arbitration Lost", TestType.ERROR, 2,
             "Multi-master arbitration: two masters driving simultaneously, verify arb lost flag",
             ["i2c_arbitration_lost", "i2c_arb_recovery"]),
            ("I2C Clock Stretching", TestType.TIMING, 2,
             "Slave holds SCL low (clock stretching), verify master waits and resumes",
             ["i2c_clock_stretch", "i2c_stretch_timeout"]),
            ("I2C FIFO Full/Empty", TestType.FIFO, 2,
             "Fill TX FIFO to threshold/overflow, drain RX FIFO to empty, verify flags",
             ["i2c_fifo_tx_full", "i2c_fifo_rx_empty", "i2c_fifo_threshold"]),
        ]

        for name, ttype, pri, desc, cov_pts in i2c_tests:
            self._add_test(plan, name=name, test_type=ttype, desc=desc,
                          priority=pri, cov_points=cov_pts,
                          rationale=f"I2C protocol test: {desc[:40]}")

    def _add_datapath_tests(self, plan: VerificationPlan, dp: DataPathInfo, ports: Dict):
        """Data path tests based on actual topology."""

        # Width-based boundary tests (only for wide signals, not one-per-port)
        if dp.largest_width >= 8:
            # Find the widest ports for targeted boundary tests
            wide_ports = [(n, i) for n, i in ports.items()
                         if i.get("width_bits", 1) == dp.largest_width]
            for name, info in wide_ports[:3]:  # Max 3 boundary tests
                w = info["width_bits"]
                self._add_test(plan,
                    name=f"Data Path Boundary: {name}",
                    test_type=TestType.CORNER,
                    desc=f"Test {name} ({w}-bit) boundary values: 0, all-1s, MSB toggled, LSB toggled, alternating pattern",
                    priority=2 if info["direction"] == "output" else 3,
                    cov_points=[f"boundary_{name}_zero", f"boundary_{name}_all1",
                               f"boundary_{name}_msb", f"boundary_{name}_pattern"],
                    rationale=f"{w}-bit signal requires comprehensive boundary testing")

        # Arithmetic tests
        if dp.has_adder:
            input_names = [n for n, i in ports.items() if i["direction"] == "input" and i.get("width_bits", 1) >= 4]
            self._add_test(plan,
                name="Adder/Subtractor Coverage",
                test_type=TestType.CORNER,
                desc="Test arithmetic: 0+0, max+max, overflow, underflow, alternating signs if signed",
                priority=2,
                cov_points=["adder_zero", "adder_overflow", "adder_underflow"],
                rationale="Arithmetic overflow is a classic hardware bug")

        if dp.has_shifter:
            self._add_test(plan,
                name="Shifter Coverage",
                test_type=TestType.CORNER,
                desc="Test shift operations: shift 0, shift full width, shift 1, bidirectional",
                priority=3,
                cov_points=["shifter_zero", "shifter_full", "shifter_overflow"],
                rationale="Shifters can lose data at boundary conditions")

        if dp.has_multiplier:
            self._add_test(plan,
                name="Multiplier Coverage",
                test_type=TestType.CORNER,
                desc="Test multiplication: 0*max, max*max, negative*negative (if signed), overflow",
                priority=2,
                cov_points=["mult_zero", "mult_max", "mult_overflow"],
                rationale="Multiplier overflow and saturation must be verified")

        if dp.has_memory:
            self._add_test(plan,
                name="Memory Array Access",
                test_type=TestType.CORNER,
                desc="Test memory array: single read/write, all addresses, address wraparound",
                priority=2,
                cov_points=["mem_single", "mem_all_addr", "mem_wraparound"],
                rationale="Memory arrays must be tested for address decode correctness")

        # Data path comparison test
        if dp.has_comparator:
            self._add_test(plan,
                name="Comparator Boundary",
                test_type=TestType.CORNER,
                desc="Test comparisons: equal, not-equal, greater-than, less-than at boundary values",
                priority=3,
                cov_points=["cmp_equal", "cmp_neq", "cmp_gt_lt"],
                rationale="Comparison operators need boundary testing for correct results")

    def _add_handshake_tests(self, plan: VerificationPlan, ports: Dict):
        """Handshake interface tests."""
        # Find valid/ready pairs
        valid_sigs = [n for n in ports if 'valid' in n.lower()]
        ready_sigs = [n for n in ports if 'ready' in n.lower()]

        if valid_sigs and ready_sigs:
            self._add_test(plan,
                name="Handshake: Valid Toggle Without Ready",
                test_type=TestType.CORNER,
                desc="Assert valid while ready stays low for extended cycles, verify data held",
                priority=2,
                cov_points=["valid_without_ready", "data_hold_stability"],
                rationale="Data must remain stable while waiting for ready")

            self._add_test(plan,
                name="Handshake: Ready Toggle Without Valid",
                test_type=TestType.CORNER,
                desc="Assert ready while valid stays low, verify no spurious transfer",
                priority=3,
                cov_points=["ready_without_valid", "no_false_transfer"],
                rationale="Ready without valid must never trigger a transfer")

            self._add_test(plan,
                name="Handshake: Simultaneous Valid+Ready",
                test_type=TestType.DIRECTED,
                desc="Valid and ready asserted in same cycle, verify single-cycle transfer",
                priority=2,
                cov_points=["handshake_simultaneous", "single_cycle_transfer"],
                rationale="Zero-wait-state transfer is the critical path scenario")

    def _add_pipeline_tests(self, plan: VerificationPlan, ci: ControlInfo):
        """Pipeline-specific tests."""
        stages = ci.pipeline_stages or 3
        self._add_test(plan,
            name="Pipeline Fill and Drain",
            test_type=TestType.PIPELINE,
            desc=f"Fill {stages}-stage pipeline with data, verify correct output after {stages} cycles",
            priority=2,
            cov_points=[f"pipeline_fill_{stages}", "pipeline_drain", "pipeline_latency"],
            rationale="Pipeline fill/drain verifies correct stage behavior")

        self._add_test(plan,
            name="Pipeline Stall/Bubble",
            test_type=TestType.PIPELINE,
            desc="Insert stall into pipeline, verify bubbles propagate correctly",
            priority=2,
            cov_points=["pipeline_stall", "pipeline_bubble"],
            rationale="Pipeline stalling is a critical correctness scenario")

        self._add_test(plan,
            name="Pipeline Hazards",
            test_type=TestType.PIPELINE,
            desc="Data hazards between pipeline stages (read-after-write, write-after-read)",
            priority=2,
            cov_points=["pipeline_hazard_raw", "pipeline_hazard_war"],
            rationale="Pipeline hazards are a common source of subtle bugs")

    def _add_concurrent_tests(self, plan: VerificationPlan):
        """Concurrent access tests for multi-interface designs."""
        self._add_test(plan,
            name="Concurrent Interface Access",
            test_type=TestType.CONCURRENT,
            desc="Simultaneous access through multiple interfaces, verify no data corruption",
            priority=2,
            cov_points=["concurrent_access", "no_corruption", "arbitration_fairness"],
            rationale="Concurrent access from multiple interfaces is a worst-case scenario")

        self._add_test(plan,
            name="Simultaneous Read/Write to Same Address",
            test_type=TestType.CONCURRENT,
            desc="Read and write same register simultaneously, verify deterministic behavior",
            priority=3,
            cov_points=["same_addr_conflict", "rw_determinism"],
            rationale="Read-write conflict to same address must have deterministic behavior")

    def _add_control_tests(self, plan: VerificationPlan, ci: ControlInfo):
        """Control logic tests based on complexity."""
        if ci.nested_ifs >= 5:
            self._add_test(plan,
                name="Complex Condition Coverage",
                test_type=TestType.CORNER,
                desc=f"Exercise all {ci.nested_ifs} conditional branches with combinatorial input values",
                priority=2,
                cov_points=["condition_branch_coverage", "all_if_else_paths"],
                rationale=f"{ci.nested_ifs} conditional branches must be exhaustively tested")

        if ci.case_statements >= 2:
            self._add_test(plan,
                name="Default Case Coverage",
                test_type=TestType.CORNER,
                desc="Drive case statement with values NOT covered by any case item, verify default path",
                priority=2,
                cov_points=["case_default_path", "case_x_propagation"],
                rationale="Default case (or lack thereof) is a common source of synthesis-sim mismatch")

        if ci.has_counter:
            self._add_test(plan,
                name="Counter Wrap/Action",
                test_type=TestType.CORNER,
                desc=f"Test {ci.counter_bits}-bit counter: max value, wrap to zero, overflow behavior",
                priority=2,
                cov_points=["counter_max", "counter_wrap", "counter_overflow"],
                rationale="Counter overflow is a classic source of bugs")

    def _add_error_tests(self, plan: VerificationPlan, complexity: int):
        """Error injection tests scaled by design complexity."""
        # Basic error tests (always present)
        self._add_test(plan,
            name="X-Propagation Check",
            test_type=TestType.ERROR,
            desc="Drive X on inputs, verify X doesn't propagate to outputs or cause metastability",
            priority=3,
            cov_points=["x_propagation", "x_isolation"],
            rationale="X-propagation can mask real bugs in simulation")

        self._add_test(plan,
            name="Illegal Input Sequences",
            test_type=TestType.ERROR,
            desc="Apply input sequences that violate protocol timing/ordering, verify graceful handling",
            priority=3,
            cov_points=["illegal_sequences", "error_recovery"],
            rationale="Designs must handle illegal inputs gracefully, not hang or produce X/Z")

        # Additional error tests for complex designs
        if complexity >= 5:
            self._add_test(plan,
                name="Timing Violation: Setup/Hold",
                test_type=TestType.TIMING,
                desc="Apply input transitions near clock edge, verify no metastability propagation",
                priority=4,
                cov_points=["timing_violation", "meta_stability"],
                rationale="Timing violations in RTL simulation may match or differ from silicon behavior")

    def _add_random_tests(self, plan: VerificationPlan, complexity: int):
        """Coverage-driven random tests."""
        base_random = 2 if complexity >= 5 else 1
        for i in range(base_random):
            seed = i + 1
            self._add_test(plan,
                name=f"Constrained Random Test (seed={seed})",
                test_type=TestType.CONSTRAINED_RANDOM,
                desc=f"Randomized transactions with constraints, seed {seed}, {4 + complexity} cycles",
                priority=3,
                cov_points=[f"random_seed_{seed}", "random_corner_hit"],
                rationale="Constrained random with different seeds increases coverage diversity")

    # ── Coverage Points ──────────────────────────────────────────────────────

    def _add_coverage_points(self, plan: VerificationPlan, ports: Dict,
                             fsm: Optional[FSMInfo], dp: DataPathInfo, ci: ControlInfo):
        """Generate differentiated coverage points."""

        # 1. Toggle coverage for all ports (but with different priorities)
        for name, info in ports.items():
            w = info.get("width_bits", 1)
            plan.coverage_points.append(CoveragePoint(
                name=f"toggle_{name}",
                target=CoverageTarget.TOGGLE,
                description=f"Toggle coverage for {name} ({w}-bit)",
                weight=3 if info["direction"] == "output" else 1,
                bin_count=w * 2,
                rtl_context=f"port {name}",
            ))

        # 2. FSM coverage
        if fsm and fsm.states:
            plan.coverage_points.append(CoveragePoint(
                name="fsm_all_states",
                target=CoverageTarget.FSM,
                description=f"All {len(fsm.states)} FSM states visited",
                weight=5,
                bin_count=len(fsm.states),
                rtl_context=f"FSM: {fsm.state_reg_name}",
            ))
            for s in fsm.states:
                plan.coverage_points.append(CoveragePoint(
                    name=f"fsm_{s}",
                    target=CoverageTarget.FSM,
                    description=f"FSM state {s} visited",
                    weight=3,
                    bin_count=1,
                    rtl_context=f"FSM: {fsm.state_reg_name} state={s}",
                ))
                plan.coverage_points.append(CoveragePoint(
                    name=f"fsm_{s}_outputs",
                    target=CoverageTarget.FSM,
                    description=f"Outputs from FSM state {s}",
                    weight=2,
                    bin_count=1,
                    rtl_context=f"FSM output decode when state={s}",
                ))

        # 3. Condition coverage (for complex combinational logic)
        if ci.condition_complexity >= 2:
            plan.coverage_points.append(CoveragePoint(
                name="condition_coverage",
                target=CoverageTarget.CONDITION,
                description=f"Condition coverage for {ci.nested_ifs} if statements with compound conditions",
                weight=3,
                bin_count=ci.nested_ifs * 2,
                rtl_context="combinational logic conditions",
            ))

        # 4. Case coverage
        if ci.case_statements > 0:
            plan.coverage_points.append(CoveragePoint(
                name="case_coverage",
                target=CoverageTarget.BRANCH,
                description=f"Case statement coverage: {ci.case_items} items across {ci.case_statements} cases",
                weight=3,
                bin_count=ci.case_items + ci.case_statements,  # +1 for default
                rtl_context="case statements",
            ))

        # 5. Data path coverage (for wide signals)
        if dp.largest_width >= 8:
            plan.coverage_points.append(CoveragePoint(
                name="datapath_boundary_coverage",
                target=CoverageTarget.FUNCTIONAL,
                description=f"Data path boundary coverage: zero, max, MSB, alternating patterns",
                weight=2,
                bin_count=4,
                rtl_context=f"widest signals ({dp.largest_width}-bit)",
            ))

        # 6. Cross coverage (meaningful pairs, not just output×output)
        #   a) Control × data pairs
        inputs = [n for n, i in ports.items() if i["direction"] == "input"]
        outputs = [n for n, i in ports.items() if i["direction"] == "output"]

        for ctrl in ['valid', 'ready', 'enable', 'sel', 'wr', 'rd']:
            ctrl_sigs = [n for n in inputs if ctrl in n.lower()]
            for ctrl_sig in ctrl_sigs[:2]:  # Max 2 per control type
                for data_sig in outputs[:4]:  # Max 4 data signals
                    plan.cross_coverage.append((ctrl_sig, data_sig))
                    plan.coverage_points.append(CoveragePoint(
                        name=f"cross_{ctrl_sig}_{data_sig}",
                        target=CoverageTarget.CROSS,
                        description=f"Cross coverage: {ctrl_sig} × {data_sig}",
                        weight=2,
                        cross_with=data_sig,
                        rtl_context=f"control × data cross",
                    ))

    def render_markdown(self, plan: VerificationPlan) -> str:
        """Render plan as markdown with analysis summary."""
        lines = []
        lines.append(f"# Verification Plan: {plan.module_name}")
        lines.append("")
        lines.append(f"**Spec:** {plan.spec_summary or 'N/A'}")
        lines.append(f"**Complexity Score:** {plan.design_complexity_score}/10")
        lines.append("")

        # Design Analysis
        lines.append("## Design Analysis")
        lines.append("")
        in_ports = len([s for s in plan.signals_under_test
                        if s in self.analyzer.ports and self.analyzer.ports[s].get('direction') == 'input'])
        out_ports = len([s for s in plan.signals_under_test
                         if s in self.analyzer.ports and self.analyzer.ports[s].get('direction') == 'output'])
        lines.append(f"- **Ports:** {len(plan.signals_under_test)} ({in_ports} inputs, {out_ports} outputs)")

        if self.analyzer.fsm_info:
            fi = self.analyzer.fsm_info
            lines.append(f"- **FSM:** {len(fi.states)} states, encoding={fi.encoding.value}, "
                        f"register={fi.state_reg_name}")
            lines.append(f"  - States: {', '.join(fi.states)}")
        else:
            lines.append(f"- **FSM:** Not detected")

        dp = self.analyzer.datapath_info
        lines.append(f"- **Data Path:** {dp.largest_width}-bit max, "
                    f"mux={dp.has_mux}, adder={dp.has_adder}, "
                    f"shifter={dp.has_shifter}, comparator={dp.has_comparator}, "
                    f"mult={dp.has_multiplier}, memory={dp.has_memory}")

        ci = self.analyzer.control_info
        lines.append(f"- **Control:** {ci.sequential_blocks} seq + {ci.combinational_blocks} combo always blocks, "
                    f"{ci.nested_ifs} conditions, {ci.case_statements} cases, "
                    f"{'pipeline' if ci.has_pipeline else 'no pipeline'}, "
                    f"{'counter' if ci.has_counter else 'no counter'}")

        if self.analyzer.protocols:
            lines.append(f"- **Protocols:** {', '.join(p.value for p in self.analyzer.protocols)}")

        lines.append(f"- **Clocks:** {', '.join(plan.clocks) if plan.clocks else 'None'}")
        lines.append(f"- **Resets:** {', '.join(plan.resets) if plan.resets else 'None'}")
        lines.append("")

        # Test Scenarios
        lines.append("## Test Scenarios")
        lines.append("")
        lines.append("| # | Name | Type | Priority | Coverage Points | Rationale |")
        lines.append("|---|------|------|----------|-----------------|-----------|")
        for t in plan.test_scenarios:
            cov_str = ", ".join(t.coverage_points[:3])
            if len(t.coverage_points) > 3:
                cov_str += "…"
            rationale = t.rationale[:40] + "…" if len(t.rationale) > 40 else t.rationale
            lines.append(f"| {t.id} | {t.name} | {t.test_type.value} | {t.priority} | {cov_str} | {rationale} |")
        lines.append("")

        # Coverage Points
        lines.append("## Coverage Points")
        lines.append("")
        lines.append("| Point | Target | Description | Weight | Bins | Context |")
        lines.append("|-------|--------|-------------|--------|------|---------|")
        for cp in plan.coverage_points:
            marker = "[✓]" if cp.hit else "[ ]"
            lines.append(f"| {marker} {cp.name} | {cp.target.value} | {cp.description} | {cp.weight} | {cp.bin_count} | {cp.rtl_context} |")
        lines.append("")

        # Cross Coverage
        if plan.cross_coverage:
            lines.append("## Cross Coverage Pairs")
            lines.append("")
            for a, b in plan.cross_coverage:
                lines.append(f"- `{a}` × `{b}`")
            lines.append("")

        # Summary
        coverage = plan.compute_coverage()
        lines.append("## Coverage Summary")
        lines.append(f"- **Total Points:** {coverage['total_points']}")
        lines.append(f"- **Hit:** {coverage['hit']}")
        lines.append(f"- **Coverage:** {coverage['coverage_pct']}%")
        lines.append("")

        return "\n".join(lines)


# ── Main entry point ─────────────────────────────────────────────────────────

class PlanGenerator:
    """
    Backward-compatible wrapper that uses the DeepRTLAnalyzer + DifferentiatedTestGenerator
    internally, but presents the same interface as v1.
    """

    def __init__(self, rtl_path: str = "", spec_text: str = ""):
        self.rtl_path = rtl_path
        self.spec_text = spec_text
        self.rtl_content = ""
        self.ports: Dict = {}
        self.state_names: List[str] = []
        self.always_blocks: List[str] = []
        self.parameters: Dict = {}
        self.clocks: List[str] = []
        self.resets: List[str] = []

        # Internal v2 components
        self._analyzer: Optional[DeepRTLAnalyzer] = None
        self._generator: Optional[DifferentiatedTestGenerator] = None

        if rtl_path and os.path.exists(rtl_path):
            with open(rtl_path) as f:
                self.rtl_content = f.read()
            self._run_v2_analysis()

    def _run_v2_analysis(self):
        """Run v2 deep analysis."""
        self._analyzer = DeepRTLAnalyzer(self.rtl_content)
        ports, clocks, resets = self._analyzer.analyze()
        self.ports = ports
        self.clocks = clocks
        self.resets = resets
        self.state_names = self._analyzer.state_names
        self.parameters = self._analyzer.parameters
        self._generator = DifferentiatedTestGenerator(self._analyzer, self.spec_text)

    def generate_plan(self) -> VerificationPlan:
        """Generate a comprehensive verification plan using v2 engine."""
        if self._generator:
            return self._generator.generate()
        # Fallback: return empty plan
        return VerificationPlan(
            module_name="unknown",
            spec_summary=self.spec_text or "No RTL file provided",
        )

    def render_markdown(self, plan: VerificationPlan) -> str:
        """Render plan as markdown using v2 renderer."""
        if self._generator:
            return self._generator.render_markdown(plan)
        # Fallback: basic markdown
        lines = [f"# Verification Plan: {plan.module_name}",
                 f"**Spec:** {plan.spec_summary}"]
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verification Plan Generator v2")
    parser.add_argument("rtl", help="RTL file to analyze")
    parser.add_argument("--spec", "-s", help="Specification text", default="")
    parser.add_argument("--output", "-o", help="Output file", default="")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--deep", action="store_true", default=True,
                       help="Enable deep RTL analysis (default)")

    args = parser.parse_args()

    if not os.path.exists(args.rtl):
        print(f"[X] RTL file not found: {args.rtl}")
        import sys; sys.exit(1)

    gen = PlanGenerator(rtl_path=args.rtl, spec_text=args.spec)
    plan = gen.generate_plan()

    if args.json:
        output = json.dumps(plan.to_dict(), indent=2)
    else:
        output = gen.render_markdown(plan)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"[OK] Plan written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    import sys as _sys
    main()
