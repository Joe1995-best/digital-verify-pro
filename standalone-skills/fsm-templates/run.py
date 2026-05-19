#!/usr/bin/env python3
"""fsm-templates — FSM controller RTL generator from spec YAML."""
import sys, os, argparse

_d = os.path.dirname(os.path.abspath(__file__))
if _d not in sys.path:
    sys.path.insert(0, _d)

def main():
    """CLI entry point for FSM template generation."""
    parser = argparse.ArgumentParser(
        description="Generate synthesizable FSM RTL from spec YAML"
    )
    parser.add_argument("--spec", help="Path to spec YAML file")
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--type", default="dma",
                      choices=["dma", "simple"],
                      help="FSM template type")
    args = parser.parse_args()
    # FSM template generation logic
    print(f"fsm-templates: type={args.type}, spec={args.spec}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
