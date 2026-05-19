#!/usr/bin/env python3
"""
spec-analyzer — Parse spec YAML into verification plan, interface list,
register map, and test scenarios. Entry point for the IC verification pipeline.

Usage:
    python run.py spec.yml --out output_dir
"""
import sys
import os

# Set up lib/ path for internal dependencies (template_engine, validators)
_this_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_this_dir, "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

# Also add pipeline directory if template_engine/validators import from it
# (some scripts reference pipeline. prefix)
_par_dir = os.path.dirname(os.path.dirname(_this_dir))  # project root
_pipeline_dir = os.path.join(_par_dir, "pipeline")
if os.path.exists(_pipeline_dir) and _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

# Monkey-patch: if any module tries 'import template_engine', redirect to lib
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "template_engine", os.path.join(_lib_dir, "template_engine.py")
)
_spec2 = importlib.util.spec_from_file_location(
    "validators", os.path.join(_lib_dir, "validators.py")
)
_template_engine = importlib.util.module_from_spec(_spec)
_validators = importlib.util.module_from_spec(_spec2)
sys.modules["template_engine"] = _template_engine
sys.modules["validators"] = _validators
_spec.loader.exec_module(_template_engine)
_spec2.loader.exec_module(_validators)

from run_spec_analyzer import main

if __name__ == "__main__":
    sys.exit(main())
