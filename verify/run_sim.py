#!/usr/bin/env python3
"""
run_sim.py — 统一仿真入口

职责：
  1. 解析 build 文件 → 编译（或复用已有 simv）
  2. 解析 regression_list.py 或 --case 参数 → 加载 case
  3. 提交仿真任务 → 收集结果 → 写入 runs/ 目录

用法：
  # 单 case
  python run_sim.py --build build_iverilog --case ctrl_rw

  # 多 case
  python run_sim.py --build build_iverilog --cases ctrl_rw,i2c_write

  # 全量回归
  python run_sim.py --build build_iverilog --regression

  # 只编译不跑
  python build_iverilog.py
"""
import os, sys, json, time, importlib, argparse, subprocess
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "runs"


def resolve_build(name: str):
    """加载 build 配置模块"""
    sys.path.insert(0, str(Path(__file__).parent))
    mod = importlib.import_module(name)
    return mod


def load_case(path: str):
    """加载单个 case 模块"""
    try:
        mod = importlib.import_module(path)
        return {
            "name": getattr(mod, "NAME", path.split(".")[-1]),
            "plusargs": getattr(mod, "PLUSARGS", []),
            "priority": getattr(mod, "PRIORITY", "p2"),
            "base_seq": getattr(mod, "BASE_SEQ", ""),
            "description": getattr(mod, "DESCRIPTION", ""),
            "feature_id": getattr(mod, "FEATURE_ID", ""),
        }
    except ImportError as e:
        print(f"[ERROR] Cannot load case '{path}': {e}")
        return None


def run_single(simv: str, case: dict, run_dir: Path, seed: int = 1):
    """运行单个 case，返回结果"""
    log_path = run_dir / "logs" / f"{case['name']}_s{seed}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [simv, f"+ntb_random_seed={seed}"] + case["plusargs"]
    start = time.time()
    result = subprocess.run(
        " ".join(cmd), shell=True,
        capture_output=True, text=True, timeout=300
    )
    elapsed = time.time() - start

    # 写日志
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# case:      {case['name']}\n")
        f.write(f"# seed:      {seed}\n")
        f.write(f"# started:   {datetime.now().isoformat()}\n")
        f.write(f"# elapsed:   {elapsed:.1f}s\n")
        f.write(f"# result:    {'PASS' if result.returncode == 0 else 'FAIL'}\n")
        f.write("#" + "─" * 56 + "\n")
        f.write(result.stdout)
        if result.stderr:
            f.write("\n# STDERR:\n" + result.stderr)

    uvm_errors = result.stdout.count("UVM_ERROR")
    uvm_fatals = result.stdout.count("UVM_FATAL")
    passed = result.returncode == 0 and uvm_fatals == 0
    if "PASS" in result.stdout and "FAIL" not in result.stdout:
        passed = True
    if "FAIL" in result.stdout and "PASS" not in result.stdout:
        passed = False

    return {
        "name": case["name"],
        "status": "PASS" if passed else "FAIL",
        "priority": case["priority"],
        "seed": seed,
        "log": str(log_path.resolve()),
        "elapsed_s": round(elapsed, 2),
        "uvm_errors": uvm_errors,
        "uvm_fatals": uvm_fatals,
    }


def write_run_results(run_dir: Path, results: list, build_name: str, simv_path: str):
    """写入 results.json + summary.json"""
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "skipped": 0,
        "pass_rate": round(
            sum(1 for r in results if r["status"] == "PASS") / max(len(results), 1) * 100, 1
        ),
        "total_elapsed_s": round(sum(r["elapsed_s"] for r in results), 1),
    }

    run_meta = {
        "run_id": run_dir.name,
        "timestamp": datetime.now().isoformat(),
        "build": build_name,
        "simv": simv_path,
        "cases": results,
        "summary": summary,
    }

    (run_dir / "results.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # 更新 latest 软链
    latest = RUNS_DIR / "latest"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    try:
        os.symlink(run_dir.name, latest, target_is_directory=True)
    except (OSError, NotImplementedError):
        pass  # Windows 可能不支持软链，忽略

    return run_meta


def main():
    ap = argparse.ArgumentParser(description="Unified simulation runner")
    ap.add_argument("--build", default="build_iverilog",
                    help="Build config module name (default: build_iverilog)")
    ap.add_argument("--case", help="Single case to run (module path)")
    ap.add_argument("--cases", help="Comma-separated case module paths")
    ap.add_argument("--regression", action="store_true",
                    help="Run all cases from regression_list.py")
    ap.add_argument("--seeds", type=int, default=1, help="Seeds per case")
    ap.add_argument("--rebuild", action="store_true",
                    help="Force recompile even if simv exists")
    args = ap.parse_args()

    # 1. Load build
    build_mod = resolve_build(args.build)
    simv_path = str(Path(__file__).parent / build_mod.OUTPUT)

    # 2. Compile if needed
    simv = Path(simv_path)
    if args.rebuild or not simv.exists():
        print(f"[BUILD] Compiling with {build_mod.SIMULATOR}...")
        incflags = " ".join(f"-I {d}" for d in build_mod.INCDIRS)
        defines = " ".join(f"-D{d}" for d in build_mod.DEFINES)
        sources = " ".join(build_mod.SOURCES)
        cmd = build_mod.COMPILE_CMD.format(
            output=simv_path, incflags=incflags,
            defines=defines, sources=sources
        )
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[BUILD FAILED]\n{r.stdout}\n{r.stderr}")
            sys.exit(1)
        print(f"[BUILD OK] {simv_path}")

    # 3. Resolve cases
    case_paths = []
    if args.regression:
        sys.path.insert(0, str(Path(__file__).parent))
        reg = importlib.import_module("regression_list")
        case_paths = reg.active_cases()
    elif args.cases:
        case_paths = [c.strip() for c in args.cases.split(",")]
    elif args.case:
        case_paths = [args.case]
    else:
        print("[ERROR] Specify --case, --cases, or --regression")
        sys.exit(1)

    cases = [load_case(p) for p in case_paths]
    cases = [c for c in cases if c]
    if not cases:
        print("[ERROR] No valid cases to run")
        sys.exit(1)

    print(f"[RUN] {len(cases)} case(s) x {args.seeds} seed(s)")

    # 4. Run
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"run_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for case in cases:
        for seed in range(1, args.seeds + 1):
            r = run_single(simv_path, case, run_dir, seed)
            all_results.append(r)
            icon = "✓" if r["status"] == "PASS" else "✗"
            print(f"  {icon} {r['name']} (seed={r['seed']}) {r['status']} ({r['elapsed_s']}s)")

    # 5. Write results
    meta = write_run_results(run_dir, all_results, args.build, simv_path)
    s = meta["summary"]
    print(f"\n[DONE] {run_dir.name}")
    print(f"  {s['passed']}/{s['total']} PASS ({s['pass_rate']}%)")
    print(f"  FAILED: {s['failed']}")

    if s["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
