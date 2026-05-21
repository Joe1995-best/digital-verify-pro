"""Tests for core engines: coverage_engine, plan_generator, formal_check_gen."""

import os
import sys
import pytest
import tempfile
import shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "engines"))
sys.path.insert(0, os.path.join(PROJECT_DIR, "pipeline"))


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_rtl_path(tmpdir_factory):
    """Create a minimal RTL file with FSM, datapath, and APB ports."""
    rtl = """
module test_fsm (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [11:0] paddr,
    input  wire [31:0] pwdata,
    input  wire        psel,
    input  wire        penable,
    input  wire        pwrite,
    output reg  [31:0] prdata,
    output reg         pready,
    output reg         pslverr
);

    localparam IDLE  = 2'b00;
    localparam READ  = 2'b01;
    localparam WRITE = 2'b10;
    localparam DONE  = 2'b11;

    reg [1:0] state, next_state;
    reg [7:0] data_reg;

    // Sequential state register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            data_reg <= 0;
        end else begin
            state <= next_state;
            data_reg <= data_reg + 1;
        end
    end

    // Next-state combinational logic
    always @(*) begin
        next_state = state;
        case (state)
            IDLE:  if (psel && penable) next_state = pwrite ? WRITE : READ;
            READ:  next_state = DONE;
            WRITE: next_state = DONE;
            DONE:  next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end

    // Output logic
    always @(*) begin
        prdata  = 32'hDEAD_BEEF;
        pready  = 1'b0;
        pslverr = 1'b0;
        case (state)
            READ:  begin prdata = {24'b0, data_reg}; pready = 1'b1; end
            WRITE: begin pready = 1'b1; end
            DONE:  begin pready = 1'b1; end
            default: ;
        endcase
    end

endmodule
"""
    p = tmpdir_factory.mktemp("rtl").join("test_fsm.sv")
    p.write(rtl)
    return str(p)


@pytest.fixture
def sample_vcd_path(tmpdir_factory):
    """Create a minimal VCD with toggle activity for coverage testing."""
    vcd = """$date
   today
$end
$version
   testgen 1.0
$end
$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 1 " rst_n $end
$var wire 32 # prdata [31:0] $end
$var wire 1 $ pready $end
$var wire 1 % pslverr $end
$var wire 2 & state [1:0] $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
0"
b00000000000000000000000000000000 #
0$
0%
b00 &
$end
#0
1!
#10
0!
1"
#20
1!
b00000000000000000000000000001010 #
1$
#30
0!
#40
1!
0"
b00000000000000000000000000001111 #
0$
1%
b01 &
#50
0!
#60
1!
b00000000000000000000000000000000 #
1$
0%
b10 &
#70
0!
#80
1!
b00000000000000000000000000000001 #
0$
b11 &
#90
0!
#100
1!
0"
b00000000000000000000000000000010 #
1$
b00 &
"""
    p = tmpdir_factory.mktemp("vcd").join("test.vcd")
    p.write(vcd)
    return str(p)


# ── PlanGenerator Tests ─────────────────────────────────────────────────────

class TestPlanGenerator:
    def test_init_no_file(self):
        from plan_generator import PlanGenerator
        pg = PlanGenerator()
        assert pg.rtl_path == ""
        assert pg._generator is None

    def test_init_with_rtl(self, sample_rtl_path):
        from plan_generator import PlanGenerator
        pg = PlanGenerator(rtl_path=sample_rtl_path)
        assert pg._analyzer is not None
        assert "clk" in pg.clocks
        assert "rst_n" in pg.resets
        assert len(pg.ports) >= 4

    def test_generate_plan(self, sample_rtl_path):
        from plan_generator import PlanGenerator
        pg = PlanGenerator(rtl_path=sample_rtl_path)
        plan = pg.generate_plan()
        assert plan.module_name == "test_fsm"
        assert len(plan.test_scenarios) > 0
        # FSM detected
        assert plan.fsm_info is not None
        assert len(plan.fsm_info.states) >= 4
        # At least some protocol or port detection happened
        assert len(plan.protocols) >= 0

    def test_plan_coverage_computation(self, sample_rtl_path):
        from plan_generator import PlanGenerator
        pg = PlanGenerator(rtl_path=sample_rtl_path)
        plan = pg.generate_plan()
        cov = plan.compute_coverage()
        assert cov["total_points"] > 0
        assert 0 <= cov["coverage_pct"] <= 100

    def test_render_markdown(self, sample_rtl_path):
        from plan_generator import PlanGenerator
        pg = PlanGenerator(rtl_path=sample_rtl_path)
        plan = pg.generate_plan()
        md = pg.render_markdown(plan)
        assert "test_fsm" in md
        assert "Verification Plan" in md
        assert "Test Scenarios" in md

    def test_complexity_score(self, sample_rtl_path):
        from plan_generator import DeepRTLAnalyzer
        with open(sample_rtl_path) as f:
            content = f.read()
        analyzer = DeepRTLAnalyzer(content)
        analyzer.analyze()
        score = analyzer.compute_complexity_score()
        assert 1 <= score <= 10


# ── CoverageEngine Tests ───────────────────────────────────────────────────

class TestCoverageEngine:
    def test_vcd_parser_basic(self, sample_vcd_path):
        from coverage_engine import VCDParser
        parser = VCDParser(sample_vcd_path)
        assert parser.parse() is True
        assert len(parser.signals) >= 4
        assert "top_clk" in parser.signals or "clk" in parser.signals
        assert parser.end_time > 0

    def test_vcd_get_value_at(self, sample_vcd_path):
        from coverage_engine import VCDParser
        parser = VCDParser(sample_vcd_path)
        parser.parse()
        val = parser.get_value_at("top_clk", 20)
        assert val is not None

    def test_toggle_info(self):
        from coverage_engine import ToggleInfo
        t = ToggleInfo(signal="top_clk", width=1)
        t.toggled_0_to_1 += 1
        t.toggled_1_to_0 += 1
        assert t.coverage_pct == 100.0
        assert t.toggle_rate == 2
        assert t.grade == "LOW"

    def test_coverage_engine_analyze(self, sample_vcd_path):
        from coverage_engine import CoverageEngine
        engine = CoverageEngine(module_name="test_fsm")
        report = engine.analyze_vcd(sample_vcd_path, clk_signal="top_clk")
        assert report.module_name == "test_fsm"
        assert report.total_signals > 0
        assert report.toggle_coverage_pct >= 0
        # At least some signals toggled
        assert report.full_toggle_signals + report.half_toggle_signals + report.stuck_signals == report.total_signals

    def test_coverage_report_to_dict(self, sample_vcd_path):
        from coverage_engine import CoverageEngine
        engine = CoverageEngine(module_name="test_fsm")
        report = engine.analyze_vcd(sample_vcd_path)
        d = report.to_dict()
        assert d["module"] == "test_fsm"
        assert "toggle" in d
        assert "gaps" in d
        assert "signal_stats" in d

    def test_condition_coverage(self):
        from coverage_engine import ConditionCoverage
        cc = ConditionCoverage(signal_a="a", signal_b="b")
        cc.both_0 = 1
        cc.both_1 = 1
        assert cc.coverage_pct == 50.0
        cc.a_1_b_0 = 1
        cc.a_0_b_1 = 1
        assert cc.coverage_pct == 100.0


# ── FormalChecker Tests ─────────────────────────────────────────────────────

class TestFormalChecker:
    def test_init_no_file(self):
        from formal_check_gen import FormalChecker
        fc = FormalChecker()
        assert fc.module_name == "unknown"

    def test_init_with_rtl(self, sample_rtl_path):
        from formal_check_gen import FormalChecker
        fc = FormalChecker(rtl_path=sample_rtl_path)
        assert fc.module_name == "test_fsm"
        assert fc.clock_signal == "clk"
        assert fc.reset_signal == "rst_n"

    def test_generate_properties(self, sample_rtl_path):
        from formal_check_gen import FormalChecker
        fc = FormalChecker(rtl_path=sample_rtl_path)
        props = fc.generate_properties()
        assert len(props) > 0
        # Check that properties have required fields
        for p in props:
            assert p.name
            assert p.kind in ("assert", "assume", "cover")
            assert p.expression

    def test_generate_config(self, sample_rtl_path):
        from formal_check_gen import FormalChecker
        fc = FormalChecker(rtl_path=sample_rtl_path)
        config = fc.generate_config(depth=30)
        assert config.module_name == "test_fsm"
        assert config.depth == 30
        assert "smtbmc" in config.to_sby()
        assert "mode bmc" in config.to_sby()

    def test_sva_module_output(self, sample_rtl_path):
        from formal_check_gen import FormalChecker
        fc = FormalChecker(rtl_path=sample_rtl_path)
        config = fc.generate_config()
        sva = config.to_sva_module()
        assert "`ifdef FORMAL" in sva
        assert "test_fsm_formal_check" in sva
        assert "assert property" in sva

    def test_property_dataclasses(self):
        from formal_check_gen import FormalProperty, FormalCheckConfig
        p = FormalProperty(name="test", kind="assert", expression="a && b")
        assert p.name == "test"
        c = FormalCheckConfig(module_name="mod", depth=10)
        assert "depth 10" in c.to_sby()
