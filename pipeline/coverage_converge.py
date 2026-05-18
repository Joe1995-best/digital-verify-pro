#!/usr/bin/env python3
"""
coverage_converge.py v2 — Automated coverage convergence loop.

Full flow:
  1. Compile RTL + TB (with -g2005-sv for SV support)
  2. Simulate (vvp), capture log + VCD
  3. Coverage analysis (toggle metrics + gaps)
  4. Generate gap-targeted SV test sequences
  5. Re-compile ORIGINAL + NEW gap sequences
  6. Re-simulate
  7. Compare coverage: before vs after
  8. Loop until convergence or max iterations

Usage:
  python coverage_converge.py --rtl <file> --tb <file> --module <name>
                              [--clk <clk>] [--target-cov 90] [--max-iter 5]
"""

import os, sys, json, subprocess, time, shutil, argparse
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass

SCRIPT_DIR = os.path.dirname(__file__)
ENGINE_DIR = os.path.join(SCRIPT_DIR, "..", "engines")

@dataclass
class IterResult:
    iteration: int
    toggle_cov: float
    overall_cov: float
    full_tgl: int
    stuck: int
    crit_gaps: int
    total_gaps: int
    new_seqs: int
    elapsed_s: float
    ts: str


class CoverageConverger:

    def __init__(self, rtl_path: str, tb_path: str, module: str,
                 clk: str = "", target: float = 90.0, max_iter: int = 5,
                 outdir: str = ""):
        self.rtl = os.path.abspath(rtl_path)
        self.tb = os.path.abspath(tb_path)
        self.module = module
        self.clk = clk
        self.target = target
        self.max_iter = max_iter
        self.outdir = os.path.abspath(outdir or f"cov_{module}")

        self.wd = os.path.join(self.outdir, "work")
        os.makedirs(self.wd, exist_ok=True)

        self.sim_exe = os.path.join(self.wd, f"{module}_sim.vvp")
        self.vcd = os.path.join(self.wd, f"{module}.vcd")
        self.gaps_json = os.path.join(self.wd, "gaps.json")
        self.log = os.path.join(self.wd, "sim.log")
        self.seq_dir = os.path.join(self.wd, "gap_seqs")
        os.makedirs(self.seq_dir, exist_ok=True)

        self.history: List[IterResult] = []

    # ── Step 1: Compile ────────────────────────────────────────────────

    def _compile(self, extra_sources: List[str] = None) -> bool:
        """Compile RTL + TB (+ optional gap sequences) into .vvp"""
        srcs = [self.rtl, self.tb]
        if extra_sources:
            for s in extra_sources:
                if os.path.exists(s):
                    srcs.append(s)

        cmd = ["iverilog", "-g2005-sv", "-o", self.sim_exe] + srcs
        print(f"  [COMPILE] {' '.join(cmd)}")

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                          cwd=os.path.dirname(self.rtl))
        if r.returncode not in (0, 1):  # iverilog exits 1 for warnings
            print(f"  [X] Compile failed: {r.stderr[:300]}")
            return False
        for line in r.stderr.split("\n"):
            if "error" in line.lower():
                print(f"      {line.strip()}")
        return True

    # ── Step 2: Simulate ───────────────────────────────────────────────

    def _simulate(self) -> bool:
        """Run vvp, return True if simulation produced VCD"""
        if not os.path.exists(self.sim_exe):
            print(f"  [X] No sim binary: {self.sim_exe}")
            return False

        old_vcd = os.path.join(self.wd, f"{self.module}.vcd")
        if os.path.exists(old_vcd):
            os.remove(old_vcd)

        r = subprocess.run(["vvp", self.sim_exe],
                          capture_output=True, text=True, timeout=120,
                          cwd=self.wd)

        with open(self.log, "w") as f:
            f.write(r.stdout)
            if r.stderr:
                f.write(f"\n--- STDERR ---\n{r.stderr}")

        passes = r.stdout.count("PASS:")
        fails = r.stdout.count("FAIL:")
        total = passes + fails
        print(f"  [SIM] {passes}/{total} tests passed" +
              ("!" if fails == 0 else f" ({fails} FAILS)"))
        for line in r.stdout.split("\n"):
            if "FAIL" in line:
                print(f"       {line.strip()}")

        vcd_found = False
        for fname in os.listdir(self.wd):
            if fname.endswith(".vcd"):
                vcd_found = True
                break
        if not vcd_found:
            print(f"  [X] No VCD produced")
            return False
        return True

    # ── Step 3: Coverage analysis ──────────────────────────────────────

    def _analyze(self) -> Dict:
        """Run coverage_engine, return metrics dict"""
        # Find VCD
        vcd = None
        for f in os.listdir(self.wd):
            if f.endswith(".vcd"):
                vcd = os.path.join(self.wd, f)
                break
        if not vcd:
            return {}

        cov_json = os.path.join(self.wd, "cov.json")
        cmd = [
            sys.executable, os.path.join(ENGINE_DIR, "coverage_engine.py"),
            "--vcd", vcd, "--module", self.module,
            "--json", cov_json, "--gaps", self.gaps_json,
        ]
        if self.clk:
            cmd += ["--clk", self.clk]

        subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        metrics = {"toggle": 0, "overall": 0, "full_tgl": 0,
                   "stuck": 0, "crit_gaps": 0, "total_gaps": 0}

        if os.path.exists(cov_json):
            with open(cov_json) as f:
                d = json.load(f)
            metrics["toggle"] = d.get("toggle", 0)
            metrics["overall"] = d.get("overall", 0)
            ss = d.get("signal_stats", {})
            metrics["full_tgl"] = ss.get("full_toggle", 0)
            metrics["stuck"] = ss.get("stuck", 0)

        if os.path.exists(self.gaps_json):
            with open(self.gaps_json) as f:
                d = json.load(f)
            metrics["crit_gaps"] = sum(1 for g in d.get("gaps", [])
                                        if g.get("severity", 0) >= 4)
            metrics["total_gaps"] = len(d.get("gaps", []))

        return metrics

    # ── Step 4: Generate gap sequences ─────────────────────────────────

    def _gen_gap_seqs(self) -> int:
        """Run gap_plugin → produces SV files in seq_dir. Returns count."""
        cmd = [
            sys.executable, os.path.join(SCRIPT_DIR, "coverage_gap_plugin.py"),
            "--gaps", self.gaps_json, "--out", self.wd,
            "--plain",
        ]
        if self.module:
            cmd += ["--module", self.module]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        seq_dir2 = os.path.join(self.wd, "coverage")
        count = 0
        if os.path.exists(seq_dir2):
            for f in os.listdir(seq_dir2):
                if f.endswith("_seq.sv"):
                    src = os.path.join(seq_dir2, f)
                    dst = os.path.join(self.seq_dir, f)
                    shutil.copy2(src, dst)
                    count += 1
        return count

    # ── Full iteration ────────────────────────────────────────────────

    def _run_iter(self, iteration: int, extra_srcs: List[str] = None) -> IterResult:
        t0 = time.time()
        print(f"\n{'='*50} ITERATION {iteration}/{self.max_iter} {'='*50}")

        ok = self._compile(extra_srcs) and self._simulate()
        if not ok:
            return IterResult(iteration, 0, 0, 0, 0, 0, 0, 0, 0, "")

        m = self._analyze()
        new_seqs = self._gen_gap_seqs() if iteration < self.max_iter else 0

        snap = IterResult(
            iteration=iteration,
            toggle_cov=m.get("toggle", 0),
            overall_cov=m.get("overall", 0),
            full_tgl=m.get("full_tgl", 0),
            stuck=m.get("stuck", 0),
            crit_gaps=m.get("crit_gaps", 0),
            total_gaps=m.get("total_gaps", 0),
            new_seqs=new_seqs,
            elapsed_s=time.time()-t0,
            ts=str(datetime.now()),
        )
        self.history.append(snap)
        print(f"  [SNAP] toggle={snap.toggle_cov}% crit_gaps={snap.crit_gaps} "
              f"new_seqs={snap.new_seqs} elapsed={snap.elapsed_s:.1f}s")
        return snap

    # ── Convergence run ────────────────────────────────────────────────

    def run(self) -> List[IterResult]:
        print(f"\n{'='*60}")
        print(f"  COVERAGE CONVERGENCE: {self.module}")
        print(f"  Target: {self.target}%  Max iters: {self.max_iter}")
        print(f"  RTL: {os.path.basename(self.rtl)}")
        print(f"  TB:  {os.path.basename(self.tb)}")
        print(f"{'='*60}")

        # Copy sources to work dir
        shutil.copy2(self.rtl, self.wd)
        shutil.copy2(self.tb, self.wd)

        # Iteration 1: baseline (no gap sequences)
        self._run_iter(1)
        self._save_checkpoint()

        # Iterations 2+: inject gap sequences
        for i in range(2, self.max_iter + 1):
            # Gather gap sequences as extra sources
            gap_srcs = [os.path.join(self.seq_dir, f)
                       for f in sorted(os.listdir(self.seq_dir))
                       if f.endswith(".sv")] if os.path.exists(self.seq_dir) else []

            if not gap_srcs:
                print(f"  [SKIP] No gap sequences to inject — coverage converged")
                break

            self._run_iter(i, gap_srcs)
            self._save_checkpoint()

            # Auto-stop if no critical gaps
            if self.history and self.history[-1].crit_gaps == 0:
                print(f"\n  [OK] Zero critical gaps — converged!")
                break

        self._save_report()
        return self.history

    # ── Reporting ──────────────────────────────────────────────────────

    def _save_checkpoint(self):
        path = os.path.join(self.outdir, "checkpoint.json")
        with open(path, "w") as f:
            json.dump({
                "module": self.module,
                "target": self.target,
                "history": [{
                    "iter": h.iteration,
                    "toggle": h.toggle_cov,
                    "overall": h.overall_cov,
                    "full": h.full_tgl,
                    "stuck": h.stuck,
                    "crit": h.crit_gaps,
                    "total": h.total_gaps,
                    "new": h.new_seqs,
                    "elapsed": h.elapsed_s,
                } for h in self.history],
            }, f, indent=2)

    def _save_report(self):
        path = os.path.join(self.outdir, "convergence_report.md")
        lines = [
            f"# Coverage Convergence: {self.module}",
            f"",
            f"**Date:** {datetime.now()}",
            f"**Target:** {self.target}%  **Iterations:** {len(self.history)}",
            f"",
            f"## History",
            f"",
            f"| Iter | Toggle% | Overall% | Full | Stuck | CritGaps | NewSeqs | Time(s) |",
            f"|------|---------|----------|------|-------|----------|---------|---------|",
        ]
        for h in self.history:
            lines.append(f"| {h.iteration} | {h.toggle_cov}% | {h.overall_cov}% | "
                        f"{h.full_tgl} | {h.stuck} | {h.crit_gaps} | "
                        f"{h.new_seqs} | {h.elapsed_s:.1f} |")

        if len(self.history) >= 2:
            f, l = self.history[0], self.history[-1]
            lines += [
                f"",
                f"## Improvement",
                f"",
                f"| Metric | Start | End | Delta |",
                f"|--------|-------|-----|-------|",
                f"| Toggle | {f.toggle_cov}% | {l.toggle_cov}% | **+{l.toggle_cov-f.toggle_cov:.1f}%** |",
                f"| Full Tgl | {f.full_tgl} | {l.full_tgl} | **+{l.full_tgl-f.full_tgl}** |",
                f"| Stuck | {f.stuck} | {l.stuck} | **-{f.stuck-l.stuck}** |",
                f"| Crit Gaps | {f.crit_gaps} | {l.crit_gaps} | **-{f.crit_gaps-l.crit_gaps}** |",
            ]

        with open(path, "w") as f:
            f.write("\n".join(lines))
        print(f"  [REPORT] {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Coverage Convergence Loop v2")
    p.add_argument("--rtl", required=True)
    p.add_argument("--tb", required=True)
    p.add_argument("--module", required=True)
    p.add_argument("--clk", default="")
    p.add_argument("--target", type=float, default=90.0)
    p.add_argument("--max-iter", type=int, default=5)
    p.add_argument("--outdir", default="")
    a = p.parse_args()

    c = CoverageConverger(a.rtl, a.tb, a.module, a.clk, a.target, a.max_iter, a.outdir)
    h = c.run()

    if h:
        f, l = h[0], h[-1]
        print(f"\n{'='*60}")
        print(f"  RESULT: {f.toggle_cov}% -> {l.toggle_cov}% "
              f"(+{l.toggle_cov-f.toggle_cov:.1f}%)")
        print(f"  Gaps:   {f.crit_gaps} -> {l.crit_gaps} critical")
        print(f"  New seqs: {sum(x.new_seqs for x in h)} total")
        print(f"{'='*60}")
