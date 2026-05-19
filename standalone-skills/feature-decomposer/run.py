#!/usr/bin/env python3
"""feature-decomposer — Feature decomposition from spec YAML."""
import sys, os, argparse

_d = os.path.dirname(os.path.abspath(__file__))
if _d not in sys.path:
    sys.path.insert(0, _d)

def main():
    """CLI entry point for feature decomposition."""
    parser = argparse.ArgumentParser(
        description="Decompose spec YAML into functional features"
    )
    parser.add_argument("--spec", help="Path to spec YAML file")
    parser.add_argument("--out", default="output", help="Output directory")
    args = parser.parse_args()
    print(f"feature-decomposer: spec={args.spec}, out={args.out}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
