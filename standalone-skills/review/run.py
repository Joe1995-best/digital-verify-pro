#!/usr/bin/env python3
"""review -- Cross-Model Code Review Engine with coverage-aware RTL checks."""
import sys, os, re, json, argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_REVIEWERS = ["style-check", "uvm-best-practices", "protocol-audit"]
REVIEW_EXTS = {".sv", ".v", ".vhd", ".vhdl", ".py", ".tcl", ".sby"}
UVM_KEYWORDS = {"uvm_component", "uvm_driver", "uvm_monitor", "uvm_agent",
                "uvm_env", "uvm_test", "uvm_sequence", "uvm_sequencer",
                "uvm_scoreboard", "uvm_subscriber", "uvm_config_db"}

class CodeScanner:
    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.files: List[Path] = []
        self.findings: Dict[str, List[Dict]] = {}
        self.summary: Dict = {"total_files": 0, "total_lines": 0, "issues_found": 0,
                              "critical": 0, "high": 0, "warning": 0, "info": 0}
        self._scanned = False

    def discover_files(self) -> int:
        if not self.source_dir.exists(): return 0
        for f in self.source_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in REVIEW_EXTS:
                self.files.append(f)
        return len(self.files)

    def scan(self) -> bool:
        self.discover_files()
        if not self.files:
            print("  [WARN] No source files found")
            return True
        self.summary["total_files"] = len(self.files)
        print(f"  [*] Scanning {len(self.files)} files...")
        for f in self.files:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                self.summary["total_lines"] += len(lines)
                self._check_file(f, lines, content)
            except Exception as e:
                print(f"  [WARN] Skipping {f}: {e}")
        self._scanned = True
        s = self.summary
        print(f"  [+] Issues: {s['issues_found']} (C={s['critical']} H={s['high']} W={s['warning']} I={s['info']})")
        return True

    def _add(self, findings, line, sev, rule, msg, fix=""):
        findings.append({"line": line, "severity": sev, "rule": rule,
                         "message": msg, "fix": fix})

    def _check_file(self, file_path: Path, lines: List[str], content: str):
        findings = []
        ext = file_path.suffix.lower()
        text_lower = content.lower()
        linenum = lambda idx: content[:idx].count("\n") + 1

        # 1. Copyright header
        if not any("copyright" in l.lower() for l in lines[:10]):
            self._add(findings, 1, "info", "copyright-header",
                      "Missing copyright header")

        # 2. Long lines
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                self._add(findings, i, "warning", "line-length",
                          f"Line exceeds 120 chars ({len(line)})")

        # 3. Tabs
        if ext in (".sv", ".v", ".vhd"):
            for i, line in enumerate(lines, 1):
                if "\t" in line:
                    self._add(findings, i, "warning", "tabs-vs-spaces",
                              "Tab detected, use spaces")

        # 4. Async reset
        if ext in (".sv", ".v"):
            for i, line in enumerate(lines, 1):
                if "always_ff" in line or "always @(posedge" in line:
                    if "negedge rst" not in line.lower() and "negedge reset" not in line.lower():
                        self._add(findings, i, "warning", "async-reset",
                                  "Missing async reset in sequential block")

        # 5. FIFO_RD_STUCK - rd_en hardwired to 0
        for m in re.finditer(r'\.rd_en\s*\(\s*1[bB]?\s*0\s*\)', content):
            ctx = content[max(0, m.start()-60):m.start()]
            inst = "?"
            for tk in re.findall(r'(\w+)\s+#\(', ctx): inst = tk
            for tk in re.findall(r'(\w+)\s+\w+\s*\(', ctx): inst = tk
            self._add(findings, linenum(m.start()), "critical", "FIFO_RD_STUCK",
                      f"FIFO '{inst}' rd_en=0: written never read",
                      "Connect rd_en to APB read strobe")

        # 6. FIFO ports unconnected
        for pat, pname in [(r'\.rdata\s*\(\)', "rdata"),
                           (r'\.empty\s*\(\)', "empty"),
                           (r'\.full\s*\(\)', "full")]:
            for m in re.finditer(pat, content):
                self._add(findings, linenum(m.start()), "critical",
                          "FIFO_PORT_UNCONNECTED",
                          f"FIFO '{pname}' unconnected: data path dead",
                          f"Connect .{pname}() to valid signal")

        # 7. HW_PORT_ZOMBIE
        for m in re.finditer(r'assign\s+\w+\s*=\s*hw_\w+', content):
            self._add(findings, linenum(m.start()), "critical", "HW_PORT_ZOMBIE",
                      f"{m.group()} uses hw_* (likely unconnected at top)",
                      "Remove hw_* override; use FSM direct connection")

        # 8. DUAL_ASSIGN_OVERRIDE
        assigns = {}
        for m in re.finditer(r'^\s*assign\s+(\w+(?:\[\w+\])?)\s*=', content, re.MULTILINE):
            sig = m.group(1)
            assigns.setdefault(sig, []).append(m.start())
        for sig, poses in assigns.items():
            if len(poses) > 1:
                self._add(findings, linenum(poses[0]), "critical",
                          "DUAL_ASSIGN_OVERRIDE",
                          f"'{sig}' has {len(poses)} assigns: first is dead",
                          "Merge into single assign or remove duplicate")

        # 9. W1C_ON_WIRE
        if "intr_status" in text_lower or "intr_reg" in text_lower:
            for m in re.finditer(r'assign\s+(\w*(?:intr_status|intr_reg)\w*)\s*=', content, re.IGNORECASE):
                self._add(findings, linenum(m.start()), "high", "W1C_ON_WIRE",
                          f"'{m.group(1)}' is wire: W1C writes have no effect",
                          "Make intr_status a flop with W1C logic")

        # 10. NO_TOGGLE_GAP
        skip_sigs = {"clk","rstn","clk_i","rst_ni","paddr","pwdata",
                     "prdata","psel","penable","pwrite","pready","pslverr"}
        for m in re.finditer(r'(?:output|wire|logic)\s+(?:\[.*?\]\s+)?(\w+)', content):
            sig = m.group(1)
            if sig in skip_sigs: continue
            if content.count(sig) <= 1:
                self._add(findings, linenum(m.start()), "warning", "NO_TOGGLE_GAP",
                          f"'{sig}' declared but never used: 0% toggle guaranteed",
                          "Remove unused signal")

        # Deduplicate (same rule+msg)
        seen = set()
        deduped = []
        for f in findings:
            key = (f["rule"], f["message"][:60])
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        self.summary["issues_found"] += len(deduped)
        for f in deduped:
            sev = f["severity"]
            if sev in self.summary:
                self.summary[sev] += 1

        if deduped:
            self.findings[str(file_path)] = deduped

    def get_report(self) -> Dict:
        return {"tool": "review", "version": "2.0.0",
                "source_dir": str(self.source_dir),
                "summary": self.summary, "findings": self.findings,
                "verdict": "FAIL" if self.summary["critical"] > 0 else "PASS"}

    def render_md(self, report: Dict) -> str:
        s = report["summary"]
        lines = [f"# Code Review Report ({report['verdict']})", "",
                 "## Summary", "",
                 f"| Metric | Value |", f"|--------|-------|",
                 f"| Files | {s['total_files']} |",
                 f"| Lines | {s['total_lines']} |",
                 f"| Issues | {s['issues_found']} |",
                 f"| Critical | {s['critical']} |",
                 f"| High | {s['high']} |",
                 f"| Warning | {s['warning']} |",
                 f"| Info | {s['info']} |", "",
                 f"**Verdict**: {report['verdict']}", ""]
        if report["findings"]:
            lines.append("## Detailed Findings\n")
            for fp, finds in sorted(report["findings"].items()):
                lines.append(f"### {fp}\n")
                lines.append("| Line | Sev | Rule | Message | Fix |")
                lines.append("|------|-----|------|---------|-----|")
                for f in finds:
                    lines.append(f"| {f['line']} | {f['severity']} | {f['rule']} "
                                 f"| {f['message']} | {f.get('fix','')} |")
                lines.append("")
        return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(description="RTL Review Engine v2")
    ap.add_argument("--dir", "-d", required=True, help="Source directory")
    ap.add_argument("--output", "-o", default="review_report.md", help="Output path")
    ap.add_argument("--json", action="store_true", help="Also output JSON")
    args = ap.parse_args()

    if not Path(args.dir).exists():
        print(f"  [ERR] Directory not found: {args.dir}")
        return 1

    scanner = CodeScanner(args.dir)
    if not scanner.scan():
        return 1

    report = scanner.get_report()
    Path(args.output).write_text(scanner.render_md(report), encoding="utf-8")
    print(f"  [OK] Report: {args.output}")

    if args.json:
        jp = Path(args.output).with_suffix(".json")
        jp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [OK] JSON: {jp}")

    print(f"  [OK] Review done - {report['summary']['issues_found']} issues")
    return 0 if report["summary"]["critical"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())


# =============================================================================
# Review Engine — RTL Code Review with Coverage-Aware Checks
#
# Detects connectivity bugs: unconnected ports, FIFO rd_en=0, dual assigns,
# hw_* zombie ports, W1C on wires, unused signals.
#
# Usage: python run.py --dir rtl/ --output report.md
#
# Key methods:
#   scan() — Run all review checks on source directory
#   _check_file() — Per-file analysis with pattern matching
#   get_report() — Generate structured report dict
#   render_md() — Convert report to markdown
#
# Severity levels: critical (simulation/cov fail), high (design intent),
#   warning (style/detectability), info (documentation)
#
# Version: 2.0.0 — Added coverage-aware RTL connectivity checks
# =============================================================================
