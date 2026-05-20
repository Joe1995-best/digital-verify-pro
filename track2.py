#!/usr/bin/env python3
"""
track2.py — Pipeline Orchestrator (Track 2: Spec-driven UVM Pipeline)

Orchestrates the agentic UVM verification pipeline phases with
checkpoint/resume support, dependency management, and timing.
"""

import os
import sys
import json
import time
import hashlib
import subprocess
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.join(SCRIPT_DIR, "pipeline")

# Pipeline phase definitions
PIPELINE_PHASES = {
    "spec-analyzer": {
        "script": "run_spec_analyzer.py",
        "description": "Parse spec → verification plan + interface list + register map",
        "output": ["output/architect/interface-list.yml", "output/architect/register-map.yml", "output/architect/test-scenarios.yml"],
    },
    "ral-gen": {"script": "run_ral_gen.py","description": "Generate UVM RAL model (registers to uvm_reg_block)","depends_on": ["spec-analyzer"],"output": ["rtl/verification/env/ral/"],},"rtl-gen": {
        "script": "run_rtl_gen.py",
        "description": "Generate synthesizable RTL from spec register definitions",
        "depends_on": ["spec-analyzer"],
        "output": ["rtl/rtl/"],
    },
    "ral-gen": {
        "script": "run_ral_gen.py",
        "description": "Generate UVM RAL model from register definitions (IEEE 1800.2)",
        "depends_on": ["spec-analyzer"],
        "output": ["output/rtl/verification/env/ral/"],
    },
    "env-builder": {
        "script": "run_env_builder.py",
        "description": "Generate UVM environment skeleton (tb_top, agents, drivers, monitors)",
        "depends_on": ["spec-analyzer", "ral-gen"],
        "output": ["output/rtl/verification/env/"],
    },
    "test-generator": {
        "script": "run_test_generator.py",
        "description": "Generate test sequences per verification scenario",
        "depends_on": ["env-builder"],
        "output": ["output/rtl/verification/env/sequences/"],
    },
    "tb-gen": {
        "script": "tb_gen.py",
        "description": "Generate UVM test sequences from test_plan.yml (feature-driven)",
        "depends_on": ["spec-analyzer"],
        "output": ["output/tests/", "verify/regression_list.py"],
    },
    "assertion-gen": {
        "script": "run_assertion_gen.py",
        "description": "Generate SVA assertions per interface",
        "depends_on": ["env-builder"],
        "output": ["output/rtl/verification/env/assertions/"],
    },
    "scoreboard-gen": {
        "script": "run_scoreboard_gen.py",
        "description": "Generate scoreboard and checker logic",
        "depends_on": ["test-generator"],
        "output": ["output/rtl/verification/env/scoreboard/"],
    },
    "coverage-plan": {
        "script": "run_coverage_plan.py",
        "description": "Define functional cover groups and coverage goals",
        "depends_on": ["spec-analyzer"],
        "output": ["output/rtl/verification/env/coverage/"],
    },
    "doc-gen": {
        "script": "run_doc_gen.py",
        "description": "Generate verification sign-off close report",
        "depends_on": ["spec-analyzer"],
        "output": ["output/docs/verification-close-report.md"],
    },
    "sw-header-gen": {
        "script": "run_sw_header_gen.py",
        "description": "Generate C header with register addresses and field bit definitions",
        "depends_on": ["spec-analyzer"],
        "output": ["output/sw/<module>.h"],
    },
    "formal-check": {
        "script": "run_formal.py",
        "description": "Generate and run formal properties (SVA + SymbiYosys)",
        "depends_on": ["spec-analyzer", "rtl-gen"],
        "output": ["architect/formal/"],
        "suggested_effort": "L3",
    },
}

PIPELINE_ORDER = ["spec-analyzer", "rtl-gen", "ral-gen", "env-builder", "test-generator", "assertion-gen",
                  "scoreboard-gen", "tb-gen", "coverage-plan", "doc-gen", "sw-header-gen", "formal-check"]

CHECKPOINT_FILE = ".pipeline_state.json"


def _spec_hash(spec_path: str) -> str:
    """Compute a hash of the spec file for checkpoint validity."""
    if not spec_path or not os.path.exists(spec_path):
        return ""
    with open(spec_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:12]


class PipelineRunner:
    """Orchestrates the agentic UVM verification pipeline (Track 2)."""

    def __init__(self, spec_path: str, outdir: str = "",
                 phases: Optional[List[str]] = None,
                 skip_checks: bool = False,
                 resume: bool = False):
        self.spec_path = os.path.abspath(spec_path) if spec_path else ""
        self.outdir = os.path.abspath(outdir) if outdir else os.path.join(SCRIPT_DIR, "output")
        self.phases = phases or list(PIPELINE_ORDER)
        self.skip_checks = skip_checks
        self.resume = resume
        self.results: Dict[str, dict] = {}
        self.start_time = time.time()
        self.phase_timings: Dict[str, float] = {}
        self.spec_hash = _spec_hash(self.spec_path)

    def validate_spec(self) -> bool:
        """Check spec file exists and is valid YAML."""
        if not self.spec_path or not os.path.exists(self.spec_path):
            print(f"  [X] Spec file not found: {self.spec_path}")
            return False
        try:
            import yaml
            with open(self.spec_path, 'r', encoding='utf-8-sig') as f:
                yaml.safe_load(f)
            return True
        except yaml.YAMLError as e:
            print(f"  [X] Invalid YAML in spec: {e}")
            return False

    def _checkpoint_path(self) -> str:
        """Full path to the checkpoint state file."""
        return os.path.join(self.outdir, CHECKPOINT_FILE)

    def _save_checkpoint(self):
        """Save current pipeline state to checkpoint file."""
        state = {
            "spec_hash": self.spec_hash,
            "spec_path": self.spec_path,
            "outdir": self.outdir,
            "phases": self.phases,
            "results": {}
        }
        for phase, result in self.results.items():
            # Strip bulky stdout/stderr from checkpoint
            slim = {k: v for k, v in result.items() if k not in ("stdout", "stderr")}
            state["results"][phase] = slim

        try:
            os.makedirs(self.outdir, exist_ok=True)
            with open(self._checkpoint_path(), "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"  [!] Could not save checkpoint: {e}")

    def _load_checkpoint(self) -> bool:
        """Load checkpoint state for resume. Returns True if valid checkpoint found."""
        path = self._checkpoint_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path) as f:
                state = json.load(f)

            # Validate checkpoint matches current run
            if state.get("spec_hash") != self.spec_hash:
                print(f"  [!] Spec file changed since checkpoint (hash mismatch)")
                print(f"      Old: {state.get('spec_hash')}  New: {self.spec_hash}")
                return False
            if state.get("outdir") != self.outdir:
                return False

            self.results = state.get("results", {})
            return True
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  [!] Corrupt checkpoint: {e}")
            return False

    def check_dependencies(self, phase: str) -> bool:
        """Check if dependencies for a phase are satisfied."""
        if self.skip_checks:
            return True
        deps = PIPELINE_PHASES.get(phase, {}).get("depends_on", [])
        for dep in deps:
            if dep not in self.phases and dep not in self.results:
                print(f"  [!] Dependency '{dep}' not in phase list and not yet run")
                return False
            dep_result = self.results.get(dep, {})
            if dep_result.get("returncode", 0) != 0 and dep not in self.phases[:self.phases.index(phase)]:
                print(f"  [!] Dependency '{dep}' failed or wasn't run")
                return False
        return True

    def run_phase(self, phase: str, phase_index: int, total: int) -> dict:
        """Execute a single pipeline phase."""
        phase_info = PIPELINE_PHASES.get(phase)
        if not phase_info:
            print(f"  [X] Unknown phase: {phase}")
            return {"phase": phase, "returncode": -1, "error": "Unknown phase"}

        script = os.path.join(PIPELINE_DIR, phase_info["script"])
        if not os.path.exists(script):
            print(f"  [X] Script not found: {script}")
            return {"phase": phase, "returncode": -1, "error": f"Script {phase_info['script']} not found"}

        if not self.check_dependencies(phase):
            print(f"  [!] Skipping {phase} — dependencies not met")
            return {"phase": phase, "returncode": -1, "error": "Dependencies not met", "skipped": True}

        print(f"")
        print(f"  {'─'*56}")
        print(f"  [{phase_index+1}/{total}] {phase}")
        print(f"  {phase_info['description']}")
        print(f"  {'─'*56}")

        t0 = time.time()
        cmd = [sys.executable, script]
        if self.spec_path:
            cmd.extend(["--spec", self.spec_path])
        cmd.extend(["--out", self.outdir])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=300, cwd=PIPELINE_DIR,
            )
            elapsed = time.time() - t0
            returncode = result.returncode
            stdout = result.stdout
            stderr = result.stderr

            # Print output
            if stdout.strip():
                for line in stdout.rstrip().split("\n"):
                    print(f"    {line}")
            if stderr.strip():
                for line in stderr.rstrip().split("\n"):
                    print(f"    ! {line}")

            # Calculate ETA based on average phase time
            avg_time = (time.time() - self.start_time) / (phase_index + 1)
            remaining = total - phase_index - 1
            eta_str = f"ETA ~{avg_time * remaining:.1f}s" if remaining > 0 else ""

            print(f"  [OK] {phase} completed in {elapsed:.1f}s {eta_str}")

            self.phase_timings[phase] = elapsed

            return {
                "phase": phase,
                "returncode": returncode,
                "elapsed": elapsed,
                "stdout": stdout,
                "stderr": stderr,
            }

        except subprocess.TimeoutExpired:
            print(f"  [X] {phase} timed out after 300s")
            return {"phase": phase, "returncode": -1, "error": "Timeout"}
        except Exception as e:
            print(f"  [X] {phase} failed: {e}")
            return {"phase": phase, "returncode": -1, "error": str(e)}

    def run(self) -> dict:
        """Execute the full pipeline with checkpoint/resume support."""
        print(f"")
        print(f"{'='*60}")
        print(f"[PIPELINE] Digital Verify Pro — UVM Pipeline (Track 2)")
        if self.spec_path:
            print(f"   Spec: {self.spec_path}")
        print(f"   Output: {self.outdir}")
        print(f"   Phases: {len(self.phases)} ({', '.join(self.phases)})")
        print(f"{'='*60}")

        if self.spec_path and not self.validate_spec():
            print(f"  [X] Spec validation failed. Aborting pipeline.")
            return {"success": False, "error": "Invalid spec", "results": self.results}

        os.makedirs(self.outdir, exist_ok=True)

        # ── Resume mode: load checkpoint and skip completed phases ──
        if self.resume:
            if self._load_checkpoint():
                completed = [p for p in self.phases
                             if p in self.results
                             and self.results[p].get("returncode") == 0]
                if completed:
                    print(f"  [RESUME] Resuming pipeline — {len(completed)} phases already completed")
                    for p in completed:
                        elapsed = self.results[p].get("elapsed", 0)
                        print(f"     [OK] {p} ({elapsed:.1f}s)")
                    # Remove completed phases from the run list
                    self.phases = [p for p in self.phases if p not in completed]
                    if not self.phases:
                        print(f"  [OK] All phases already completed! Nothing to resume.")
                        total_orig = len(self.results)
                        print(f"\n{'='*60}")
                        print(f"[PIPELINE] All {total_orig} phases already completed successfully.")
                        print(f"{'='*60}")
                        return {
                            "success": True,
                            "elapsed": 0,
                            "total": total_orig,
                            "passed": total_orig,
                            "failed": 0,
                            "skipped": 0,
                            "results": self.results,
                        }
                else:
                    print(f"  [RESUME] Checkpoint found but no completed phases, starting fresh")
            else:
                print(f"  [RESUME] No valid checkpoint found, starting fresh")
        else:
            # Fresh run: clean old checkpoint
            cp = self._checkpoint_path()
            if os.path.exists(cp):
                try:
                    os.remove(cp)
                except OSError:
                    pass

        # ── Restore start_time offset for ETA calculations ──
        # If resuming, account for time already spent in completed phases
        if not hasattr(self, 'start_time') or self.resume:
            self.start_time = time.time()

        total = len(self.phases)
        total_orig = len(self.results) + total
        passed = sum(1 for r in self.results.values() if r.get("returncode") == 0)
        failed = sum(1 for r in self.results.values() if r.get("returncode", 1) != 0 and not r.get("skipped"))
        skipped = sum(1 for r in self.results.values() if r.get("skipped"))

        for i, phase in enumerate(self.phases):
            result = self.run_phase(phase, i, total)

            self.results[phase] = result
            self._save_checkpoint()
            if result.get("returncode") == 0:
                passed += 1
            elif result.get("skipped"):
                skipped += 1
            else:
                failed += 1
                if self.phases and phase in PIPELINE_ORDER:
                    print(f"  [!] Pipeline halted at {phase}")
                    break

        elapsed = time.time() - self.start_time

        print(f"")
        print(f"{'='*60}")
        print(f"[PIPELINE] Summary — {elapsed:.1f}s total")
        print(f"{'='*60}")
        print(f"   Phases:   {total_orig} total, {passed} passed, {failed} failed, {skipped} skipped")
        print(f"   Output:   {self.outdir}")
        if self.spec_path:
            plan_path = os.path.join(self.outdir, "verification-plan.md")
            if os.path.exists(plan_path):
                print(f"   Plan:     {plan_path}")
            env_dir = os.path.join(self.outdir, "rtl", "verification", "env")
            if os.path.exists(env_dir):
                print(f"   UVM Env:  {env_dir}/")
        print(f"{'='*60}")
        print(f"")

        # Clean up checkpoint on full success
        if failed == 0:
            try:
                os.remove(self._checkpoint_path())
            except (OSError, FileNotFoundError):
                pass

        return {
            "success": failed == 0,
            "elapsed": elapsed,
            "total": total_orig,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "results": self.results,
        }
