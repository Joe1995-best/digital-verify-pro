"""
Performance baseline regression for VCD parsing.

Measures the time taken to parse known VCD files using the coverage-engine
VCD backend and compares against ``baseline.json``.

Exits with code 1 if any benchmark exceeds 120% of its baseline median.

Usage:
    python benchmark/vcd_parse_benchmark.py
    python benchmark/vcd_parse_benchmark.py --json  # output perf data as JSON
"""

import json
import os
import sys
import time
from pathlib import Path

# Allow running from project root
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

BASELINE_PATH = _REPO / "benchmark" / "baseline.json"
THRESHOLD_RATIO = 1.20  # 120%

# ── Try to import the VCD backend ───────────────────────────────────────────

try:
    from engines.vcd_backend import parse_vcd
except ImportError:
    parse_vcd = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _find_vcd_files() -> list[Path]:
    """Discover VCD files at the project root and under examples/."""
    candidates: list[Path] = []
    for ext in ("*.vcd", "*.VCD"):
        candidates.extend(_REPO.glob(ext))
        examples = _REPO / "examples"
        if examples.is_dir():
            candidates.extend(examples.glob(f"**/{ext}"))
    return sorted(candidates)


def load_baseline() -> dict:
    """Load the baseline JSON; return {} if missing or corrupt."""
    if not BASELINE_PATH.is_file():
        return {}
    try:
        with open(BASELINE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _bench_one(vcd_path: Path, iterations: int = 5) -> float:
    """Run *iterations* parses and return median time in seconds.

    Uses ``parse_vcd`` if available, otherwise simulates with a file-read.
    """
    timings: list[float] = []
    vcd_str = str(vcd_path)
    for _ in range(iterations):
        t0 = time.perf_counter()
        if parse_vcd is not None:
            # noinspection PyCallingNonCallable
            parse_vcd(vcd_str)
        else:
            # Fallback: measure raw file read
            with open(vcd_str, "rb") as f:
                f.read()
        elapsed = time.perf_counter() - t0
        timings.append(elapsed)

    timings.sort()
    n = len(timings)
    if n % 2 == 0:
        median = (timings[n // 2 - 1] + timings[n // 2]) / 2.0
    else:
        median = timings[n // 2]
    return round(median, 6)


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    baseline = load_baseline()
    bench_data = baseline.get("benchmarks", {})

    vcd_files = _find_vcd_files()
    if not vcd_files:
        print("No VCD files found at project root or examples/.", file=sys.stderr)
        return 0  # not a failure — nothing to benchmark

    all_pass = True
    results: dict[str, dict] = {}

    print(f"{'File':<40} {'Baseline(s)':<14} {'Actual(s)':<14} {'Ratio':<10} Status")
    print("-" * 90)

    for vf in vcd_files:
        name = vf.name
        median = _bench_one(vf)
        # Look up baseline
        for bkey, bval in bench_data.items():
            if bval.get("file") == name:
                baseline_sec = bval.get("median_time_sec", 0.0)
                break
        else:
            baseline_sec = 0.0

        if baseline_sec > 0:
            ratio = median / baseline_sec
        else:
            ratio = 0.0

        status = "PASS"
        if ratio > THRESHOLD_RATIO:
            status = "FAIL"
            all_pass = False

        print(f"{name:<40} {baseline_sec:<14.6f} {median:<14.6f} {ratio:<10.2%} {status}")

        results[name] = {
            "file": name,
            "size_bytes": vf.stat().st_size,
            "median_time_sec": median,
            "baseline_sec": baseline_sec,
            "ratio": round(ratio, 4),
            "status": status,
        }

    # JSON output for CI
    if "--json" in sys.argv:
        out = {
            "threshold_ratio": THRESHOLD_RATIO,
            "passed": all_pass,
            "results": results,
        }
        print(json.dumps(out, indent=2))

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
