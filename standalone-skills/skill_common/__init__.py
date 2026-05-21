#!/usr/bin/env python3
"""
skill_common — Shared utilities for digital-verify-pro standalone skills.

Provides unified:
  - Logging (get_logger)
  - Exit codes (ExitCode enum)
  - Result reporting (write_result, read_result)
  - Input/Output validation (validate_inputs, validate_outputs)
  - Config loader (load_config)
  - Spec helpers (find_spec)
  - Args parsing (common_args)

Usage:
    from skill_common import get_logger, ExitCode, write_result
    logger = get_logger(__name__)
    write_result({"status": "pass", "module": "test", "metrics": {"total": 10}})
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
    candidates = ["spec.yml", "../spec.yml", "../../spec.yml"]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None

# ---------------------------------------------------------------------------
# Input/Output validation (contract enforcement)
# ---------------------------------------------------------------------------
def validate_inputs(args, required_args: list = None, schema_path: str = None) -> list:
    """
    Validate CLI inputs against required args list and optional JSON Schema.
    Returns list of error dicts (empty = pass).
    """
    errors = []
    if required_args:
        for arg in required_args:
            val = getattr(args, arg, None)
            if val is None or (isinstance(val, (str, list)) and not val):
                errors.append({"code": 1, "field": arg, "message": f"Required argument --{arg.replace('_', '-')} is missing"})
    if schema_path and os.path.isfile(schema_path):
        try:
            import yaml, json, jsonschema
            if args.spec and os.path.isfile(args.spec):
                with open(args.spec, encoding='utf-8') as f:
                    data = yaml.safe_load(f) if args.spec.endswith(('.yml', '.yaml')) else json.load(f)
                with open(schema_path, encoding='utf-8') as f:
                    schema = json.load(f)
                jsonschema.validate(instance=data, schema=schema)
        except ImportError:
            pass  # jsonschema optional
        except Exception as e:
            errors.append({"code": 2, "message": f"Schema validation failed: {e}"})
    return errors


def validate_outputs(out_dir: str, schema_dir: str = None) -> list:
    """
    Validate output files against schema directory.
    Returns list of error dicts (empty = pass).
    """
    errors = []
    if not schema_dir or not os.path.isdir(schema_dir):
        return errors
    import json, glob
    schema_files = glob.glob(os.path.join(schema_dir, "*.schema.json"))
    for sf in schema_files:
        try:
            import jsonschema
            with open(sf, encoding='utf-8') as f:
                schema = json.load(f)
            # Match output file: schema name -> output JSON
            basename = os.path.basename(sf).replace(".schema.json", "")
            candidate = os.path.join(out_dir, basename + ".json")
            if os.path.isfile(candidate):
                with open(candidate, encoding='utf-8') as f:
                    data = json.load(f)
                jsonschema.validate(instance=data, schema=schema)
        except ImportError:
            pass
        except Exception as e:
            errors.append({"code": 4, "message": f"Output schema '{sf}' validation failed: {e}"})
    return errors

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

# Re-export shared lib modules for convenience
from .lib import validators, template_engine, questa_vcs_support
