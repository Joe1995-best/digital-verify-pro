"""
Field-level toggle coverage mapper.

Reads a YAML spec to extract register fields with bit positions,
then maps VCD signal names and bit positions to register fields and
computes per-field toggle status.

Usage:
    mapper = FieldCoverageMapper("i2c_spec.yml")
    report = mapper.analyze(parsed_vcd)
    # report -> {"ctrl_reg.enable": {"bits": 1, "toggled": 1, "status": "PASS"}, ...}
"""

import json
import os
import yaml
from typing import Any


# ── Field description ───────────────────────────────────────────────────────

FieldDef = dict[str, Any]
"""
  name    : str
  bits    : str   (e.g. "[0]", "[15:8]", "[31:0]")
  access  : str   (rw/ro/wo)
  reset   : str
"""


class FieldCoverageMapper:
    """Mapper between YAML register fields and VCD signal bits."""

    def __init__(self, spec_path: str):
        self.spec_path = spec_path
        self.fields: list[FieldDef] = []
        self._parse_spec()

    def _parse_spec(self) -> None:
        """Read ``registers`` from the spec YAML and flatten fields."""
        if not os.path.isfile(self.spec_path):
            raise FileNotFoundError(f"Spec not found: {self.spec_path}")

        with open(self.spec_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw_regs = data.get("registers", [])
        for reg in raw_regs:
            reg_name: str = reg["name"]
            for field in reg.get("fields", []):
                fdef: FieldDef = {
                    "name": f"{reg_name}.{field['name']}",
                    "bits": field["bits"],
                    "access": field.get("access", "rw"),
                    "reset": field.get("reset", "0"),
                    "reg": reg_name,
                }
                self.fields.append(fdef)

    def _bits_range(self, bits_spec: str) -> tuple[int, int]:
        """Parse bit spec string → (high_bit, low_bit).

        Examples:
            "[0]"     → (0, 0)
            "[4]"     → (4, 4)
            "[15:8]"  → (15, 8)
            "[31:0]"  → (31, 0)
        """
        raw = bits_spec.strip().strip("[]")
        if ":" in raw:
            hi_s, lo_s = raw.split(":", 1)
            return int(hi_s), int(lo_s)
        v = int(raw)
        return v, v

    def map_signal_to_field(self, signal_name: str, bit_position: int) -> str | None:
        """Return the fully-qualified field name that contains *bit_position*
        within *signal_name*, or None if no match.

        This is a simplified heuristic: the YAML register name is matched
        as a substring of *signal_name* (e.g. ``ctrl_reg`` → ``ctrl_reg_q``).
        """
        for f in self.fields:
            reg = f["reg"]
            if reg not in signal_name:
                continue
            hi, lo = self._bits_range(f["bits"])
            if lo <= bit_position <= hi:
                return f["name"]
        return None

    def analyze(self, parsed_vcd: dict[str, Any]) -> dict[str, Any]:
        """Analyze toggle coverage for every known field.

        *parsed_vcd* is expected to be a dict keyed by signal name where each
        value is a dict with ``width`` (int) and ``toggles`` (dict of
        bit_position → int, or a flat integer for 1-bit signals).

        Returns a JSON-serialisable dict:
            {"<reg>.<field>": {"bits": N, "toggled": M, "status": "PASS"|"PARTIAL"|"ZERO"}, …}
        """
        report: dict[str, Any] = {}

        for f in self.fields:
            # Find VCD signal
            sig_name = f["reg"]
            vcd_sig = parsed_vcd.get(sig_name)

            if vcd_sig is None:
                # Try case-insensitive suffix match
                for vname, vsig in parsed_vcd.items():
                    if sig_name in vname or vname in sig_name:
                        vcd_sig = vsig
                        break

            hi, lo = self._bits_range(f["bits"])
            bit_count = hi - lo + 1
            toggled_bits = 0

            if vcd_sig is not None:
                width = vcd_sig.get("width", 1)
                toggles_raw = vcd_sig.get("toggles", {})

                for bp in range(lo, min(hi + 1, width)):
                    # toggles could be per-bit or aggregate
                    count = toggles_raw.get(str(bp), 0)
                    if isinstance(toggles_raw, int):
                        # flat signal — toggled if non-zero
                        count = toggles_raw

                    # Handle direct VCD backend format: dict with "toggled" boolean
                    if isinstance(toggles_raw, dict) and "toggled" in toggles_raw:
                        count = 1 if toggles_raw["toggled"] else 0

                    if count > 0:
                        toggled_bits += 1

            if toggled_bits == bit_count:
                status = "PASS"
            elif toggled_bits > 0:
                status = "PARTIAL"
            else:
                status = "ZERO"

            report[f["name"]] = {
                "bits": bit_count,
                "toggled": toggled_bits,
                "status": status,
            }

        return report

    def to_json(self, parsed_vcd: dict[str, Any], output_path: str | None = None) -> str:
        """Analyze and serialize to JSON. Writes to *output_path* if given."""
        report = self.analyze(parsed_vcd)
        text = json.dumps(report, indent=2, ensure_ascii=False)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
        return text
