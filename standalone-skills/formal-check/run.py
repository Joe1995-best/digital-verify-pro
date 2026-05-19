#!/usr/bin/env python3
"""
formal-check — Formal property verification engine.

Usage:
    python run.py --spec <spec.yml> [--out output_dir] [--no-run]
"""
import sys
import os

_this_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_this_dir, "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

# Monkey-patch internal dependencies
import importlib.util

def _monkey_patch(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)

for fname in ["template_engine.py", "validators.py", "formal_check_gen.py"]:
    fpath = os.path.join(_lib_dir, fname)
    if os.path.exists(fpath):
        _monkey_patch(fname.replace(".py", ""), fpath)

from run_formal import main

if __name__ == "__main__":
    sys.exit(main())
