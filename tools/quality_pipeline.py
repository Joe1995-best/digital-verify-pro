#!/usr/bin/env python3
"""
quality_pipeline.py -- digital-verify-pro 单 Skill 质量评估工具

对标 IC Agent Hub 的 5 步管线，对任一 Agent Skill 进行 5 维度自动化评分。
产出 JSON + Markdown 质量报告。

Usage:
    python tools/quality_pipeline.py pipeline/agent_skills/spec-analyzer/
    python tools/quality_pipeline.py engines/coverage_engine.py --output report.json
"""

import argparse
import ast
import json
import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Windows GBK 兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'gb18030'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---- 配置 ----

REQUIRED_SKILLMD_FIELDS = ["name", "description"]
WIDTHS = {"Q1": 25, "Q2": 20, "Q3": 20, "Q4": 20, "Q5": 15}

# 危险 API 模式 (compile() 单独处理 — Python 中大量合法用途)
HIGH_RISK_PATTERNS = [
    (r"\beval\s*\(", "eval() 调用", -3),
    (r"\bexec\s*\(", "exec() 调用", -3),
    (r"\bos\.system\s*\(", "os.system() 调用", -2),
    (r"\bsubprocess\.Popen\b", "subprocess.Popen", -1),
    (r"\bsubprocess\.call\b", "subprocess.call", -1),
    (r"\bsubprocess\.run\b.*shell=True", "shell=True 风险", -1),
    (r"\b__import__\s*\(", "__import__()", -2),
    (r"\bopen\s*\(.*[\"\'][^\"\']*\.\.\.[\"\']", "疑似路径遍历", -1),
]

COMPILE_PATTERN = re.compile(r"\bcompile\s*\(")

LICENSE_PATTERNS = [
    r"SPDX-License-Identifier:", r"Apache License", r"MIT License",
    r"BSD", r"Copyright", r"Licensed under",
]


# ---- 路径解析 ----

def resolve_skill(path: str) -> Tuple[Path, Optional[Path]]:
    """返回 (skill_dir, primary_py_file) 接受: SKILL.md / .py / 目录"""
    p = Path(path)
    if p.is_file():
        if p.name == "SKILL.md":
            return p.parent, None
        if p.suffix == ".py":
            return p.parent, p
        return p.parent, None
    return p, None


def parse_skilmd(skill_dir: Path) -> Tuple[Optional[Dict], Optional[str]]:
    """解析 SKILL.md frontmatter"""
    skilmd_path = skill_dir / "SKILL.md"
    if not skilmd_path.exists():
        for f in skill_dir.glob("**/SKILL.md"):
            skilmd_path = f
            break
        else:
            return None, None

    text = skilmd_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None, text
    fmap = {}
    for line in m.group(1).strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fmap[k.strip()] = v.strip().strip("'\"")
    return fmap, text


def collect_py_files(skill_dir: Path, primary_py: Optional[Path] = None) -> List[Path]:
    """收集 .py 文件"""
    if primary_py:
        return [primary_py] if primary_py.exists() else []
    out = [f for f in skill_dir.glob("*.py") if "__pycache__" not in str(f)]
    out += [f for f in skill_dir.rglob("*.py") if "__pycache__" not in str(f)]
    return out


def find_run_script(skill_dir: Path) -> Optional[Path]:
    """匹配 pipeline/run_<skill>.py — 从 skill 目录往项目根找"""
    for parent in skill_dir.parents:
        if (parent / "pro_verify.py").exists():
            pipeline_dir = parent / "pipeline"
            if pipeline_dir.exists():
                candidates = list(pipeline_dir.glob("run_*.py"))
                name = skill_dir.name.replace("-", "_")
                for c in candidates:
                    if name in c.stem.replace("run_", ""):
                        return c
            break
    return None


# ---- Q1 功能完备性 ----

def _pencent(v: float, m: float) -> str:
    return f"{v/m:.0%}" if m > 0 else "-"


def check_functional(skill_dir: Path, fm: Optional[Dict], text: Optional[str],
                     primary_py: Optional[Path] = None) -> dict:
    """Q1: 功能完备性"""
    score, mx = 0.0, 25.0
    det = {}

    # 1.1 Inputs/Outputs 声明
    io = 0
    if text:
        has_in = "## Inputs" in text
        has_out = "## Outputs" in text
        if has_in and has_out:
            io = 3
        elif has_in or has_out:
            io = 1
    det["1.1_io_declared"] = {"s": io, "m": 3, "d": "Input+Output 齐全" if io == 3 else ("部分" if io else "无")}
    score += io

    # 1.2 输出文件存在性
    if text and "## Outputs" in text:
        sec = text.split("## Outputs")[1]
        if "\n## " in sec:
            sec = sec.split("\n## ")[0]
        files = re.findall(r"\| `([^`]+)`", sec)
        # 过滤运行时产出（通常是报告/json），只检查源代码文件
        runtime_exts = (".json", ".md", ".html", ".log", ".vcd", ".txt", ".csv", ".xml")
        check_files = [f for f in files if not any(f.endswith(e) for e in runtime_exts)]
        if check_files:
            exist = sum(1 for f in check_files if (skill_dir / f).exists() or any(skill_dir.rglob(f)))
            fs = min(exist / max(len(check_files), 1) * 3, 3)
            det["1.2_outputs_exist"] = {"s": round(fs, 1), "m": 3, "d": f"{exist}/{len(check_files)} 存在"}
            score += fs
        else:
            # 全是运行时产出，给个基础分
            det["1.2_outputs_exist"] = {"s": 2, "m": 3, "d": "产出为运行时文件(报告/JSON)"}
            score += 2
    else:
        det["1.2_outputs_exist"] = {"s": 0, "m": 3, "d": "无 Outputs 章节"}

    # 1.3 Capabilities
    if text and "## Capabilities" in text:
        sec = text.split("## Capabilities")[1]
        # 用 \n## （换行+双#+空格）分割，避免 ### 三级标题误匹配
        if "\n## " in sec:
            sec = sec.split("\n## ")[0]
        n = len(re.findall(r"###?\s*\d*\.?\s*\w", sec))
        cs = min(n * 1.5, 5)
        det["1.3_capabilities"] = {"s": round(cs, 1), "m": 5, "d": f"{n} 个能力点"}
        score += cs
    else:
        det["1.3_capabilities"] = {"s": 0, "m": 5, "d": "无 Capabilities"}

    # 1.4 Run 脚本存在 — 检查 run.py 或 pipeline 匹配
    run_py = skill_dir / "run.py"
    rs = run_py if run_py.exists() else find_run_script(skill_dir)
    rv = 4 if rs else 0
    det["1.4_run_script"] = {"s": rv, "m": 4, "d": rs.name if rs else "未匹配"}
    score += rv

    # 1.5 Effort
    if text and "## Effort" in text:
        score += 3
        det["1.5_effort"] = {"s": 3, "m": 3, "d": "支持 Effort"}
    else:
        det["1.5_effort"] = {"s": 0, "m": 3, "d": "无 Effort"}

    # 1.6 上下游
    has_chain = text and ("## Dependencies" in text or "## Upstream" in text or "## Downstream" in text)
    if has_chain:
        cv = 3
    elif fm and "pipeline" in str(fm.get("description", "")).lower():
        cv = 2
    else:
        cv = 0
    det["1.6_pipeline_aware"] = {"s": cv, "m": 3, "d": "有" if cv > 0 else "无"}
    score += cv

    # 1.7 测试
    tc = sum(1 for _ in skill_dir.rglob("test_*.py"))
    tc += sum(1 for _ in skill_dir.rglob("*test*.sv"))
    for td in skill_dir.glob("tests"):
        tc += len(list(td.rglob("*.py"))) + len(list(td.rglob("*.sv")))
    ts = min(tc, 4)
    det["1.7_tests"] = {"s": ts, "m": 4, "d": f"{tc} 个测试"}
    score += ts

    return {"score": round(score, 1), "max": mx, "details": det}


# ---- Q2 代码/文档 ----

def check_code_quality(skill_dir: Path, fm: Optional[Dict], text: Optional[str],
                       primary_py: Optional[Path] = None) -> dict:
    """Q2: 代码/文档"""
    score, mx = 0.0, 20.0
    det = {}
    pys = collect_py_files(skill_dir, primary_py)

    # 2.1 SKILL.md 字段
    if fm:
        missing = [f for f in REQUIRED_SKILLMD_FIELDS if f not in fm]
        det["2.1_skilmd_fields"] = {"s": 4 if not missing else 1, "m": 4, "d": f"ok ({len(fm)} fields)" if not missing else f"缺 {missing}"}
        score += 4 if not missing else 1
    else:
        det["2.1_skilmd_fields"] = {"s": 0, "m": 4, "d": "无 SKILL.md"}

    # 2.2 注释率
    tl = cl = 0
    for pf in pys:
        try:
            for line in pf.read_text(encoding="utf-8").split("\n"):
                tl += 1
                s = line.strip()
                if s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
                    cl += 1
        except Exception:
            pass
    if tl > 0:
        cr = cl / tl
        cs = 4 if cr >= 0.20 else 2 if cr >= 0.10 else 1 if cr >= 0.05 else 0
        det["2.2_comment_ratio"] = {"s": cs, "m": 4, "d": f"注释率 {cr:.0%} ({cl}/{tl})"}
        score += cs
    else:
        det["2.2_comment_ratio"] = {"s": 0, "m": 4, "d": "无 .py 文件"}

    # 2.3 Docstring
    df = tf = 0
    for pf in pys:
        try:
            tree = ast.parse(pf.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    tf += 1
                    if ast.get_docstring(node):
                        df += 1
        except SyntaxError:
            pass
    if tf > 0:
        dr = df / tf
        ds = 3 if dr >= 0.7 else 2 if dr >= 0.4 else 1 if dr >= 0.1 else 0
        det["2.3_docstring"] = {"s": ds, "m": 3, "d": f"docstring {df}/{tf} ({dr:.0%})"}
        score += ds
    else:
        det["2.3_docstring"] = {"s": 0, "m": 3, "d": "无函数/类"}

    # 2.4 CLI
    has_ap = any("argparse" in pf.read_text(encoding="utf-8", errors="ignore") for pf in pys)
    if has_ap:
        score += 3
        det["2.4_cli"] = {"s": 3, "m": 3, "d": "argparse"}
    else:
        det["2.4_cli"] = {"s": 0, "m": 3, "d": "非 CLI skill"}

    # 2.5 代码风格
    sty = 0
    for pf in pys:
        try:
            tree = ast.parse(pf.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    if not re.match(r"^[a-z_][a-z0-9_]*$", node.name):
                        sty += 1
                if isinstance(node, ast.ClassDef):
                    if not re.match(r"^[A-Z]", node.name):
                        sty += 1
        except SyntaxError:
            pass
    ss = max(3 - sty * 0.5, 0)
    det["2.5_style"] = {"s": round(ss, 1), "m": 3, "d": f"{sty} 处命名问题" if sty else "良好"}
    score += ss

    # 2.6 版本/Changelog
    has_ver = fm and "version" in fm
    has_ch = any((skill_dir / f).exists() for f in ["CHANGELOG.md", "CHANGES.md", "HISTORY.md"])
    vs = (1 if has_ver else 0) + (2 if has_ch else 0)
    det["2.6_versioning"] = {"s": vs, "m": 3, "d": f"ver={'有' if has_ver else '无'}, changelog={'有' if has_ch else '无'}"}
    score += vs

    return {"score": round(score, 1), "max": mx, "details": det}


# ---- Q3 安全与合规 ----

def check_security(skill_dir: Path, fm: Optional[Dict],
                   primary_py: Optional[Path] = None) -> dict:
    """Q3: 安全与合规"""
    score, mx = 0.0, 20.0
    det = []
    pys = collect_py_files(skill_dir, primary_py)
    all_code = "".join(pf.read_text(encoding="utf-8", errors="ignore") for pf in pys)

    # 3.1 高危代码
    deduction = 0
    for pat, desc, pen in HIGH_RISK_PATTERNS:
        n = len(re.findall(pat, all_code))
        if n:
            deduction += pen * n
            det.append(f"{desc} {n}处 (扣{pen*n}分)")

    comp_n = len(COMPILE_PATTERN.findall(all_code))
    # compile() 不扣分 — Python 中合法用途广泛（VCD 编译、DSL 等）
    # 只标记数量

    hs = max(5 + deduction, 0)
    score += hs
    detail = f"{len(det)} 项风险" if det else "无高危"
    if comp_n:
        detail += f" | compile(): {comp_n}处(已标记-非高危)"
    hs_name = "3.1_high_risk"

    # 3.2 依赖声明+一致性
    req = skill_dir / "requirements.txt"
    if not req.exists():
        req = skill_dir.parent / "requirements.txt"
    has_req = req.exists()
    declared = set()
    if has_req:
        for line in req.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                pkg = re.split(r"[=<>~!]", line)[0].strip().lower()
                if pkg:
                    declared.add(pkg)

    # 收集本地 .py 文件名（含 lib/ 子目录），它们不是第三方依赖
    local_modules = set()
    for f in collect_py_files(skill_dir, primary_py):
        stem = f.stem.lower()
        local_modules.add(stem)
    for f in (skill_dir / "lib").rglob("*.py") if (skill_dir / "lib").exists() else []:
        stem = f.stem.lower()
        local_modules.add(stem)

    # 额外过滤：常见的项目内部路径前缀
    internal_prefixes = {"engines", "pipeline"}

    actual = set()
    for imp in re.findall(r"^(?:from|import)\s+(\S+)", all_code, re.MULTILINE):
        base = imp.split(".")[0].split()[0].strip(",").lower()
        if base in local_modules or base in internal_prefixes:
            continue  # 本地文件/内部路径，不是第三方依赖
        if base not in sys.stdlib_module_names and base not in ("__future__", "__init__"):
            actual.add(base)
    # 映射 pyyaml → yaml 等 pip 包名 ≠ import 名的情况
    pkg_import_aliases = {"pyyaml": "yaml"}
    standardized = set()
    for p in declared:
        aliased = pkg_import_aliases.get(p, p)
        standardized.add(aliased)
    declared = standardized

    actual -= {"os", "sys", "re", "json", "math", "time", "datetime", "pathlib",
               "argparse", "subprocess", "ast", "copy", "collections", "typing",
               "functools", "itertools", "io", "textwrap", "tempfile", "shutil",
               "logging", "hashlib", "uuid", "enum", "abc", "inspect", "struct",
               "dataclasses", "random", "pickle", "socket", "ssl",
               "configparser", "csv", "glob", "pprint", "traceback",
               "base64", "html", "xml"}

    if has_req:
        frag = 2
        undeclared = actual - declared
        if len(undeclared) == 0:
            cons = 4
        elif len(undeclared) <= max(len(actual) * 0.3, 2):
            cons = 2
        else:
            cons = 0
        dep_detail = f"requirements.txt ({len(declared)} 声明), "
        dep_detail += f"{len(undeclared)} 未声明" if undeclared else "一致"
    elif actual:
        frag = 0
        cons = 0
        dep_detail = f"无 requirements.txt, {len(actual)} 个未声明依赖: {', '.join(sorted(actual)[:5])}"
    else:
        frag = 2
        cons = 2
        dep_detail = "纯标准库, 无需声明"

    score += frag + cons
    det.append(f"依赖: {dep_detail}")

    # 3.4 文件安全（License 检查已移除）
    writes = re.findall(r'open\([^)]*["\']([^"\']+)["\']', all_code)
    dang = [w for w in writes if ".." in w or w.startswith("/") or w.startswith("~")]
    hard = re.findall(r'["\'](C:[/\\][^"\']+)["\']', all_code)
    fp = len(dang) + len(hard) * 0.5
    fs = max(4 - fp, 0)
    det.append(f"文件安全: {len(dang)} 危险写入, {len(hard)} 硬编码路径 => {fs}/4")
    score += fs

    sec_details = {
        hs_name: {"s": round(hs, 1), "m": 6, "d": detail},
        "3.2_dependencies": {"s": round(frag + cons, 1), "m": 9, "d": dep_detail},
        "3.4_file_safety": {"s": round(fs, 1), "m": 5, "d": f"{len(dang)} 危险, {len(hard)} 硬编码"},
    }

    return {"score": round(score, 1), "max": mx, "details": sec_details, "issues": det}


# ---- Q4 运行可靠性 ----

def check_reliability(skill_dir: Path, fm: Optional[Dict],
                      primary_py: Optional[Path] = None) -> dict:
    """Q4: 运行可靠性"""
    score, mx = 0.0, 20.0
    det = {}
    pys = collect_py_files(skill_dir, primary_py)
    all_code = "".join(pf.read_text(encoding="utf-8", errors="ignore") for pf in pys)

    # 4.1 错误处理
    tr = all_code.count("try:")
    ex = all_code.count("except")
    has_specific = bool(re.findall(r"except\s+\w+", all_code))
    has_bare = bool(re.findall(r"except\s*:", all_code))
    es = 0
    if tr > 0:
        es += 2
    if has_specific:
        es += 2
    if not has_bare or tr == 0:
        es += 1
    det["4.1_error_handling"] = {"s": es, "m": 5, "d": f"try={tr} except={ex} bare={has_bare}"}
    score += es

    # 4.2 日志
    lg = "logging." in all_code or "print(" in all_code
    em = "raise " in all_code or "assert " in all_code or "error" in all_code.lower()
    vb = "-v" in all_code or "--verbose" in all_code
    ds = sum([1.5 if lg else 0, 1.5 if em else 0, 1 if vb else 0])
    det["4.2_diagnostics"] = {"s": round(ds, 1), "m": 4, "d": f"log={lg} err={em} verbose={vb}"}
    score += ds

    # 4.3 输入校验
    has_val = any(p in all_code for p in [r"if\s+not\s+\w+", r"if\s+\w+\s+is\s+None",
                  r"if\s+len\(", r"if\s+isinstance", r"validate",
                  r"ValueError", r"TypeError", r"raise\s+.*Error"])
    vs = 3 if has_val else 0
    det["4.3_input_validation"] = {"s": vs, "m": 3, "d": "有" if has_val else "无"}
    score += vs

    # 4.4 清理
    has_cl = any(p in all_code for p in [r"finally:", r"with\s+open", r"tempfile",
                 r"shutil\.rmtree", r"os\.remove", r"\.close\(", r"__exit__"])
    cls = 3 if has_cl else 0
    det["4.4_cleanup"] = {"s": cls, "m": 3, "d": "有" if has_cl else "无"}
    score += cls

    # 4.5 超时
    ht = "timeout" in all_code.lower() or "timeout=" in all_code
    he = "sys.exit" in all_code or "exit(" in all_code
    ts = (2 if ht else 0) + (1 if he else 0)
    det["4.5_timeout"] = {"s": ts, "m": 3, "d": f"timeout={ht} exit_clean={he}"}
    score += ts

    # 4.6 Run test
    rs = find_run_script(skill_dir)
    bonus = 0
    if rs and rs.exists():
        try:
            r = subprocess.run([sys.executable, str(rs), "--help"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                bonus = 2
        except Exception:
            pass
    det["4.6_runnable"] = {"s": bonus, "m": 2, "d": "通过" if bonus else "跳过"}
    score += bonus

    return {"score": round(score, 1), "max": mx, "details": det}


# ---- Q5 兼容性 ----

def check_compatibility(skill_dir: Path, fm: Optional[Dict],
                        primary_py: Optional[Path] = None) -> dict:
    """Q5: 兼容性"""
    score, mx = 0.0, 15.0
    det = {}
    pys = collect_py_files(skill_dir, primary_py)
    all_code = "".join(pf.read_text(encoding="utf-8", errors="ignore") for pf in pys)

    # 5.1 Python 版本
    has_pyver = any((skill_dir / f).exists() for f in [".python-version", ".python_version"])
    has_req = "python_requires" in all_code
    ps = (2 if has_pyver else 0) + (1 if has_req else 0)
    det["5.1_python_version"] = {"s": ps, "m": 3, "d": f"vers={has_pyver} req={has_req}"}
    score += ps

    # 5.2 输出格式
    fmt = set()
    for ext in [".yml", ".yaml", ".json", ".md", ".sv", ".v", ".vhd", ".py", ".tcl"]:
        for f in skill_dir.rglob(f"*{ext}"):
            if "__pycache__" not in str(f):
                fmt.add(ext)
    fms = min(len(fmt) * 0.8, 3)
    if any(e in fmt for e in [".yml", ".json", ".md", ".sv"]):
        fms += 1
    det["5.2_output_formats"] = {"s": round(fms, 1), "m": 4, "d": f"{', '.join(sorted(fmt)) if fmt else '无'}"}
    score += fms

    # 5.3 跨平台
    hp = "Path(" in all_code or "pathlib" in all_code
    oj = "os.path.join" in all_code
    posix_hard = bool(re.findall(r'["\']/(?:tmp|usr|home|dev|proc|etc)/', all_code))
    plat = 3 if hp else 2 if oj else 1
    if posix_hard:
        plat = max(plat - 1, 0)
    det["5.3_cross_platform"] = {"s": plat, "m": 3, "d": f"pathlib={hp} os.join={oj} posix-hard={posix_hard}"}
    score += plat

    # 5.4 EDA 工具
    tools = [t for t in ["iverilog", "vcs", "questa", "xcelium", "verilator", "sby", "yosys",
                         "synopsys", "cadence", "mentor"] if t in all_code.lower()]
    eda = min(len(set(tools)) * 0.5, 3)
    det["5.4_eda_compat"] = {"s": round(eda, 1), "m": 3, "d": f"{', '.join(tools) if tools else '无'}"}
    score += eda

    # 5.5 Shebang
    she = any(
        pf.read_text(encoding="utf-8", errors="ignore").startswith("#!/")
        for pf in pys
    )
    det["5.5_entrypoint"] = {"s": 2 if she else 0, "m": 2, "d": "有" if she else "无"}
    score += 2 if she else 0

    return {"score": round(score, 1), "max": mx, "details": det}


# ---- 报告生成 ----

def get_grade(ts: float) -> Tuple[str, str]:
    if ts >= 90:
        return "A+", "[Certified]"
    if ts >= 75:
        return "A", "[Approved]"
    if ts >= 60:
        return "B", "[Beta]"
    if ts >= 40:
        return "C", "[In Development]"
    return "D", "[Unstable]"


def gen_report(path: str, q1: dict, q2: dict, q3: dict, q4: dict, q5: dict,
               fm: Optional[Dict], issues: list) -> dict:
    dims = {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4, "Q5": q5}
    ts = sum(d["score"] for d in dims.values())
    tmax = sum(d["max"] for d in dims.values())
    g, lbl = get_grade(ts)
    recs = []
    for qk, dim in dims.items():
        for ck, cv in dim.get("details", {}).items():
            cm = cv.get("m", 1)
            cs = cv.get("s", 0)
            if cm > 0 and cs / cm < 0.5:
                recs.append(f"[{qk}] {cv.get('d', ck)} ({cs}/{cm})")
    return {
        "skill": {
            "name": fm.get("name", Path(path).name) if fm else Path(path).name,
            "path": str(path),
        },
        "version": fm.get("version", "unknown") if fm else "unknown",
        "score": {
            "total": round(ts, 1), "max": tmax,
            "functional": q1["score"], "code_docs": q2["score"],
            "security": q3["score"], "reliability": q4["score"],
            "compatibility": q5["score"],
        },
        "grade": g, "label": lbl,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dimensions": dims,
        "recommendations": recs,
        "issues": issues,
    }


def render_md(r: dict) -> str:
    s = r["score"]
    dims = r["dimensions"]
    names = {"Q1": "功能完备性", "Q2": "代码/文档", "Q3": "安全与合规",
             "Q4": "运行可靠性", "Q5": "兼容性"}
    lines = [
        f"## {r['skill']['name']} -- Quality Report",
        "",
        "| 维度 | 得分 | 占比 |",
        "|------|:----:|:----:|",
        f"| **Q1 功能完备性** | {s['functional']}/{dims['Q1']['max']} | {s['functional']/dims['Q1']['max']:.0%} |",
        f"| **Q2 代码/文档** | {s['code_docs']}/{dims['Q2']['max']} | {s['code_docs']/dims['Q2']['max']:.0%} |",
        f"| **Q3 安全与合规** | {s['security']}/{dims['Q3']['max']} | {s['security']/dims['Q3']['max']:.0%} |",
        f"| **Q4 运行可靠性** | {s['reliability']}/{dims['Q4']['max']} | {s['reliability']/dims['Q4']['max']:.0%} |",
        f"| **Q5 兼容性** | {s['compatibility']}/{dims['Q5']['max']} | {s['compatibility']/dims['Q5']['max']:.0%} |",
        f"| **总分** | **{s['total']}/{s['max']}** | **{r['label']}** |",
        "",
        f"版本: {r.get('version', 'unknown')}  检查时间: {r['checked_at']}",
        "",
    ]
    for qk in ["Q1","Q2","Q3","Q4","Q5"]:
        dim = dims[qk]
        lines.append(f"### {qk}: {names[qk]} ({dim['score']}/{dim['max']})")
        lines.append("")
        for ck, cv in dim.get("details", {}).items():
            bar = "++" if cv["s"]/cv["m"] >= 0.7 else "+-" if cv["s"]/cv["m"] >= 0.4 else "--"
            lines.append(f"- [{bar}] {cv.get('d', ck)} ({cv['s']}/{cv['m']})")
        lines.append("")
    if r.get("recommendations"):
        lines.append("### 改进建议")
        lines.append("")
        for i, rec in enumerate(r["recommendations"], 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
    if r.get("issues"):
        lines.append("### 安全/依赖问题")
        lines.append("")
        for iss in r["issues"]:
            lines.append(f"- {iss}")
        lines.append("")
    return "\n".join(lines)


# ---- CLI ----

def _p(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "ignore").decode("ascii"))


def main():
    ap = argparse.ArgumentParser(
        description="digital-verify-pro Skill 质量评估工具",
        epilog="""示例:
  python tools/quality_pipeline.py pipeline/agent_skills/spec-analyzer/
  python tools/quality_pipeline.py engines/coverage_engine.py -o report.json""")
    ap.add_argument("skill", help="Skill 路径（目录/SKILL.md/.py）")
    ap.add_argument("--output", "-o", help="JSON 输出路径")
    ap.add_argument("--markdown", "-m", action="store_true", help="同时输出 Markdown")
    ap.add_argument("--open", action="store_true", help="输出后打开 Markdown")
    args = ap.parse_args()

    skill_dir, primary_py = resolve_skill(args.skill)
    if not skill_dir.exists():
        _p(f"[ERR] 路径不存在: {skill_dir}")
        return 1
    _p(f"[检查] {skill_dir}" + (f" (文件: {primary_py.name})" if primary_py else ""))

    fm, text = parse_skilmd(skill_dir)
    if fm:
        _p(f"[SKILL.md] {fm.get('name','?')} v{fm.get('version','?')}")
    else:
        _p("[WARN] 无 SKILL.md")

    q1 = check_functional(skill_dir, fm, text, primary_py)
    q2 = check_code_quality(skill_dir, fm, text, primary_py)
    q3 = check_security(skill_dir, fm, primary_py)
    q4 = check_reliability(skill_dir, fm, primary_py)
    q5 = check_compatibility(skill_dir, fm, primary_py)
    issues = q3.get("issues", [])

    report = gen_report(args.skill, q1, q2, q3, q4, q5, fm, issues)
    s = report["score"]

    # 输出 JSON
    out_path = None
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = skill_dir / "quality_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _p(f"[JSON] {out_path.resolve()}")

    if args.markdown:
        md_path = out_path.with_suffix(".md") if str(out_path).endswith(".json") else skill_dir / "quality_report.md"
        md_path.write_text(render_md(report), encoding="utf-8")
        _p(f"[MD]   {md_path.resolve()}")
        if args.open and os.name == "nt":
            os.system(f'start "" "{md_path}"')

    # 终端摘要
    _p("")
    _p("=" * 46)
    _p(f"  {report['skill']['name']:30s}")
    _p(f"  Q1 功能完备性  {s['functional']:>5}/{q1['max']:<3}  {s['functional']/q1['max']:>7.0%}")
    _p(f"  Q2 代码/文档   {s['code_docs']:>5}/{q2['max']:<3}  {s['code_docs']/q2['max']:>7.0%}")
    _p(f"  Q3 安全与合规  {s['security']:>5}/{q3['max']:<3}  {s['security']/q3['max']:>7.0%}")
    _p(f"  Q4 运行可靠性  {s['reliability']:>5}/{q4['max']:<3}  {s['reliability']/q4['max']:>7.0%}")
    _p(f"  Q5 兼容性      {s['compatibility']:>5}/{q5['max']:<3}  {s['compatibility']/q5['max']:>7.0%}")
    _p(f"  总分: {s['total']:>5}/{s['max']:<3}  {report['label']}")
    _p("=" * 46)

    if report.get("recommendations"):
        _p("")
        _p("[改进建议]:")
        for i, rec in enumerate(report["recommendations"], 1):
            _p(f"  {i}. {rec}")
    if report.get("issues"):
        _p("")
        _p("[安全/依赖问题]:")
        for iss in report["issues"]:
            _p(f"  * {iss}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
