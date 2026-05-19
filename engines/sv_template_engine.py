"""
SVTemplateEngine — Jinja2 模板驱动的 SV 代码生成器。

替代 run_rtl_gen.py 中的字符串拼接，通过模板+数据分离保证语法正确。
"""
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import jinja2


@dataclass
class PortDef:
    name: str
    direction: str  # input, output
    width: int = 1


@dataclass
class RegDef:
    name: str
    offset: str
    reset: str
    is_wire: bool = False
    write_expr: str = "pwdata"
    fields: List[Dict] = field(default_factory=list)


class SVTemplateEngine:
    """SV 模板引擎。"""

    def __init__(self, template_dir: Optional[str] = None):
        if template_dir is None:
            template_dir = str(
                Path(__file__).resolve().parent.parent / "pipeline" / "templates" / "sv"
            )
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **kwargs) -> str:
        template = self.env.get_template(template_name)
        return template.render(**kwargs)

    def render_regs(self, module_name: str, registers: List[RegDef],
                    ports: List[PortDef], **kwargs) -> str:
        """渲染寄存器模块。"""
        return self.render("regs_module.sv.j2",
            module_name=module_name,
            registers=registers,
            ports=ports,
            **kwargs)

    @staticmethod
    def spec_to_regdefs(spec: Dict) -> List[RegDef]:
        """从 spec dict 提取 RegDef 列表。"""
        regs = []
        for r in spec.get("registers", []):
            regs.append(RegDef(
                name=r["name"],
                offset=r.get("offset", "0x00"),
                reset=r.get("reset", "0").replace("0x", ""),
                is_wire=self._is_readonly(r),
                write_expr=self._write_expr(r),
                fields=r.get("fields", []),
            ))
        return regs

    @staticmethod
    def _is_readonly(reg: Dict) -> bool:
        fields = reg.get("fields", [])
        return all(f.get("access") == "ro" for f in fields)

    @staticmethod
    def _write_expr(reg: Dict) -> str:
        fields = reg.get("fields", [])
        # If fields have specific widths, generate bitfield write
        if fields:
            exprs = []
            for f in fields:
                bits = f.get("bits", "[31:0]").strip("[]")
                acc = f.get("access", "rw")
                if acc == "rw":
                    msb = bits.split(":")[0]
                    lsb = bits.split(":")[1] if ":" in bits else bits
                    if msb == "31" and lsb == "0":
                        return "pwdata"
                    exprs.append(f"pwdata[{msb}:{lsb}]")
            if exprs:
                return f"{{ {' , '.join(exprs)} }}" if len(exprs) > 1 else exprs[0]
        return "pwdata"
