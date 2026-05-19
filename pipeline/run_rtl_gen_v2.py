#!/usr/bin/env python3
"""run_rtl_gen_v2.py — Jinja2 模板驱动的 RTL 生成器 (替代字符串拼接)。

用法:
    python pipeline/run_rtl_gen_v2.py --spec i2c_spec.yml --out output_v2 --v2

与 v1 的区别:
  - 使用 Jinja2 模板 (pipeline/templates/sv/*.j2)
  - 支持 Pydantic Spec 模型输入
  - 新增 --v2 标记显式启用
"""
import os, sys, argparse, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from template_engine import build_spec_data
from fsm_templates import generate_fsm, has_dma_fsm, has_i2c_fsm, has_spi_fsm
from validators import validate_spec_with_pydantic

# Try Pydantic; fall back to dict if not available
try:
    from models.spec import Spec as PydanticSpec
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False


def setup_jinja() -> Environment:
    """初始化 Jinja2 环境。"""
    tpl_dir = str(BASE_DIR / "templates" / "sv")
    return Environment(
        loader=FileSystemLoader(tpl_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )


def generate_regs_v2(env: Environment, data: dict, out_dir: Path) -> str:
    """Generate regs module using Jinja2 template."""
    regs = []
    for r in data.get("registers", []):
        regs.append({
            "n": r["name"],
            "o": r.get("offset", "0x00").replace("0x", ""),
            "rst": r.get("reset", "0").replace("0x", ""),
            "w": all(f.get("access") == "ro" for f in r.get("fields", [])),
        })

    ports = [{"n": "clk", "dir": "input", "w": 1},
             {"n": "rstn", "dir": "input", "w": 1},
             {"n": "psel", "dir": "input", "w": 1},
             {"n": "penable", "dir": "input", "w": 1},
             {"n": "pwrite", "dir": "input", "w": 1},
             {"n": "paddr", "dir": "input", "w": 12},
             {"n": "pwdata", "dir": "input", "w": 32},
             {"n": "prdata", "dir": "output", "w": 32},
             {"n": "pready", "dir": "output", "w": 1}]

    code = env.get_template("regs_module.sv.j2").render(
        module_name=data["module_name"],
        regs=regs,
        ports=ports,
        date=datetime.date.today().isoformat(),
    )

    fpath = out_dir / f"{data['module_name']}_regs.sv"
    fpath.write_text(code, encoding="utf-8")
    return str(fpath)


def generate_top_v2(env: Environment, data: dict, out_dir: Path) -> str:
    """Generate top module using Jinja2 template."""
    fsm_type = data.get("fsm", {}).get("type", "")
    is_dma = has_dma_fsm(data)
    is_i2c = has_i2c_fsm(data)
    is_spi = has_spi_fsm(data)

    # Build port list from spec interfaces
    ports = [{"n": "clk", "dir": "input", "w": 1},
             {"n": "rstn", "dir": "input", "w": 1}]
    for iface in data.get("interfaces", []):
        for sig in iface.get("signals", []):
            ports.append({
                "n": sig["name"],
                "dir": sig.get("direction", "input"),
                "w": sig.get("width", 1),
            })

    fsm_label = f"YES ({fsm_type})" if (is_dma or is_i2c or is_spi) else "NO"

    code = env.get_template("top_module.sv.j2").render(
        mn=data["module_name"],
        ports=ports,
        fsm={"label": fsm_label},
    )

    fpath = out_dir / f"{data['module_name']}.sv"
    fpath.write_text(code, encoding="utf-8")
    return str(fpath)


def main():
    ap = argparse.ArgumentParser(description="RTL Generator v2 (Jinja2)")
    ap.add_argument("--spec", default="")
    ap.add_argument("--out", default=str(BASE_DIR.parent / "output_v2"))
    ap.add_argument("--v2", action="store_true",
                    help="启用 Jinja2 模板生成 (否则使用旧版字符串拼接)")
    ap.add_argument("--validate", action="store_true", help="运行验证")
    args = ap.parse_args()

    if not args.v2:
        # 回退到旧版生成器
        from run_rtl_gen import main as legacy_main
        sys.argv = [sys.argv[0], "--spec", args.spec, "--out", args.out]
        return legacy_main()

    if not HAS_JINJA:
        print("[FAIL] Jinja2 未安装: pip install jinja2")
        return 1

    # 加载 spec
    spec_path = args.spec or str(BASE_DIR.parent / "i2c_spec.yml")
    if not os.path.exists(spec_path):
        print(f"[X] Spec not found: {spec_path}")
        return 1

    data = build_spec_data(spec_path)
    module = data["module_name"]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 可选 Pydantic 验证
    if HAS_PYDANTIC and args.validate:
        try:
            spec = PydanticSpec.from_yaml(spec_path)
            print(f"  [PD] Pydantic validated: {spec.module_name}")
        except Exception as e:
            print(f"  [PD] Validation error: {e}")
            return 1

    env = setup_jinja()

    print(f"{'='*60}")
    print(f"  RTL-GEN v2 — {module.upper()}")
    print(f"  Template: Jinja2 ({'/'.join(env.loader.searchpath)})")
    print(f"  FSM: {'YES (' + data.get('fsm',{}).get('type','') + ')' if has_dma_fsm(data) or has_i2c_fsm(data) or has_spi_fsm(data) else 'NO'}")
    print(f"{'='*60}")

    # 生成寄存器模块
    regs_file = generate_regs_v2(env, data, out_dir)
    print(f"  [OK] Regs: {os.path.basename(regs_file)}")

    # 生成顶层模块
    top_file = generate_top_v2(env, data, out_dir)
    print(f"  [OK] Top:  {os.path.basename(top_file)}")

    # FSM 生成（委托给 fsm_templates）
    is_spi = has_spi_fsm(data)
    if is_spi:
        # SPI FSM 使用独立模板
        from shutil import copy2
        fsm_src = BASE_DIR / "templates" / "spi_slave_fsm.sv"
        if fsm_src.exists():
            fsm_dst = out_dir / f"{module}_spi_slave_fsm.sv"
            copy2(fsm_src, fsm_dst)
            print(f"  [OK] FSM:  {fsm_dst.name}")
    elif has_dma_fsm(data) or has_i2c_fsm(data):
        fsm_files = generate_fsm(data)
        for fname, fcode in fsm_files.items():
            (out_dir / fname).write_text(fcode, encoding="utf-8")
            print(f"  [OK] FSM:  {fname}")

    # Pydantic 验证
    if args.validate and HAS_PYDANTIC:
        try:
            spec = PydanticSpec.from_yaml(spec_path)
            print(f"  [PD] Pydantic: {spec.module_name}, {len(spec.registers)} regs")
            for reg in spec.registers:
                if int(reg.offset, 16) > 0xFFF:
                    print(f"  [PD WARN] {reg.name}: offset {reg.offset} exceeds APB space")
        except Exception as e:
            print(f"  [PD] Error: {e}")

    print(f"{'='*60}")
    print(f"  RTL-GEN v2 COMPLETE ({module})")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
