"""
Fault injector — light-weight simulation fault injection plan generator.

WARNING: FIXME — This is a placeholder/stub. The module defines the fault
injection *patterns* but does not perform actual DPI/PLI-level injection.

Fault modes defined:
    1. BUS_HANG     — apb_write() followed by "force psel = 0"
    2. RESET_GLITCH — inject a positive glitch on active-low rst_n
    3. SEU          — randomly flip a single bit in ctrl_reg_q

Output: ``fault_injection_plan.json``
"""

import json
import random
from enum import Enum
from typing import Any


class FaultMode(Enum):
    """Injection fault modes supported by the plan generator."""
    BUS_HANG = "bus_hang"
    RESET_GLITCH = "reset_glitch"
    SEU = "seu"


# ── Plan generation ─────────────────────────────────────────────────────────

_FIXTURE_MAP = {
    FaultMode.BUS_HANG: {
        "description": "Force APB select low after write to hang bus",
        "trigger": "post apb_write()",  # FIXME: requires PLI callback
        "method": (
            "force psel = 0;  // FIXME: actual force timing depends on simulator\n"
            "#100ns;   // hold for 100 ns\n"
            "release psel;"
        ),
        "expected_effect": "APB transfer not completing — pready stays low",
    },
    FaultMode.RESET_GLITCH: {
        "description": "Posedge glitch on active-low rst_n during reset",
        "trigger": "while (rst_n == 0)",  # FIXME: needs precise timing
        "method": (
            "// FIXME: glitch insertion — use force/release or DPI\n"
            "force rst_n = 1;  // illegal posedge during reset\n"
            "#5ns;\n"
            "release rst_n;"
        ),
        "expected_effect": "Possible metastability or incomplete reset",
    },
    FaultMode.SEU: {
        "description": "Single event upset — flip one random bit of ctrl_reg_q",
        "trigger": "randomised during simulation",  # FIXME: needs seeding
        "method": (
            "// FIXME: bit flip via DPI or VPI\n"
            "$random_bit = $urandom_range(31, 0);\n"
            "force ctrl_reg_q[$random_bit] = ~ctrl_reg_q[$random_bit];"
        ),
        "expected_effect": "Transient register corruption",
    },
}


def generate_plan(
    *,
    modes: list[FaultMode] | None = None,
    seed: int = 42,
    iterations: int = 10,
) -> dict[str, Any]:
    """Generate a fault-injection plan JSON dict.

    Args:
        modes: Fault modes to include (default: all).
        seed: Random seed for SEU bit selection.
        iterations: Number of injection attempts.

    Returns:
        JSON-serialisable plan.
    """
    if modes is None:
        modes = list(FaultMode)

    random.seed(seed)

    injections: list[dict[str, Any]] = []
    for mode in modes:
        for i in range(iterations):
            fixture = _FIXTURE_MAP[mode]
            entry: dict[str, Any] = {
                "id": f"{mode.value}_{i:04d}",
                "mode": mode.value,
                "iteration": i,
                "description": fixture["description"],
                "trigger": fixture["trigger"],
                "method": fixture["method"],
                "expected_effect": fixture["expected_effect"],
            }
            if mode == FaultMode.SEU:
                entry["target_bit"] = random.randint(0, 31)
            injections.append(entry)

    plan: dict[str, Any] = {
        "version": "1.0.0",
        "note": "FIXME — auto-generated plan requires manual review and PLI/DPI hooks",
        "seed": seed,
        "iterations_per_mode": iterations,
        "total_injections": len(injections),
        "injections": injections,
    }
    return plan


def generate_plan_file(output_path: str = "fault_injection_plan.json", **kwargs: Any) -> str:
    """Generate plan and write to *output_path*. Returns the JSON text."""
    plan = generate_plan(**kwargs)
    text = json.dumps(plan, indent=2, ensure_ascii=False)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text
