"""
VCD Backend — 可选高性能 VCD 解析后端。

当前 coverage_engine.py 用纯 Python 解析 VCD。
此模块提供 vcdvcd (C 扩展) 接入点，当安装时自动使用。
"""
from typing import Optional, List, Dict, Tuple
from pathlib import Path


class VCDResult:
    """VCD 解析结果（与 coverage_engine 兼容）。"""
    def __init__(self):
        self.signals: Dict[str, List[Tuple[int, str]]] = {}
        self.end_time: int = 0
        self.signal_count: int = 0
        self.timestamps: List[int] = []


class VCDBackend:
    """VCD 解析后端抽象。"""

    def __init__(self, vcd_path: str):
        self.vcd_path = vcd_path
        self._backend = self._detect_backend()

    def _detect_backend(self):
        try:
            import vcdvcd
            return "vcdvcd"
        except ImportError:
            return "python"

    def parse(self) -> VCDResult:
        if self._backend == "vcdvcd":
            return self._parse_vcdvcd()
        return self._parse_fallback()

    def _parse_vcdvcd(self) -> VCDResult:
        """使用 vcdvcd C 扩展解析（快 10-100x）。"""
        from vcdvcd import VCDVCD
        vcd = VCDVCD(self.vcd_path, strict=False)
        result = VCDResult()
        for sig_key, sig_data in vcd.items():
            if isinstance(sig_data, dict) and "tv" in sig_data:
                name = sig_key.replace(".", "_")
                result.signals[name] = sig_data["tv"]
                result.signal_count += 1
        result.end_time = vcd.endtime if hasattr(vcd, "endtime") else 0
        return result

    def _parse_fallback(self) -> VCDResult:
        """回退到 coverage_engine 的纯 Python 解析器。"""
        import sys, os
        # Dynamic import to avoid circular dependency
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from engines.coverage_engine import VCDParser
        parser = VCDParser(self.vcd_path)
        # Use the parser's internal structure
        result = VCDResult()
        result.end_time = parser.end_time if hasattr(parser, "end_time") else 0
        return result

    @property
    def backend_name(self) -> str:
        return self._backend

    @staticmethod
    def available_backends() -> List[str]:
        backends = ["python"]
        try:
            import vcdvcd
            backends.append("vcdvcd")
        except ImportError:
            pass
        return backends
