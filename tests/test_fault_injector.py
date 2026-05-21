"""Tests for engines/fault_injector.py — full-featured fault injection engine."""

import os
import sys
import pytest
import json
import tempfile
import shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "engines"))


class TestFaultMode:
    def test_from_str_valid(self):
        from fault_injector import FaultMode
        assert FaultMode.from_str("seu") == FaultMode.SEU
        assert FaultMode.from_str("bus_hang") == FaultMode.BUS_HANG

    def test_from_str_invalid(self):
        from fault_injector import FaultMode
        with pytest.raises(ValueError):
            FaultMode.from_str("not_a_mode")

    def test_all_modes_present(self):
        from fault_injector import FaultMode
        modes = list(FaultMode)
        assert len(modes) == 8
        values = {m.value for m in modes}
        assert "seu" in values
        assert "reset_glitch" in values
        assert "glitch" in values


class TestGeneratePlan:
    def test_default_modes(self):
        from fault_injector import generate_plan
        plan = generate_plan(seed=42, iterations=2)
        assert plan["version"] == "2.0.0"
        assert plan["total_injections"] == 8 * 2  # 8 modes * 2 iterations
        assert plan["seed"] == 42
        # Check all modes represented
        modes_in_plan = {inj["mode"] for inj in plan["injections"]}
        assert len(modes_in_plan) == 8

    def test_subset_modes(self):
        from fault_injector import generate_plan, FaultMode
        plan = generate_plan(modes=[FaultMode.SEU, FaultMode.BUS_HANG], iterations=3)
        assert plan["total_injections"] == 6  # 2 modes * 3 iterations
        for inj in plan["injections"]:
            assert inj["mode"] in ("seu", "bus_hang")

    def test_seu_has_target_bit(self):
        from fault_injector import generate_plan, FaultMode
        plan = generate_plan(modes=[FaultMode.SEU], iterations=1)
        inj = plan["injections"][0]
        assert "target_bit" in inj
        assert 0 <= inj["target_bit"] <= 31

    def test_module_name(self):
        from fault_injector import generate_plan
        plan = generate_plan(module_name="i2c")
        assert plan["module"] == "i2c"


class TestWritePlan:
    def test_round_trip(self, tmp_path):
        from fault_injector import generate_plan, write_plan
        plan = generate_plan(seed=7, iterations=1)
        path = str(tmp_path / "plan.json")
        write_plan(plan, path)
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["seed"] == 7


class TestSVGeneration:
    def test_tasks_header(self):
        from fault_injector import generate_sv_tasks
        text = generate_sv_tasks("test_mod")
        assert "fault_injector_tasks" in text
        assert "test_mod" in text
        assert "`timescale" in text
        assert "fi_bus_hang" in text
        assert "fi_reset_glitch" in text
        assert "fi_seu" in text

    def test_tasks_subset(self):
        from fault_injector import generate_sv_tasks, FaultMode
        text = generate_sv_tasks("mod", modes=[FaultMode.SEU, FaultMode.GLITCH])
        assert "fi_seu" in text
        assert "fi_glitch" in text
        assert "fi_bus_hang" not in text

    def test_wrapper_generation(self):
        from fault_injector import generate_sv_wrapper
        text = generate_sv_wrapper("mod")
        assert "module fault_injector" in text
        assert "FAULT_MODE" in text
        assert "TRIGGER_CYCLE" in text
        assert "force_active" in text

    def test_uvm_sequence(self):
        from fault_injector import generate_uvm_sequence, FaultMode
        text = generate_uvm_sequence("mod", modes=[FaultMode.BUS_HANG, FaultMode.SEU])
        assert "fault_injector_seq" in text
        assert "bus_hang" in text
        assert "seu" in text
        assert "trigger_delay_ns" in text


class TestFaultInjectorClass:
    def test_detect_module_from_rtl(self, tmp_path):
        from fault_injector import FaultInjector
        rtl = tmp_path / "my_dut.sv"
        rtl.write_text("module my_dut (input clk); endmodule")
        fi = FaultInjector(rtl_path=str(rtl))
        assert fi.module_name == "my_dut"

    def test_detect_module_from_spec(self):
        from fault_injector import FaultInjector
        fi = FaultInjector(spec_path="i2c_spec.yml")
        assert fi.module_name == "i2c"

    def test_generate_all(self, tmp_path):
        from fault_injector import FaultInjector, FaultMode
        fi = FaultInjector(spec_path="uart_spec.yml")
        fi.set_modes([FaultMode.RESET_GLITCH, FaultMode.CLK_STALL])
        out = str(tmp_path / "fi_out")
        paths = fi.generate_all(out, seed=99, iterations=3)
        assert os.path.isfile(paths["plan"])
        assert os.path.isfile(paths["sv_tasks"])
        assert os.path.isfile(paths["sv_wrapper"])
        assert os.path.isfile(paths["uvm_seq"])
        # Verify plan content
        with open(paths["plan"], encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["total_injections"] == 6  # 2 modes * 3 iters
        assert plan["seed"] == 99

    def test_generate_plan_only(self, tmp_path):
        from fault_injector import FaultInjector
        fi = FaultInjector(spec_path="spi_spec.yml")
        path = fi.generate_plan_only(str(tmp_path / "plan.json"), seed=1, iterations=1)
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["module"] == "spi"

    def test_generate_sv_only(self, tmp_path):
        from fault_injector import FaultInjector
        fi = FaultInjector(spec_path="gpio_spec.yml")
        paths = fi.generate_sv_only(str(tmp_path / "sv_out"))
        assert os.path.isfile(paths["sv_tasks"])
        assert os.path.isfile(paths["sv_wrapper"])
        assert os.path.isfile(paths["uvm_seq"])


class TestCLI:
    def test_list_modes(self, capsys):
        from fault_injector import main
        rc = main(["--list-modes"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "bus_hang" in captured.out
        assert "seu" in captured.out
        assert "glitch" in captured.out

    def test_plan_only(self, tmp_path, capsys):
        from fault_injector import main
        out = str(tmp_path / "fi")
        rc = main(["--spec", "i2c_spec.yml", "--mode", "seu", "--plan-only", "--out", out])
        assert rc == 0
        assert os.path.isfile(os.path.join(out, "fault_injection_plan.json"))

    def test_sv_only(self, tmp_path, capsys):
        from fault_injector import main
        out = str(tmp_path / "fi")
        rc = main(["--rtl", "rtl/i2c.sv", "--mode", "reset_glitch", "--sv-only", "--out", out])
        assert rc == 0
        assert os.path.isfile(os.path.join(out, "fault_injector_tasks.sv"))
        assert os.path.isfile(os.path.join(out, "fault_injector.sv"))
