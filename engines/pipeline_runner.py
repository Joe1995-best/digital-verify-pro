"""
PipelineConfig — 增量构建流水线配置与缓存。

类似 Makefile 的阶段缓存：每个阶段的输入文件哈希不变时跳过执行。
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StageDef:
    name: str
    inputs: List[str]          # 输入文件 glob
    outputs: List[str]         # 输出文件 glob
    cache_key_sources: List[str] = field(default_factory=list)  # 额外缓存因子
    parallel: bool = False
    batch_size: int = 1

    @property
    def cache_key(self) -> str:
        """计算阶段缓存键。"""
        h = hashlib.sha256()
        for pattern in self.inputs:
            for f in sorted(Path().glob(pattern)):
                if f.exists():
                    h.update(f.read_bytes()[:1024])  # 只读前 1KB 做哈希
        for s in self.cache_key_sources:
            h.update(s.encode())
        return h.hexdigest()


@dataclass
class PipelineConfig:
    stages: List[StageDef] = field(default_factory=list)
    cache_dir: str = ".pipeline_cache"


class PipelineRunner:
    """增量构建流水线运行器。"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.cache_dir = Path(config.cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._load_cache()

    def _load_cache(self):
        cache_file = self.cache_dir / "state.json"
        self._cache: Dict = {}
        if cache_file.exists():
            with open(cache_file) as f:
                self._cache = json.load(f)

    def _save_cache(self):
        cache_file = self.cache_dir / "state.json"
        with open(cache_file, "w") as f:
            json.dump(self._cache, f, indent=2)

    def needs_run(self, stage: StageDef) -> bool:
        """检查阶段是否需要执行（缓存失效或输出缺失）。"""
        # 检查缓存
        cached_key = self._cache.get(f"{stage.name}_key")
        current_key = stage.cache_key
        if cached_key != current_key:
            return True
        # 检查所有输出文件是否存在
        for pattern in stage.outputs:
            found = list(Path().glob(pattern))
            if not found:
                return True
        return False

    def run_stage(self, stage: StageDef, fn: Callable) -> bool:
        """运行单个阶段（如有必要）。"""
        if not self.needs_run(stage):
            print(f"  [CACHE] {stage.name}: 命中缓存，跳过")
            return True
        print(f"  [RUN] {stage.name}...")
        try:
            fn()
            # 更新缓存
            self._cache[f"{stage.name}_key"] = stage.cache_key
            self._cache[f"{stage.name}_time"] = datetime.now().isoformat()
            self._save_cache()
            print(f"  [OK] {stage.name} 完成")
            return True
        except Exception as e:
            print(f"  [FAIL] {stage.name}: {e}")
            return False

    def run_all(self, stage_map: Dict[str, Callable]) -> bool:
        """顺序运行所有阶段。"""
        for stage in self.config.stages:
            fn = stage_map.get(stage.name)
            if fn is None:
                print(f"  [SKIP] {stage.name}: 无执行函数")
                continue
            if not self.run_stage(stage, fn):
                return False
        return True


# 默认流水线配置
def default_pipeline() -> PipelineConfig:
    return PipelineConfig(stages=[
        StageDef("spec-analyzer",
                 inputs=["*_spec.yml"],
                 outputs=[".contract_spec-analyzer.json"]),
        StageDef("rtl-gen",
                 inputs=["*_spec.yml", "pipeline/templates/*"],
                 outputs=["output/rtl/rtl/*.sv"],
                 cache_key_sources=["template_version:2.0"]),
        StageDef("sim-runner",
                 inputs=["output/rtl/rtl/*.sv", "verify_ot_dma/**/*.sv"],
                 outputs=["*.vcd"],
                 parallel=True, batch_size=4),
        StageDef("coverage",
                 inputs=["*.vcd"],
                 outputs=["output/coverage/gaps.json"]),
    ])
