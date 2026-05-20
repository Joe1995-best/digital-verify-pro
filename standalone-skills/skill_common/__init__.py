#!/usr/bin/env python3
"""
skill_common — Shared utilities for digital-verify-pro standalone skills.

Provides unified:
  - Logging (skill_logger)
  - Exit codes (ExitCode enum)
  - Result reporting (write_result)
  - File/spec helpers (find_spec, safe_read)
  - Args parsing conventions

Usage:
    from skill_common import get_logger, ExitCode, write_result
    logger = get_logger(__name__)
    logger.info("processing...")
    write_result({"status": "pass", "tests": 10, "passed": 10})
    sys.exit(ExitCode.SUCCESS)
"""

import os, sys, json, logging, argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
class ExitCode:
    """Unified exit code convention for all skills."""
    SUCCESS = 0
    INPUT_ERROR = 1        # missing/invalid input args
    SPEC_ERROR = 2         # spec YAML parsing failure
    RUNTIME_ERROR = 3      # runtime exception (file not found, tool failure)
    VALIDATION_ERROR = 4   # output validation failed
    DEPENDENCY_ERROR = 5   # missing dependency (tool, library)
    TIMEOUT = 6            # execution exceeded expected time
    CONFIG_ERROR = 7       # config file parse failure
    INTERNAL_ERROR = 99    # unexpected bug

    _descriptions = {
        0: "Success",
        1: "Input/argument error — check CLI args and spec path",
        2: "Spec file parse failure — validate YAML syntax",
        3: "Runtime error — check logs for exception details",
        4: "Output validation failed — generated output didn't pass checks",
        5: "Missing dependency — required tool or library not found",
        6: "Execution timed out",
        7: "Config file error — check config.yaml",
        99: "Internal error — unexpected exception",
    }

    @classmethod
    def describe(cls, code: int) -> str:
        return cls._descriptions.get(code, f"Unknown exit code {code}")

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
_LOG_FORMAT = "[%(levelname)s] %(name)s: %(message)s"
_LOG_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO,
               "warn": logging.WARNING, "error": logging.ERROR}

def get_logger(name: str, level: str = "info") -> logging.Logger:
    """Get a formatted logger. Output goes to stderr (reserving stdout for data)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(_LOG_LEVELS.get(level, logging.INFO))
    logger.propagate = False
    return logger

# ---------------------------------------------------------------------------
# Result writer
# ---------------------------------------------------------------------------
_RESULT_SCHEMA = {
    "type": "object",
    "required": ["status", "timestamp"],
    "properties": {
        "status": {"type": "string", "enum": ["pass", "fail", "error", "skip"]},
        "timestamp": {"type": "string", "format": "date-time"},
        "module": {"type": "string"},
        "summary": {"type": "string"},
        "metrics": {"type": "object"},
        "outputs": {"type": "object"},
        "errors": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": {"type": "object"}},
    }
}

def write_result(data: Dict[str, Any], path: str = "result.json") -> str:
    """Write a standardized result.json. Returns absolute path."""
    payload = {
        "status": data.get("status", "pass"),
        "timestamp": datetime.now().isoformat(),
        "module": data.get("module", ""),
        "summary": data.get("summary", ""),
        "metrics": data.get("metrics", {}),
        "outputs": data.get("outputs", {}),
        "errors": data.get("errors", []),
        "warnings": data.get("warnings", []),
    }
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return abs_path

def read_result(path: str = "result.json") -> Optional[Dict[str, Any]]:
    """Read a result.json produced by a skill."""
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Load a YAML config file, returning dict. Returns {} on missing file."""
    try:
        import yaml
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
    except ImportError:
        return {}

# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------
def find_spec(spec_path: Optional[str]) -> Optional[str]:
    """Resolve a spec file path. Returns None if not found with logging."""
    if spec_path and os.path.isfile(spec_path):
        return os.path.abspath(spec_path)
    # Search common locations
    candidates = ["spec.yml", "../spec.yml", "../../spec.yml"]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None

# ---------------------------------------------------------------------------
# Standardized argument parser (convention)
# ---------------------------------------------------------------------------
def common_args(description: str = "") -> argparse.ArgumentParser:
    """Create a standardized argument parser with common flags."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--spec", type=str, help="Path to spec YAML file")
    parser.add_argument("--out", type=str, default="output",
                        help="Output directory (default: output)")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Path to config.yaml (optional)")
    parser.add_argument("--log-level", type=str, default="info",
                        choices=["debug", "info", "warn", "error"],
                        help="Logging level (default: info)")
    parser.add_argument("--result", type=str, default="result.json",
                        help="Path to write result.json")
    return parser
