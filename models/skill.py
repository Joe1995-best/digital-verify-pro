"""
VerificationSkill — 所有 standalone-skill 的统一接口 ABC。

每个 skill 实现此接口后可通过 SkillRegistry 自动发现和运行。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path


@dataclass
class SkillContext:
    """Skill 运行上下文。"""
    args: List[str] = field(default_factory=list)
    cwd: str = "."
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill 运行结果。"""
    success: bool
    output: str = ""
    artifacts: List[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class QualityReport:
    """质量报告（与 quality_pipeline.py 兼容）。"""
    total: float = 0.0
    max_score: float = 100.0
    functional: float = 0.0
    code_docs: float = 0.0
    security: float = 0.0
    reliability: float = 0.0
    compatibility: float = 0.0
    label: str = "Unstable"
    recommendations: List[str] = field(default_factory=list)


class VerificationSkill(ABC):
    """验证 Skill 基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill 名称（与 standalone-skills/ 目录名一致）。"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """语义化版本号。"""
        ...

    @abstractmethod
    def run(self, ctx: SkillContext) -> SkillResult:
        """执行 skill 的主功能。"""
        ...

    @abstractmethod
    def quality(self) -> QualityReport:
        """返回当前质量评分。"""
        ...


class SkillRegistry:
    """Skill 注册与自动发现。"""

    def __init__(self):
        self._skills: Dict[str, VerificationSkill] = {}

    def register(self, skill: VerificationSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[VerificationSkill]:
        return self._skills.get(name)

    def discover(self, base_dir: str = "standalone-skills") -> List[str]:
        """从 standalone-skills/ 目录自动发现。"""
        discovered = []
        base = Path(base_dir)
        if not base.exists():
            return discovered
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "run.py").exists():
                discovered.append(d.name)
                self._register_from_dir(d)
        return discovered

    def _register_from_dir(self, d: Path) -> None:
        """尝试从目录加载并注册 skill。"""
        try:
            import importlib.util
            run_py = d / "run.py"
            spec = importlib.util.spec_from_file_location(
                f"standalone_{d.name}", run_py
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "main"):
                    # Create adapter for non-ABC skills
                    self._register_adapter(d.name, mod)
        except Exception:
            pass  # Silently skip malformed skills

    def _register_adapter(self, name: str, mod) -> None:
        """为当前无 ABC 包装的 skill 创建适配器。"""
        main_fn = getattr(mod, "main", None)
        if main_fn:

            class SkillAdapter(VerificationSkill):
                @property
                def name(self) -> str:
                    return name

                @property
                def version(self) -> str:
                    return getattr(mod, "__version__", "1.0.0")

                def run(self, ctx: SkillContext) -> SkillResult:
                    import sys, io
                    old_stdout = sys.stdout
                    sys.stdout = buf = io.StringIO()
                    try:
                        ret = main_fn()
                        return SkillResult(success=ret == 0, output=buf.getvalue())
                    except Exception as e:
                        return SkillResult(success=False, output=str(e))
                    finally:
                        sys.stdout = old_stdout

                def quality(self) -> QualityReport:
                    return QualityReport()

            self.register(SkillAdapter())

    @property
    def all(self) -> List[VerificationSkill]:
        return list(self._skills.values())

    def run_all(self, ctx: SkillContext) -> Dict[str, SkillResult]:
        """运行所有已注册 skill。"""
        results = {}
        for skill in self.all:
            results[skill.name] = skill.run(ctx)
        return results


# 全局注册表
_registry = SkillRegistry()
