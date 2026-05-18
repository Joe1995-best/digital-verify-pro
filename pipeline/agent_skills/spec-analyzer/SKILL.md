---
name: spec-analyzer
description: >
  Parse top-level spec into verification plan, identify protocols, interfaces,
  registers, and functional coverage goals. First skill in the digital verification pipeline.
---

# spec-analyzer

**Verification Architect Phase 1**: spec parsing and verification planning.

Takes a top-level specification and decomposes it into a structured verification plan with interface identification, register map extraction, protocol analysis, coverage goal definition, and test scenario planning.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `spec.yml` or `spec.md` or IP-XACT | Working directory | yes |
| User constraints (EDA tool preference, reuse strategy) | User | no |

## Outputs

| Output | Location | Description |
|--------|----------|-------------|
| `verification-plan.md` | `architect/verification-plan.md` | Full verification plan with scenarios, coverage goals, pass criteria |
| `interface-list.yml` | `architect/interface-list.yml` | All interfaces with protocol type, direction, signal list |
| `register-map.yml` | `architect/register-map.yml` | Complete register map from spec |
| `test-scenarios.yml` | `architect/test-scenarios.yml` | Test cases derived from spec |

## Capabilities

### 1. Interface Detection
- APB / AHB / AXI / AXI-Stream / AXI-Lite
- I2C / SPI / UART / I2S / JTAG
- Custom interfaces (user-defined)
- Protocol version detection (AXI3/AXI4/AXI4-Lite)

### 2. Register Analysis
- Extract address map from spec
- Detect field types (RW/RO/WO/W1C/RW1C)
- Flag reserved spaces and address holes
- Generate IP-XACT if input is YAML, or vice versa

### 3. Coverage Planning
- Functional cover points per feature
- Cross coverage between interfaces
- Protocol-specific coverage (AXI channel tracking)
- Register coverage (all addressable locations accessed)

### 4. Test Scenario Generation
- Basic functional tests (write/read/initialize)
- Protocol-specific tests (burst/unaligned/out-of-order)
- Error injection tests (parity error/CRC error/protocol violation)
- Corner cases (reset sequences/power-up/power-down)
- Random stress tests
- Register access tests
- Interrupt tests (if applicable)

## Effort Interaction

| Effort | Scenarios | Coverage detail |
|--------|-----------|----------------|
| lite | 3-5 basic tests | Functional only |
| standard | 8-12 tests | Functional + protocol |
| intensive | 15-25 tests | Full scenario matrix |
| exhaustive | 30+ tests | All scenarios + cross coverage + bugs |

## Effort

Spec analysis itself is always thorough — effort level influences downstream test generation breadth and coverage depth, not the spec parsing quality.
