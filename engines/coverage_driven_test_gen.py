"""
CoverageDrivenTestGen — 覆盖度缺口 → 可执行 SV 测试闭环。

读取 coverage_engine 的 gaps.json，自动生成 SystemVerilog 测试用例，
针对每个未翻转信号生成 APB 写/读序列强制翻转。
"""
import json
import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class CoverageGap:
    signal: str
    gap_type: str        # no_toggle, half_toggle, low_activity
    severity: int        # 1-5
    module: str = ""
    reg_name: str = ""   # 推测的寄存器名


@dataclass
class GeneratedTest:
    name: str
    test_type: str       # directed, corner_case
    code: str            # SystemVerilog test body
    target_signal: str
    priority: int = 1


class CoverageDrivenTestGen:
    """从覆盖度缺口自动生成定向测试。"""

    def __init__(self, gaps_path: str, spec_path: str = ""):
        with open(gaps_path, "r", encoding="utf-8") as f:
            raw = json.load(f) if gaps_path.endswith(".json") else {}
        self.gaps = self._parse_gaps(raw)
        self.spec = self._load_spec(spec_path) if spec_path else {}
        self.reg_map = self._build_reg_map() if self.spec else {}

    def _parse_gaps(self, raw: dict) -> List[CoverageGap]:
        gaps = []
        for g in raw.get("gaps", []):
            gaps.append(CoverageGap(
                signal=g.get("signal", "unknown"),
                gap_type=g.get("type", "no_toggle"),
                severity=g.get("severity", 3),
            ))
        # 也解析顶层列表格式
        if not gaps:
            for entry in raw if isinstance(raw, list) else []:
                gaps.append(CoverageGap(
                    signal=entry.get("signal", "unknown"),
                    gap_type=entry.get("type", "no_toggle"),
                    severity=entry.get("severity", 3),
                ))
        return gaps

    def _load_spec(self, path: str) -> dict:
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _build_reg_map(self) -> Dict[str, str]:
        """从 spec 构建 {信号名 → 寄存器偏移} 映射。"""
        reg_map = {}
        for reg in self.spec.get("registers", []):
            name = reg.get("name", "")
            offset = reg.get("offset", "")
            if name and offset:
                reg_map[name.lower()] = offset
                # 也加缩写匹配
                for f in reg.get("fields", []):
                    fname = f.get("name", "").lower()
                    reg_map[f"{name}_{fname}".lower()] = offset
                    reg_map[fname] = offset
        return reg_map

    def _estimate_reg(self, gap: CoverageGap) -> str:
        """从信号名推测对应寄存器。"""
        sig_lower = gap.signal.lower()
        for reg_name, offset in self.reg_map.items():
            if reg_name in sig_lower or sig_lower in reg_name:
                return offset
        return "0x000"

    def generate(self, max_gaps: int = 10) -> List[GeneratedTest]:
        tests = []
        for gap in self.gaps[:max_gaps]:
            if gap.gap_type == "no_toggle":
                test = self._gen_no_toggle_test(gap)
            elif gap.gap_type == "half_toggle":
                test = self._gen_half_toggle_test(gap)
            else:
                test = self._gen_low_activity_test(gap)
            if test:
                tests.append(test)
        return tests

    def _gen_no_toggle_test(self, gap: CoverageGap) -> Optional[GeneratedTest]:
        """从未翻转信号 → APB 写 1 再写 0 强制翻转。"""
        offset = self._estimate_reg(gap)
        name = f"gap_toggle_{self._safe_name(gap.signal)}"

        code = f"""  // Auto-generated: force toggle {gap.signal}
  $display("--- {name} ---");
  apb_write({offset}, 32'hFFFFFFFF);  // set all bits
  apb_read({offset}, rd);
  apb_write({offset}, 32'h00000000);  // clear all bits
  apb_read({offset}, rd);
  $display("  {name} done");
"""
        return GeneratedTest(
            name=name,
            test_type="directed",
            code=code,
            target_signal=gap.signal,
            priority=1,
        )

    def _gen_half_toggle_test(self, gap: CoverageGap) -> Optional[GeneratedTest]:
        """半翻转信号 → 写 1 后写 0 补全翻转。"""
        offset = self._estimate_reg(gap)
        name = f"gap_half_{self._safe_name(gap.signal)}"

        code = f"""  // Auto-generated: complete toggle {gap.signal}
  $display("--- {name} ---");
  apb_write({offset}, 32'h00000000);  // force 1→0 transition
  apb_read({offset}, rd);
  apb_write({offset}, 32'hFFFFFFFF);  // force 0→1 again
  apb_read({offset}, rd);
  $display("  {name} done");
"""
        return GeneratedTest(
            name=name,
            test_type="corner_case",
            code=code,
            target_signal=gap.signal,
            priority=2,
        )

    def _gen_low_activity_test(self, gap: CoverageGap) -> Optional[GeneratedTest]:
        """低频信号 → 多次切换增加 activity。"""
        offset = self._estimate_reg(gap)
        name = f"gap_active_{self._safe_name(gap.signal)}"

        code = f"""  // Auto-generated: increase activity {gap.signal}
  $display("--- {name} ---");
  repeat (10) begin
    apb_write({offset}, 32'hFFFFFFFF);
    apb_write({offset}, 32'h00000000);
  end
  $display("  {name} done");
"""
        return GeneratedTest(
            name=name,
            test_type="stress",
            code=code,
            target_signal=gap.signal,
            priority=3,
        )

    @staticmethod
    def _safe_name(signal: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_]', '_', signal)

    def generate_testbench_insert(self, tests: List[GeneratedTest]) -> str:
        """生成可插入 testbench initial 块的代码片段。"""
        lines = [
            "// ===== Coverage-driven test insertion =====",
            "// Generated by CoverageDrivenTestGen",
        ]
        for t in tests:
            lines.append(t.code)
        lines.append("// ===== End coverage-driven tests =====")
        return "\n".join(lines)

    def report(self, tests: List[GeneratedTest]) -> str:
        lines = [
            "| # | Test | Type | Target | Priority |",
            "|---|------|------|--------|:--------:|",
        ]
        for i, t in enumerate(tests, 1):
            lines.append(
                f"| {i} | {t.name} | {t.test_type} "
                f"| {t.target_signal[:40]} | {t.priority} |"
            )
        return "\n".join(lines)
