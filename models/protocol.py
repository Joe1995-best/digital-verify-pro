"""
ProtocolPlugin — 协议抽象层 (ABC)

每个芯片协议（DMA/I2C/SPI/GPIO/UART）实现此接口，
注册后即可被 run_rtl_gen.py 调用，不修改核心代码。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class RTLModule:
    """生成的 RTL 模块。"""
    name: str          # 模块名 (如 i2c_regs)
    filename: str       # 文件名 (如 i2c_regs.sv)
    code: str           # SystemVerilog 源码
    description: str = ""


@dataclass
class ProtocolConfig:
    """协议配置 — 从 spec.yml 解析。"""
    module_name: str
    interfaces: List[Dict[str, Any]]
    registers: List[Dict[str, Any]]
    fsm: Optional[Dict[str, Any]] = None
    clk_name: str = "clk"
    rst_name: str = "rstn"
    addr_width: int = 12
    reserved_ranges: List[Dict[str, Any]] = field(default_factory=list)


class ProtocolPlugin(ABC):
    """协议插件基类。每个协议实现此接口的 4 个方法。"""

    @property
    @abstractmethod
    def protocol_type(self) -> str:
        """返回协议标识符，与 spec.yml 中 fsm.type 匹配。"""
        ...

    @abstractmethod
    def detect(self, config: ProtocolConfig) -> bool:
        """判断此协议是否适用于当前 spec。"""
        ...

    @abstractmethod
    def generate_top(self, config: ProtocolConfig) -> Optional[RTLModule]:
        """生成顶层模块 (top.sv)。返回 None 则用通用模板。"""
        ...

    @abstractmethod
    def generate_regs(self, config: ProtocolConfig) -> RTLModule:
        """生成寄存器模块 (regs.sv)。"""
        ...

    @abstractmethod
    def generate_fsm(self, config: ProtocolConfig) -> Optional[RTLModule]:
        """生成 FSM 控制器。返回 None 表示无需 FSM。"""
        ...


class ProtocolRegistry:
    """协议注册表 — 全局单例。"""

    def __init__(self):
        self._plugins: Dict[str, ProtocolPlugin] = {}

    def register(self, plugin: ProtocolPlugin) -> None:
        self._plugins[plugin.protocol_type] = plugin

    def get(self, protocol_type: str) -> Optional[ProtocolPlugin]:
        return self._plugins.get(protocol_type)

    def detect(self, config: ProtocolConfig) -> Optional[ProtocolPlugin]:
        for plugin in self._plugins.values():
            if plugin.detect(config):
                return plugin
        return None

    @property
    def all(self) -> List[ProtocolPlugin]:
        return list(self._plugins.values())


# 全局注册表
_registry = ProtocolRegistry()


def register(plugin: ProtocolPlugin) -> None:
    _registry.register(plugin)


def registry() -> ProtocolRegistry:
    return _registry
