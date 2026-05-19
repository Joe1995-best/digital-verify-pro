#!/usr/bin/env python3
"""
feature_decomposer.py — Feature-driven testpoint decomposition engine.

Principle: Tests are generated from SPEC FEATURES, not from RTL code.
If the RTL doesn't implement a feature, the testpoint still gets generated
and marked as UNIMPLEMENTED. This makes the verification plan a contract
between spec and RTL.

Usage:
  from feature_decomposer import decompose_features
  testpoints = decompose_features(spec_yaml_dict)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Testpoint:
    name: str
    feature: str          # which feature this tests
    stage: str            # V1=smoke, V2=stress, V3=signoff
    stimulus: str
    checking: str
    description: str
    rtl_status: str = "IMPLEMENTED"  # IMPLEMENTED | PARTIAL | UNIMPLEMENTED
    category: str = "auto_generated"
    config: str = "default"
    tests: List[str] = field(default_factory=list)


def decompose_features(spec: Dict) -> List[Testpoint]:
    """
    Take a spec YAML dict, return a list of Testpoints decomposed from features.
    Each feature in spec['features'] produces 1+ testpoints.
    """
    result = []
    module_name = spec.get("module", {}).get("name", "unknown")
    features = spec.get("features", [])
    registers = spec.get("registers", [])

    if not features:
        # Fallback: derive features from module description and register map
        features = _derive_features(spec)

    for feat in features:
        feat_name = feat.get("name", "")
        feat_desc = feat.get("description", "")
        rtl_status = feat.get("rtl_status", "IMPLEMENTED")
        category = feat.get("category", "protocol")

        tps = _feat_to_testpoints(feat, registers, module_name)
        for tp in tps:
            # Feature-level UNIMPLEMENTED propagates; otherwise keep testpoint override
            if rtl_status == "UNIMPLEMENTED":
                tp.rtl_status = "UNIMPLEMENTED"
        result.extend(tps)

    # Always add register-level testpoints regardless of features
    result.extend(_register_testpoints(registers, module_name))

    return result


def _derive_features(spec: Dict) -> List[Dict]:
    """
    Derive features from spec description and registers when no explicit features section.
    This creates the feature set from what the spec SAYS it should do.
    """
    desc = spec.get("module", {}).get("description", "").lower()
    interfaces = spec.get("interfaces", [])
    registers = spec.get("registers", [])

    features = []

    # Detect protocol type
    proto_types = {i["type"].upper() for i in interfaces
                   if i["type"].upper() not in ("APB", "INTERRUPT")}

    # Bus protocol — always present
    features.append({
        "name": "apb_interface",
        "description": "APB slave register interface for configuration and status",
        "category": "bus",
        "rtl_status": "IMPLEMENTED",
    })

    # Collect all field names for keyword matching
    all_field_names = []
    for r in registers:
        for f in r.get("fields", []):
            all_field_names.append(f["name"].lower())
    field_text = " ".join(all_field_names)

    # Detect features from description keywords
    feature_keywords = [
        ("i2c_controller", "I2C controller (master) mode", "protocol",
         "master" in desc or "controller" in desc or "I2C" in desc.upper()),
        ("i2c_target", "I2C target (slave) mode", "protocol",
         "target" in field_text or "slave" in desc or "target" in desc or "I2C" in desc.upper()),
        ("i2c_target", "I2C target (slave) mode", "protocol",
         "slave" in desc or "target" in desc or "both" in desc),
        ("multi_controller", "Multi-controller arbitration support", "protocol",
         "multi" in desc or "arbitration" in desc),
        ("clock_stretching", "Clock stretching support", "protocol",
         "stretch" in desc),
        ("speed_config", "Configurable bus speed (100k/400k/1M)", "protocol",
         "speed" in desc or "configurable" in desc),
        ("fifo", "TX/RX FIFO with threshold and overflow handling", "fifo",
         "fifo" in desc),
        ("interrupt", "Interrupt generation and clearing", "interrupt",
         "interrupt" in desc),
        ("start_stop", "START/STOP condition generation", "protocol",
         "start" in desc or "stop" in desc or "start" in field_text or "stop" in field_text),
        ("ack_nack", "ACK/NACK generation and detection", "protocol",
         "ack" in desc or "nack" in desc or "ack" in field_text or "nack" in field_text),
        ("ten_bit_addr", "10-bit addressing mode", "protocol",
         "10bit" in desc or "10-bit" in desc or "10bit" in field_text),
        ("dma_transfer", "DMA transfer engine", "protocol",
         "dma" in desc),
        ("host_interface", "Host bus interface for data transfer", "protocol",
         "host" in desc),
        ("error_handling", "Error detection and recovery", "error",
         "error" in desc or "error" in field_text),
        ("reset_handling", "Reset behavior and recovery", "reset",
         True),
    ]

    for fname, fdesc, fcat, present in feature_keywords:
        if present:
            features.append({
                "name": fname,
                "description": fdesc,
                "category": fcat,
                "rtl_status": "IMPLEMENTED",
            })

    # Add register-specific features
    reg_names = [r["name"] for r in registers]

    # Detect specific features from register fields
    has_clock_stretch = any(
        "stretch" in f.get("name", "").lower()
        for r in registers for f in r.get("fields", [])
    )
    has_interrupt = any(
        "intr" in f.get("name", "").lower()
        for r in registers for f in r.get("fields", [])
    )
    has_arbitration = any(
        "arb" in f.get("name", "").lower()
        for r in registers for f in r.get("fields", [])
    )
    has_fifo = any("fifo" in r["name"].lower() for r in registers)
    has_speed = any("speed" in r["name"].lower() for r in registers)
    has_tenbit = any("10bit" in f.get("name", "").lower()
                     for r in registers for f in r.get("fields", []))

    if has_clock_stretch and not any(f["name"] == "clock_stretching" for f in features):
        features.append({"name": "clock_stretching", "description": "Clock stretching from register field", "category": "protocol", "rtl_status": "IMPLEMENTED"})
    if has_arbitration and not any(f["name"] == "multi_controller" for f in features):
        features.append({"name": "multi_controller", "description": "Multi-controller arbitration from register field", "category": "protocol", "rtl_status": "IMPLEMENTED"})
    if has_tenbit and not any(f["name"] == "ten_bit_addr" for f in features):
        features.append({"name": "ten_bit_addr", "description": "10-bit addressing from register field", "category": "protocol", "rtl_status": "IMPLEMENTED"})

    return features


def _feat_to_testpoints(feat: Dict, registers: List[Dict], module: str) -> List[Testpoint]:
    """Generate testpoints for a single feature."""
    name = feat["name"]
    desc = feat["description"]
    cat = feat.get("category", "protocol")

    # Feature-to-testpoint mapping
    mapper = {
        "i2c_controller": _tp_i2c_controller,
        "i2c_target": _tp_i2c_target,
        "multi_controller": _tp_multi_controller,
        "clock_stretching": _tp_clock_stretch,
        "speed_config": _tp_speed_config,
        "fifo": _tp_fifo,
        "interrupt": _tp_interrupt,
        "start_stop": _tp_start_stop,
        "ack_nack": _tp_ack_nack,
        "ten_bit_addr": _tp_ten_bit_addr,
        "apb_interface": _tp_apb,
        "dma_transfer": _tp_dma_transfer,
        "host_interface": _tp_host,
        "error_handling": _tp_error,
        "reset_handling": _tp_reset,
    }

    if name in mapper:
        return mapper[name](feat, registers, module)
    else:
        return [Testpoint(
            name=f"{module}_{name}_smoke",
            feature=name,
            stage="V1",
            stimulus=f"Configure and exercise {desc}",
            checking=f"Verify {desc} operates correctly",
            description=f"Smoke test for {desc}",
        )]


def _tp_i2c_controller(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_host_smoke", feature=feat["name"], stage="V1",
            stimulus="Configure I2C controller mode, set speed, program address and data, start transaction",
            checking="START condition generated, address sent, ACK received, data byte transferred, STOP condition generated, cmd_complete interrupt asserted",
            description="I2C controller basic write transaction"),
        Testpoint(name=f"{mod}_host_read", feature=feat["name"], stage="V1",
            stimulus="Configure controller read: START + addr(R) + data bytes + NACK + STOP",
            checking="Received data in rx_data_reg, NACK sent after last byte, STOP generated",
            description="I2C controller basic read transaction"),
        Testpoint(name=f"{mod}_host_combined", feature=feat["name"], stage="V2",
            stimulus="Combined transaction: START + addr(W) + data + RESTART + addr(R) + data + STOP",
            checking="Repeated START condition, correct data in both directions, final STOP",
            description="I2C controller combined write+read with restart"),
        Testpoint(name=f"{mod}_host_backtoback", feature=feat["name"], stage="V2",
            stimulus="Multiple back-to-back write transactions without intervening idle bus time",
            checking="Each transaction completes correctly, bus free time between transactions within spec",
            description="I2C controller back-to-back transactions"),
    ]


def _tp_i2c_target(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_target_smoke", feature=feat["name"], stage="V1",
            stimulus="Configure I2C target mode, external controller sends write then read",
            checking="Address match ACK, write data in ACQ FIFO, target TX data sent on read",
            description="I2C target basic operation",
            rtl_status="UNIMPLEMENTED"),
        Testpoint(name=f"{mod}_target_addr_mask", feature=feat["name"], stage="V2",
            stimulus="Configure target with address mask, send addresses within/outside mask range",
            checking="Matching addresses ACKed, non-matching addresses NACKed/dropped",
            description="I2C target address mask filtering",
            rtl_status="UNIMPLEMENTED"),
    ]


def _tp_multi_controller(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_arbitration_lost", feature=feat["name"], stage="V2",
            stimulus="Two controllers driving simultaneously: conflicting data on SDA",
            checking="Arbitration lost flag set, bus released, no data corruption on winning controller's transaction",
            description="Multi-controller arbitration lost detection and recovery"),
        Testpoint(name=f"{mod}_bus_monitor", feature=feat["name"], stage="V2",
            stimulus="Enable bus monitor in multi-controller mode, observe transaction from external controller",
            checking="Bus free/busy status accurate, bus free time measured correctly",
            description="Multi-controller bus monitor mode",
            rtl_status="PARTIAL"),
    ]


def _tp_clock_stretch(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_controller_stretch", feature=feat["name"], stage="V2",
            stimulus="Enable clock stretching, slave holds SCL low after ACK",
            checking="Controller waits (SCL high), resumes after slave releases SCL, no data loss",
            description="I2C controller clock stretching handling"),
        Testpoint(name=f"{mod}_stretch_timeout", feature=feat["name"], stage="V2",
            stimulus="Program timeout value, slave holds SCL low beyond timeout",
            checking="Stretch timeout interrupt asserted, transaction terminated with STOP",
            description="Clock stretch timeout detection",
            rtl_status="PARTIAL"),
    ]


def _tp_speed_config(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_speed_100k", feature=feat["name"], stage="V1",
            stimulus="Configure speed_reg for 100kHz, run write transaction",
            checking="SCL frequency = 100kHz ± tolerance, transaction completes correctly",
            description="Standard mode 100kHz operation"),
        Testpoint(name=f"{mod}_speed_400k", feature=feat["name"], stage="V1",
            stimulus="Configure speed_reg for 400kHz, run write transaction",
            checking="SCL frequency = 400kHz ± tolerance, transaction completes correctly",
            description="Fast mode 400kHz operation"),
        Testpoint(name=f"{mod}_speed_1m", feature=feat["name"], stage="V1",
            stimulus="Configure speed_reg for 1MHz, run write transaction",
            checking="SCL frequency = 1MHz ± tolerance, transaction completes correctly",
            description="Fast mode plus 1MHz operation"),
        Testpoint(name=f"{mod}_speed_dynamic", feature=feat["name"], stage="V2",
            stimulus="Change speed mid-operation across transactions without reset",
            checking="Both frequencies correct, no bus errors from speed change",
            description="Dynamic speed switching"),
    ]


def _tp_fifo(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_fifo_fill_drain", feature=feat["name"], stage="V1",
            stimulus="Fill TX FIFO to threshold/watermark, drain RX FIFO to empty",
            checking="TX full flag asserted, RX empty flag asserted, data integrity after drain",
            description="FIFO basic fill and drain"),
        Testpoint(name=f"{mod}_fifo_watermark", feature=feat["name"], stage="V2",
            stimulus="Program TX/RX threshold, cross threshold in both directions",
            checking="Threshold interrupt asserted at correct level, clears when level recedes",
            description="FIFO watermark/threshold interrupt"),
        Testpoint(name=f"{mod}_fifo_overflow", feature=feat["name"], stage="V2",
            stimulus="Write beyond FIFO depth, read back",
            checking="Overflow flag set, first entries retain correct data, no corruption",
            description="FIFO overflow behavior"),
        Testpoint(name=f"{mod}_fifo_flush", feature=feat["name"], stage="V2",
            stimulus="Fill FIFO partially, assert flush, immediately read",
            checking="FIFO empty after flush, no stale data, both TX/RX flush independently",
            description="FIFO flush/reset"),
        Testpoint(name=f"{mod}_fifo_full", feature=feat["name"], stage="V2",
            stimulus="Fill FIFO completely, attempt further writes and reads",
            checking="Full status accurate, writes rejected when full, no data loss during full condition",
            description="FIFO full state behavior"),
        Testpoint(name=f"{mod}_fifo_simultaneous", feature=feat["name"], stage="V2",
            stimulus="Simultaneous FIFO read and write at full speed",
            checking="Pointers increment correctly, no data corruption, no overflow/underflow",
            description="FIFO simultaneous read and write"),
    ]


def _tp_interrupt(feat, regs, mod) -> List[Testpoint]:
    tps = [
        Testpoint(name=f"{mod}_intr_assert_clear", feature=feat["name"], stage="V1",
            stimulus="Trigger each interrupt source, read interrupt status",
            checking="Each pending bit set correctly, read-to-clear behavior works, all bits return to 0",
            description="Interrupt assertion and clearing"),
        Testpoint(name=f"{mod}_intr_multiple", feature=feat["name"], stage="V2",
            stimulus="Assert multiple interrupt sources simultaneously",
            checking="All sources reflected in status, clearing individual source does not affect others",
            description="Multiple concurrent interrupt sources"),
    ]
    # Add per-interrupt testpoints from register fields
    intr_regs = [r for r in regs if "intr" in r["name"].lower()]
    for r in intr_regs:
        for f in r.get("fields", []):
            if "intr" in f.get("name", "").lower() or "reserved" not in f.get("name", "").lower():
                pass  # keep generic
    return tps


def _tp_start_stop(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_start_condition", feature=feat["name"], stage="V1",
            stimulus="Write cmd_reg.start=1, observe SDA/SCL",
            checking="SDA falling edge while SCL high, START timing meets I2C spec min hold times",
            description="START condition generation"),
        Testpoint(name=f"{mod}_stop_condition", feature=feat["name"], stage="V1",
            stimulus="Write cmd_reg.stop=1, observe SDA/SCL",
            checking="SDA rising edge while SCL high, STOP timing meets I2C spec min setup times",
            description="STOP condition generation"),
        Testpoint(name=f"{mod}_repeated_start", feature=feat["name"], stage="V2",
            stimulus="Generate RESTART instead of STOP between transactions",
            checking="RESTART condition (no STOP before second START), bus remains active",
            description="Repeated START condition"),
    ]


def _tp_ack_nack(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_ack_received", feature=feat["name"], stage="V1",
            stimulus="Write to slave that ACKs, observe ACK bit after address byte",
            checking="ACK received flag not set, transaction continues normally",
            description="ACK from slave received correctly"),
        Testpoint(name=f"{mod}_nack_received", feature=feat["name"], stage="V2",
            stimulus="Write to non-existent slave address, observe NACK",
            checking="NACK flag set, transaction stops or generates STOP, interrupt asserted",
            description="NACK from slave detected and handled"),
        Testpoint(name=f"{mod}_nack_sent", feature=feat["name"], stage="V2",
            stimulus="Master read with NAKOK set after last byte",
            checking="NACK sent after final data byte, STOP generated, no bus conflict",
            description="Master NACK generation on last read byte"),
    ]


def _tp_ten_bit_addr(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_addr_10bit_write", feature=feat["name"], stage="V2",
            stimulus="Configure addr_10bit=1, set 10-bit address, start write transaction",
            checking="Two address bytes sent: 11110xx(W) + first data byte, transaction completes",
            description="10-bit addressing write"),
        Testpoint(name=f"{mod}_addr_10bit_read", feature=feat["name"], stage="V2",
            stimulus="Configure 10-bit address, start read transaction with RESTART",
            checking="Full 10-bit read sequence: addr(W) + restart + addr(R) + data",
            description="10-bit addressing read"),
    ]


def _tp_apb(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_reg_reset", feature=feat["name"], stage="V1",
            stimulus="Assert reset, deassert, read all registers",
            checking="Each register matches its spec reset value",
            description="Register reset values"),
        Testpoint(name=f"{mod}_reg_rw", feature=feat["name"], stage="V1",
            stimulus="Write each RW field with pattern, read back",
            checking="Written data matches read data, field-level access per access type (RW/RO/WO)",
            description="Register read/write access"),
        Testpoint(name=f"{mod}_reg_bitbash", feature=feat["name"], stage="V1",
            stimulus="Walk a 1 through each multi-bit field, read back after each bit flip",
            checking="Each bit toggles independently, no aliasing between adjacent bits",
            description="Register bit-bash independence"),
        Testpoint(name=f"{mod}_reg_reserved", feature=feat["name"], stage="V1",
            stimulus="Write 1s to all reserved bit positions, read back",
            checking="Reserved bits read as 0, writable bits unaffected",
            description="Reserved bit positions stuck-at-0"),
        Testpoint(name=f"{mod}_reg_aliasing", feature=feat["name"], stage="V1",
            stimulus="Write each register, read ALL registers sequentially",
            checking="Non-written registers return previous value, no cross-talk",
            description="Register aliasing (cross-talk) check"),
        Testpoint(name=f"{mod}_pslverr", feature=feat["name"], stage="V1",
            stimulus="Access reserved address space (>= 0x24)",
            checking="PSLVERR asserted, prdata returns 0",
            description="Reserved address → PSLVERR"),
    ]


def _tp_dma_transfer(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_dma_basic", feature=feat["name"], stage="V1",
            stimulus="Configure src/dst addresses, total_size, start DMA",
            checking="Host read request issued, data returned, host write completes, done flag set",
            description="DMA single-word transfer"),
        Testpoint(name=f"{mod}_dma_multiple", feature=feat["name"], stage="V2",
            stimulus="Configure multi-word transfer (4+ words), handle alternating read/write host cycles",
            checking="All words transferred, remaining_q decrements, done flag set, no error",
            description="DMA multi-word transfer"),
        Testpoint(name=f"{mod}_dma_error", feature=feat["name"], stage="V2",
            stimulus="Start DMA, inject host error mid-transfer",
            checking="Error flag set, error_code reports bus error, host activity stops",
            description="DMA host error handling"),
        Testpoint(name=f"{mod}_dma_abort", feature=feat["name"], stage="V3",
            stimulus="Start DMA, assert stop mid-transfer",
            checking="Transfer aborts cleanly, partial data coherent, re-startable",
            description="DMA abort mid-transfer",
            rtl_status="UNIMPLEMENTED"),
    ]


def _tp_host(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_host_grant", feature=feat["name"], stage="V1",
            stimulus="Initiate host request, assert grant",
            checking="After grant, host completes transaction, deasserts request",
            description="Host grant handshake"),
        Testpoint(name=f"{mod}_host_timeout", feature=feat["name"], stage="V2",
            stimulus="Initiate host request, never grant",
            checking="Timeout interrupt after configurable duration, host returns to idle",
            description="Host request timeout",
            rtl_status="UNIMPLEMENTED"),
    ]


def _tp_error(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_error_status", feature=feat["name"], stage="V2",
            stimulus="Trigger each error condition, read error status register",
            checking="Each error type has unique error_code, status register reflects active errors",
            description="Error status register coverage"),
        Testpoint(name=f"{mod}_error_recovery", feature=feat["name"], stage="V3",
            stimulus="Trigger error, clear error, resume normal operation",
            checking="After clear, design returns to normal, no residual error state",
            description="Error recovery after fault"),
    ]


def _tp_reset(feat, regs, mod) -> List[Testpoint]:
    return [
        Testpoint(name=f"{mod}_reset_value", feature=feat["name"], stage="V1",
            stimulus="Assert and deassert reset, read all registers and status outputs",
            checking="All registers at reset values, FSM in IDLE, outputs initialized",
            description="Reset value verification"),
        Testpoint(name=f"{mod}_reset_active_mid", feature=feat["name"], stage="V2",
            stimulus="Start transaction, assert reset before completion, deassert, check state",
            checking="Clean state after reset, no bus hang, design is restartable",
            description="Reset during active transaction"),
    ]


def _register_testpoints(registers: List[Dict], module: str) -> List[Testpoint]:
    """Generate per-register testpoints."""
    tps = []
    for r in registers:
        rname = r["name"]
        roffset = r["offset"]
        fields = r.get("fields", [])
        accs = {f["access"].lower() for f in fields}

        # RW test per register
        if any(a in ("rw", "wo") for a in accs):
            tps.append(Testpoint(
                name=f"{module}_reg_rw_{rname}",
                feature="apb_interface",
                stage="V1",
                stimulus=f"Write pattern to {rname} ({roffset}), read back and verify",
                checking=f"Field-level correctness for {rname}: writable fields updated, read returns written value",
                description=f"Register RW: {rname}",
            ))

        # RO test per register
        ro_fields = [f for f in fields if f["access"].lower() == "ro"
                     and "reserved" not in f.get("name", "").lower()]
        if ro_fields:
            tps.append(Testpoint(
                name=f"{module}_reg_ro_{rname}",
                feature="apb_interface",
                stage="V1",
                stimulus=f"Write 0xFFFFFFFF to {rname} ({roffset}), read back",
                checking=f"RO fields return reset values, write is ignored for RO bits",
                description=f"Register RO: {rname}",
            ))

        # Reserved fields test
        res_fields = [f for f in fields if "reserved" in f.get("name", "").lower()]
        if res_fields:
            tps.append(Testpoint(
                name=f"{module}_reg_reserved_{rname}",
                feature="apb_interface",
                stage="V1",
                stimulus=f"Write 1s to reserved bit positions in {rname} ({roffset})",
                checking=f"Reserved bits read back as 0",
                description=f"Register reserved bits: {rname}",
            ))

        # Bit-bash per multi-bit writable field
        for f in fields:
            bits = f.get("bits", "[0]").strip("[]")
            width = (int(bits.split(":")[0]) - int(bits.split(":")[1]) + 1) if ":" in bits else 1
            access = f.get("access", "rw").lower()
            if width > 1 and access in ("rw", "wo"):
                tps.append(Testpoint(
                    name=f"{module}_bitbash_{rname}_{f['name']}",
                    feature="apb_interface",
                    stage="V1",
                    stimulus=f"Walk a 1 through {rname}.{f['name']} ({bits}, {width}-bit): write each bit pattern, read back",
                    checking=f"Each bit toggles independently, no aliasing between adjacent bits within field",
                    description=f"Bit-bash: {rname}.{f['name']}",
                ))

    return tps


def render_testplan_markdown(testpoints: List[Testpoint]) -> str:
    """Render testpoints as markdown verification plan."""
    lines = []
    lines.append(f"# Feature-Driven Verification Plan")
    lines.append(f"")
    lines.append(f"**Total testpoints:** {len(testpoints)}")
    lines.append(f"")

    # Group by feature
    from collections import OrderedDict
    by_feature: Dict[str, List[Testpoint]] = OrderedDict()
    for tp in testpoints:
        by_feature.setdefault(tp.feature, []).append(tp)

    for feat_name, tps in by_feature.items():
        stages = set(tp.stage for tp in tps)
        n_impl = sum(1 for tp in tps if tp.rtl_status == "IMPLEMENTED")
        n_unimpl = sum(1 for tp in tps if tp.rtl_status != "IMPLEMENTED")
        status_tag = f" ({n_impl} impl, {n_unimpl} gap)" if n_unimpl else ""

        lines.append(f"## Feature: {feat_name}{status_tag}")
        lines.append(f"")
        lines.append(f"| Testpoint | Stage | Status | Stimulus | Checking |")
        lines.append(f"|-----------|-------|--------|----------|----------|")
        for tp in tps:
            status = tp.rtl_status
            stim = tp.stimulus[:60] + "..." if len(tp.stimulus) > 60 else tp.stimulus
            chk = tp.checking[:60] + "..." if len(tp.checking) > 60 else tp.checking
            lines.append(f"| {tp.name} | {tp.stage} | {status} | {stim} | {chk} |")
        lines.append(f"")

    # Summary
    n_v1 = sum(1 for tp in testpoints if tp.stage == "V1")
    n_v2 = sum(1 for tp in testpoints if tp.stage == "V2")
    n_v3 = sum(1 for tp in testpoints if tp.stage == "V3")
    n_gap = sum(1 for tp in testpoints if tp.rtl_status != "IMPLEMENTED")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total testpoints | {len(testpoints)} |")
    lines.append(f"| V1 (smoke) | {n_v1} |")
    lines.append(f"| V2 (stress) | {n_v2} |")
    lines.append(f"| V3 (signoff) | {n_v3} |")
    lines.append(f"| Implemented | {len(testpoints) - n_gap} |")
    lines.append(f"| Gaps (UNIMPLEMENTED) | {n_gap} |")
    lines.append(f"")

    return "\n".join(lines)


def render_json(testpoints: List[Testpoint]) -> List[Dict]:
    """Render testpoints as JSON-serializable dicts."""
    return [
        {
            "name": tp.name,
            "feature": tp.feature,
            "stage": tp.stage,
            "stimulus": tp.stimulus,
            "checking": tp.checking,
            "description": tp.description,
            "rtl_status": tp.rtl_status,
            "category": tp.category,
            "config": tp.config,
            "tests": tp.tests or [f"{tp.name}_test"],
        }
        for tp in testpoints
    ]


# =============================================================================
# Feature Decomposer — Functional Feature Decomposition Engine
#
# Decomposes spec YAML into hierarchical functional features for verification
# planning. Generates feature-to-test mapping matrices and coverage gap analyses.
#
# Key functions:
#   extract_features(spec_data) - Parse spec into feature hierarchy
#   build_mapping_matrix(features, tests) - Generate traceability matrix
#   analyze_coverage_gaps(features, coverage) - Find uncovered features
#
# Dependencies: Python >= 3.10 (pure standard library)
# =============================================================================



# =============================================================================
# Feature Decomposer - Functional Feature Decomposition
#
# Decomposes IC spec YAML into hierarchical functional features:
#   1. Feature hierarchy extraction (modules, interfaces, registers, FSM)
#   2. Feature-to-test mapping matrix (traceability)
#   3. Coverage gap analysis (uncovered features with severity)
#
# Input: spec YAML + optional coverage gap JSON
# Output: feature hierarchy, mapping matrix, gap report
# Dependencies: Python >= 3.10 (pure stdlib)
# =============================================================================

