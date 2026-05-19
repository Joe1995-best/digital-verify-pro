"""
SPI Protocol Plugin — 生成 SPI 从机顶层 + FSM + 寄存器。
"""
from models.protocol import ProtocolPlugin, ProtocolConfig, RTLModule, register
from pipeline.fsm_templates import has_spi_fsm


class SPIProtocol(ProtocolPlugin):

    @property
    def protocol_type(self) -> str:
        return "spi"

    def detect(self, config: ProtocolConfig) -> bool:
        data = self._to_data(config)
        return has_spi_fsm(data)

    def generate_top(self, config: ProtocolConfig) -> Optional[RTLModule]:
        # SPI 顶层使用 run_rtl_gen.py 的通用模板（不含 FSM），
        # 然后由 tools/spi_rtl_stitch.py 后处理添加 FSM 连接
        return None  # 使用通用模板

    def generate_regs(self, config: ProtocolConfig) -> RTLModule:
        # 使用通用寄存器生成（run_rtl_gen.py 的 generate_regs_module）
        return None  # 由主生成器处理

    def generate_fsm(self, config: ProtocolConfig) -> Optional[RTLModule]:
        # 返回 SPI FSM 模板，由 stitching 脚本注入顶层
        from pathlib import Path
        tpl_path = Path(__file__).resolve().parent.parent / "pipeline" / "templates" / "spi_slave_fsm.sv"
        if tpl_path.exists():
            code = tpl_path.read_text(encoding="utf-8")
            return RTLModule(
                name=f"{config.module_name}_spi_slave_fsm",
                filename=f"{config.module_name}_spi_slave_fsm.sv",
                code=code,
                description="SPI slave FSM (shift-register based)"
            )
        return None

    def _to_data(self, config: ProtocolConfig) -> dict:
        return {"fsm": config.fsm or {}}


# 自动注册
register(SPIProtocol())
