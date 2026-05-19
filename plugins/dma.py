"""
DMA Protocol Plugin — 符合 ProtocolPlugin 接口的 DMA FSM 生成器。

将 run_rtl_gen.py 中原有的 has_dma_fsm() 逻辑封装为插件。
"""
from models.protocol import ProtocolPlugin, ProtocolConfig, RTLModule, register
from pipeline.fsm_templates import (
    has_dma_fsm, generate_fsm,
    generate_interrupt_top_insert
)
from pipeline.template_engine import build_spec_data


class DMAProtocol(ProtocolPlugin):

    @property
    def protocol_type(self) -> str:
        return "dma"

    def detect(self, config: ProtocolConfig) -> bool:
        # 复用现有检测逻辑
        data = self._to_data(config)
        return has_dma_fsm(data)

    def generate_top(self, config: ProtocolConfig) -> RTLModule:
        from pipeline.run_rtl_gen import generate_top_module_dma
        data = self._to_data(config)
        code = generate_top_module_dma(data)
        return RTLModule(
            name=f"{config.module_name}",
            filename=f"{config.module_name}.sv",
            code=code,
            description="DMA top module with FSM + FIFOs"
        )

    def generate_regs(self, config: ProtocolConfig) -> RTLModule:
        from pipeline.run_rtl_gen import generate_regs_module
        from pipeline.run_rtl_gen import generate_i2c_regs_module
        data = self._to_data(config)
        # DMA uses standard regs, not I2C
        code = generate_regs_module(data)
        return RTLModule(
            name=f"{config.module_name}_regs",
            filename=f"{config.module_name}_regs.sv",
            code=code,
            description="DMA register bank"
        )

    def generate_fsm(self, config: ProtocolConfig) -> Optional[RTLModule]:
        data = self._to_data(config)
        fsm_files = generate_fsm(data)
        modules = []
        for fname, fcode in fsm_files.items():
            mod_name = fname.replace(".sv", "")
            modules.append(RTLModule(
                name=mod_name,
                filename=fname,
                code=fcode,
                description="DMA FSM controller"
            ))
        # Return the main FSM module
        return modules[0] if modules else None

    def _to_data(self, config: ProtocolConfig) -> dict:
        """Convert ProtocolConfig → dict (template_engine 兼容格式)。"""
        import yaml
        return {
            "module": {"name": config.module_name},
            "module_name": config.module_name,
            "clk_name": config.clk_name,
            "rst_name": config.rst_name,
            "registers": config.registers,
            "interfaces": config.interfaces,
            "fsm": config.fsm or {},
            "reserved_ranges": config.reserved_ranges,
        }


# 注册到全局注册表
register(DMAProtocol())
