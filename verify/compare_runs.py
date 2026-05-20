#!/usr/bin/env python3
"""
compare_runs.py — 回归结果对比工具

用法：
  python compare_runs.py --run-a runs/run_20260520_093000 --run-b runs/run_20260520_100000
  python compare_runs.py --latest  # 对比最近两轮
"""
import os, sys, json, argparse
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "runs"


def load_run(run_name: str):
    """加载一轮回归的结果"""
    run_dir = RUNS_DIR / run_name
    results_file = run_dir / "results.json"
    if not results_file.exists():
        print(f"[ERROR] results.json not found in {run_dir}")
        sys.exit(1)
    with open(results_file, encoding="utf-8") as f:
        return json.load(f)


def get_latest_runs(n=2):
    """获取最近 n 轮回归的目录名"""
    if not RUNS_DIR.exists():
        return []
    runs = sorted(
        [d.name for d in RUNS_DIR.iterdir()
         if d.is_dir() and d.name.startswith("run_")],
        reverse=True
    )
    return runs[:n]


def compare(run_a, run_b):
    """对比两轮回归结果，返回分类结果"""
    cases_a = {c["name"]: c for c in run_a["cases"]}
    cases_b = {c["name"]: c for c in run_b["cases"]}

    all_names = set(cases_a) | set(cases_b)

    result = {
        "regression_fail": [],   # 上次 PASS 这次 FAIL
        "fixed": [],             # 上次 FAIL 这次 PASS
        "new_pass": [],          # 上次没跑 这次 PASS
        "new_fail": [],          # 上次没跑 这次 FAIL
        "still_fail": [],        # 两次都 FAIL
        "still_pass": [],        # 两次都 PASS
        "summary": {},
    }

    for name in sorted(all_names):
        a = cases_a.get(name)
        b = cases_b.get(name)
        status_a = a["status"] if a else None
        status_b = b["status"] if b else None

        if status_a == "PASS" and status_b == "FAIL":
            result["regression_fail"].append(name)
        elif status_a == "FAIL" and status_b == "PASS":
            result["fixed"].append(name)
        elif status_a is None and status_b == "PASS":
            result["new_pass"].append(name)
        elif status_a is None and status_b == "FAIL":
            result["new_fail"].append(name)
        elif status_a == "FAIL" and status_b == "FAIL":
            result["still_fail"].append(name)
        elif status_a == "PASS" and status_b == "PASS":
            result["still_pass"].append(name)

    result["summary"] = {
        "run_a": run_a["run_id"],
        "run_b": run_b["run_id"],
        "total": len(all_names),
        "regression_fail": len(result["regression_fail"]),
        "fixed": len(result["fixed"]),
        "new_pass": len(result["new_pass"]),
        "new_fail": len(result["new_fail"]),
        "still_fail": len(result["still_fail"]),
        "still_pass": len(result["still_pass"]),
    }

    return result


def print_comparison(result):
    """打印对比结果"""
    s = result["summary"]
    print(f"=== 回归对比: {s['run_a']} ↔ {s['run_b']} ===\n")

    def print_list(label, items, icon):
        if items:
            print(f"  {icon} {label} ({len(items)})")
            for name in items:
                print(f"      {name}")

    print_list("回归 FAIL（需立即关注）", result["regression_fail"], "🔴")
    print_list("修复 PASS", result["fixed"], "🟢")
    print_list("新增 PASS", result["new_pass"], "✅")
    print_list("新增 FAIL", result["new_fail"], "❌")
    print_list("持续 FAIL", result["still_fail"], "⚠️")
    print_list("持续 PASS", result["still_pass"], "✓")

    print(f"\n=== 概要 ===")
    print(f"  总 case: {s['total']}")
    print(f"  回归 FAIL: {s['regression_fail']}")
    print(f"  修复:     {s['fixed']}")
    print(f"  新增 FAIL: {s['new_fail']}")
    print(f"  持续 FAIL: {s['still_fail']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Compare two regression runs")
    ap.add_argument("--run-a", help="First run (default: latest-1)")
    ap.add_argument("--run-b", help="Second run (default: latest)")
    ap.add_argument("--latest", action="store_true", help="Compare latest two runs")
    args = ap.parse_args()

    if args.latest or (not args.run_a and not args.run_b):
        runs = get_latest_runs(2)
        if len(runs) < 2:
            print(f"[ERROR] Need at least 2 runs to compare. Found {len(runs)}")
            sys.exit(1)
        run_a_name, run_b_name = runs[1], runs[0]
    else:
        run_a_name = args.run_a
        run_b_name = args.run_b or get_latest_runs(1)[0]

    print(f"Loading {run_a_name}...")
    run_a = load_run(run_a_name)
    print(f"Loading {run_b_name}...")
    run_b = load_run(run_b_name)

    result = compare(run_a, run_b)
    print_comparison(result)
