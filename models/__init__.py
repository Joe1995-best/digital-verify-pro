"""digital-verify-pro data models."""
from .spec import Spec, Module, Register, RegField, Interface, Signal, Clock, Reset, FSMConfig, FSMState
from .protocol import ProtocolPlugin, ProtocolConfig, RTLModule, ProtocolRegistry, register, registry
from .skill import VerificationSkill, SkillContext, SkillResult, QualityReport, SkillRegistry
