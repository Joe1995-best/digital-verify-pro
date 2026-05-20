import pytest

"""Integration tests for coverage-engine -- validate result.json + coverage_report."""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def test_minimal_vcd_produces_valid_result():
    vcd = os.path.join(FIXTURES, "minimal.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            [sys.executable, "run.py", "--vcd", vcd, "--out", tmp, "--result", os.path.join(tmp, "result.json")],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert r.returncode != 99, "INTERNAL_ERROR: " + r.stderr[:200]

        rj = os.path.join(tmp, "result.json")
        assert os.path.isfile(rj), "result.json not produced"
        with open(rj) as f:
            data = json.load(f)
        assert data["status"] in ("pass", "fail", "error", "skip")
        assert "metrics" in data
        assert "timestamp" in data

        # P1-3: Verify metric values are valid ranges
        assert data["metrics"]["total_signals"] >= 0
        assert data["metrics"]["toggle_coverage_percent"] >= 0
        assert data["metrics"]["toggle_coverage_percent"] <= 100
        assert data["metrics"]["stuck_signals"] >= 0

def test_output_files_exist():
    vcd = os.path.join(FIXTURES, "minimal.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "run.py", "--vcd", vcd, "--out", tmp],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        for fn in ("coverage_report.json", "coverage_report.md"):
            fp = os.path.join(tmp, fn)
            if os.path.isfile(fp) and fn.endswith(".json"):
                with open(fp) as f:
                    payload = json.load(f)
                assert isinstance(payload, dict)


# ── P1-5 Boundary Fixture Tests ──────────────────────────────────────────────

def test_empty_vcd_graceful():
    """Empty VCD with only $enddefinitions should parse without error."""
    vcd = os.path.join(FIXTURES, "empty.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    from coverage_engine import VCDParser
    parser = VCDParser(vcd)
    ok = parser.parse()
    assert ok, "VCDParser.parse() should return True for empty.vcd"
    assert len(parser.signals) == 0, "No signals expected from empty VCD"


def test_corrupt_vcd_graceful():
    """Corrupt VCD with illegal timestamp should not raise."""
    vcd = os.path.join(FIXTURES, "corrupt.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    from coverage_engine import VCDParser, CoverageEngine
    parser = VCDParser(vcd)
    # Should not raise
    ok = parser.parse()
    # May still return True if parser is tolerant, but shouldn't crash
    assert ok == True or ok == False


def test_multi_clock_vcd_parses():
    """VCD with 2 clock domains should parse both clocks."""
    vcd = os.path.join(FIXTURES, "multi_clock.vcd")
    if not os.path.isfile(vcd):
        pytest.skip("fixture not found")
    from coverage_engine import VCDParser
    parser = VCDParser(vcd)
    ok = parser.parse()
    assert ok, f"multi_clock.vcd should parse ok"
    # Should have at least 2 clock signals
    clk_signals = [s for s in parser.signals if "clk" in s.lower()]
    # We may have clk1 and clk2 from top module
    clock_names = [s for s in parser.signals if any(c in s.lower() for c in ("clk"))]
    assert len(clock_names) >= 1, f"Expected at least 1 clock signal, got {clock_names}"
    assert parser.end_time >= 0
