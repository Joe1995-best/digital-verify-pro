"""
digital-verify-pro — Pydantic Spec Models

强类型 Spec 验证：spec YAML → 加载时类型检查，非生成 RTL 后报错。
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class Clock(BaseModel):
    name: str
    frequency: Optional[str] = None


class Reset(BaseModel):
    name: str
    polarity: str = "active_low"
    async_: bool = Field(default=True, alias="async")

    @field_validator("polarity")
    @classmethod
    def check_polarity(cls, v: str) -> str:
        if v not in ("active_low", "active_high"):
            raise ValueError(f"polarity must be active_low or active_high, got {v}")
        return v


class Signal(BaseModel):
    name: str
    width: int = 1
    direction: Literal["input", "output", "inout", "bidir"]
    desc: Optional[str] = None


class Interface(BaseModel):
    name: str
    type: str
    direction: str = "slave"
    signals: List[Signal]


class RegField(BaseModel):
    name: str
    bits: str
    access: Literal["rw", "ro", "wo", "w1c", "w1s"]
    reset: str = "0"
    desc: Optional[str] = None

    @field_validator("bits")
    @classmethod
    def validate_bits(cls, v: str) -> str:
        # Accept: "0", "7:0", "[31:16]"
        clean = v.strip("[]")
        parts = clean.split(":")
        for p in parts:
            try:
                int(p, 10)
            except ValueError:
                raise ValueError(f"invalid bit range: {v}")
        if len(parts) == 1:
            pass  # single bit
        elif len(parts) == 2:
            if int(parts[0]) <= int(parts[1]):
                raise ValueError(f"msb must be > lsb: {v}")
        else:
            raise ValueError(f"invalid bit format: {v}")
        return v


class Register(BaseModel):
    name: str
    offset: str
    reset: str = "0x0"
    description: Optional[str] = None
    fields: List[RegField] = []

    @field_validator("offset")
    @classmethod
    def validate_offset(cls, v: str) -> str:
        if not re.match(r"^0x[0-9a-fA-F]+$", v):
            raise ValueError(f"offset must be hex (0x...), got {v}")
        return v


class FSMTransition(BaseModel):
    next: str
    condition: Optional[str] = None


class FSMState(BaseModel):
    name: str
    value: Optional[int] = None
    desc: Optional[str] = None
    transitions: List[FSMTransition] = []
    actions: Optional[List[str]] = None


class FSMConfig(BaseModel):
    type: Literal["dma", "i2c", "spi", "gpio", "uart", "generic"] = "generic"
    name: Optional[str] = None
    description: Optional[str] = None
    states: List[FSMState] = []
    interrupts: List[Dict[str, str]] = []


class Module(BaseModel):
    name: str
    description: Optional[str] = None
    version: Optional[str] = None


class Spec(BaseModel):
    module: Module
    clocks: List[Clock] = []
    resets: List[Reset] = []
    interfaces: List[Interface] = []
    registers: List[Register] = []
    fsm: Optional[FSMConfig] = None

    @field_validator("registers")
    @classmethod
    def check_no_overlap(cls, v: List[Register]) -> List[Register]:
        offsets = [r.offset for r in v]
        if len(offsets) != len(set(offsets)):
            raise ValueError(f"duplicate register offsets: {offsets}")
        return v

    @property
    def module_name(self) -> str:
        return self.module.name

    @property
    def clk_name(self) -> str:
        return self.clocks[0].name if self.clocks else "clk"

    @property
    def rst_name(self) -> str:
        return self.resets[0].name if self.resets else "rstn"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for template engine compatibility."""
        import yaml
        return yaml.safe_load(self.model_dump_json())

    @classmethod
    def from_yaml(cls, path: str) -> "Spec":
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)
