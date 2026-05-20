#!/usr/bin/env python3
"""doc-gen — Generate verification close documentation"""
import sys, argparse, json
from pathlib import Path
from datetime import datetime, timezone

# skill_common provides shared logger, exit codes, result writer, validators
import skill_common
from skill_common import get_logger, ExitCode, write_result, load_config, validate_inputs, validate_outputs

logger = get_logger("doc-gen")


def parse_args(argv=None):
    """Parse CLI arguments matching skill_spec.json interface.signature"""
    ap = argparse.ArgumentParser(description="Generate verification close documentation")
    ap.add_argument("--spec", type=Path, help="YAML spec for context")
    ap.add_argument("--out", type=Path, default=Path("output/"), help="Output directory")
    ap.add_argument("--log-level", default="info", choices=["debug", "info", "warn", "error"],
                    help="Log level")
    ap.add_argument("--result", type=Path, default=None, help="result.json path override")
    
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logger.setLevel(args.log_level.upper())
    
    # 1. Load config
    config = load_config("config.yaml")
    
    # 2. Input validation
    errors = validate_inputs(args, required_args=[], schema_path=str(Path(__file__).parent / "schemas" / "input.schema.json"))
    if errors:
        for err in errors:
            logger.error(err["message"])
        write_result(status="fail", module="doc-gen", errors=errors,
                     outputs={}, path=str(args.result or "result.json"))
        return ExitCode.INPUT_ERROR
    
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Execute core logic
    try:
                from run_doc_gen import main as doc_main
        doc_main()
        result = {"status": "pass", "summary": ""Documentation generated""}
    except Exception as e:
        logger.exception("Runtime error")
        write_result(status="error", module="doc-gen",
                     errors=[{"code": 3, "message": str(e)}],
                     outputs={}, path=str(args.result or out_dir / "result.json"))
        return ExitCode.RUNTIME_ERROR
    
    # 4. Write outputs
    result_path = out_dir / "result.json"
    if args.result:
        result_path = Path(args.result)
    
    write_result(
        status=result.get("status", "pass"),
        module=args.spec.stem if args.spec and args.spec.exists() else "doc-gen",
        summary=result.get("summary", ""),
        metrics=result.get("metrics", {}),
        outputs=result.get("outputs", {}),
        errors=result.get("errors", []),
        warnings=result.get("warnings", []),
        path=str(result_path)
    )
    
    # 5. Output schema validation
    out_errors = validate_outputs(str(out_dir), schema_dir=str(Path(__file__).parent / "schemas"))
    for err in out_errors:
        logger.warning(err["message"])
    
    logger.info(result.get("summary", "Done"))
    return ExitCode.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
