#!/usr/bin/env python3
"""coverage-engine — VCD toggle coverage analysis"""
import sys, argparse, json
from pathlib import Path
from datetime import datetime, timezone

# skill_common provides shared logger, exit codes, result writer, validators
import skill_common
from skill_common import get_logger, ExitCode, write_result, load_config, validate_inputs, validate_outputs

logger = get_logger("coverage-engine")


def parse_args(argv=None):
    """Parse CLI arguments matching skill_spec.json interface.signature"""
    ap = argparse.ArgumentParser(description="VCD toggle coverage analysis")
    ap.add_argument("--spec", type=Path, help="YAML spec for context")
    ap.add_argument("--out", type=Path, default=Path("output/"), help="Output directory")
    ap.add_argument("--log-level", default="info", choices=["debug", "info", "warn", "error"],
                    help="Log level")
    ap.add_argument("--result", type=Path, default=None, help="result.json path override")
        ap.add_argument("--vcd", type=Path, required=True, help="VCD waveform file")
    ap.add_argument("--report", type=Path, default=Path("coverage_report.json"), help="Output report path")
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
        write_result(status="fail", module="coverage-engine", errors=errors,
                     outputs={}, path=str(args.result or "result.json"))
        return ExitCode.INPUT_ERROR
    
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Execute core logic
    try:
                # Import and run engine
        from coverage_engine import CoverageEngine
        engine = CoverageEngine(args.vcd)
        engine.parse()
        report = engine.analyze()
        report_path = out_dir / args.report
        report_path.write_text(json.dumps(report.to_dict(), indent=2))
        report_dict = report.to_dict() if hasattr(report, 'to_dict') else {}
        result = {
            "status": "pass",
            "summary": f"{report.total_signals} signals, {report.toggle_coverage:.1f}% toggle, {report.stuck_signals} stuck",
            "metrics": {
                "total_signals": report.total_signals,
                "toggle_coverage_percent": report.toggle_coverage,
                "stuck_signals": report.stuck_signals,
                "duration_seconds": getattr(report, 'duration', 0),
            },
            "outputs": {
                "coverage_report": str(report_path) if 'report_path' in dir() else "",
                "result_json": str(result_path) if 'result_path' in dir() else "",
            }
        }
    except Exception as e:
        logger.exception("Runtime error")
        write_result(status="error", module="coverage-engine",
                     errors=[{"code": 3, "message": str(e)}],
                     outputs={}, path=str(args.result or out_dir / "result.json"))
        return ExitCode.RUNTIME_ERROR
    
    # 4. Write outputs
    result_path = out_dir / "result.json"
    if args.result:
        result_path = Path(args.result)
    
    write_result(
        status=result.get("status", "pass"),
        module=args.spec.stem if args.spec and args.spec.exists() else "coverage-engine",
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
