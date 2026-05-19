"""
pipeline_cache.py — 增量构建缓存 (mtime 比对 + md5 哈希)。

每个阶段的输入文件 mtime 变化时自动重跑，否则跳过。
集成到现有流水线脚本的最小改动方案。
"""
import hashlib, json, os, time
from pathlib import Path
from typing import List, Optional


class StageCache:
    """阶段缓存：记录输入文件的 mtime + 内容哈希。"""

    def __init__(self, cache_dir: str = ".pipeline_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._state = self._load()

    def _load(self) -> dict:
        f = self.cache_dir / "cache_state.json"
        if f.exists():
            return json.loads(f.read_text())
        return {}

    def _save(self):
        f = self.cache_dir / "cache_state.json"
        f.write_text(json.dumps(self._state, indent=2))

    def _file_hash(self, path: Path) -> str:
        """计算文件前 4KB 的 md5 作为轻量哈希。"""
        h = hashlib.md5()
        try:
            data = path.read_bytes()[:4096]
            h.update(data)
        except Exception:
            pass
        return h.hexdigest()

    def _file_mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    def check(self, stage_name: str, input_patterns: List[str],
              output_patterns: List[str]) -> bool:
        """检查阶段是否有效 (True=跳过, False=需要重跑)。"""
        key = f"stage_{stage_name}"
        cached = self._state.get(key)

        # 检查每个输入文件
        current_sig = {}
        for pattern in input_patterns:
            for f in sorted(Path().glob(pattern)):
                current_sig[str(f)] = {
                    "mtime": self._file_mtime(Path(f)),
                    "hash": self._file_hash(Path(f)),
                }

        # 检查每个输出文件是否存在
        outputs_missing = False
        for pattern in output_patterns:
            if not list(Path().glob(pattern)):
                outputs_missing = True
                break

        if not outputs_missing and cached and cached.get("inputs") == current_sig:
            return True  # 缓存命中，跳过

        # 更新缓存
        self._state[key] = {
            "inputs": current_sig,
            "time": time.time(),
        }
        self._save()
        return False  # 需要重跑

    def invalidate(self, stage_name: str):
        """使某阶段缓存失效（强制重跑）。"""
        key = f"stage_{stage_name}"
        self._state.pop(key, None)
        self._save()


# 便捷装饰器
def cached(stage_name: str, inputs: List[str], outputs: List[str]):
    """装饰器：跳过缓存未失效的阶段。"""
    cache = StageCache()

    def decorator(func):
        def wrapper(*args, **kwargs):
            if cache.check(stage_name, inputs, outputs):
                print(f"  [CACHE] {stage_name}: 输入未变，跳过")
                return None
            print(f"  [RUN] {stage_name}...")
            result = func(*args, **kwargs)
            print(f"  [OK] {stage_name}")
            return result
        return wrapper
    return decorator
