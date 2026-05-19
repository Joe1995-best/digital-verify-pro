# digital-verify-pro

**专业级数字芯片验证框架** — 双模式并行：手写 RTL + VRF 仿真验证 / spec-YAML → RTL 自动生成 + 仿真验证。覆盖度驱动收敛，RTL 审查 + 验证签收清单自动化。纯 SystemVerilog + iverilog 兼容，不需要商业 EDA 工具。

## 快速开始

```bash
# 安装依赖
pip install pyyaml jinja2

# Mode 1: 手写 RTL 验证 (DMA)
python run_dma_convergence.py

# Mode 2: Spec → RTL 生成 + 验证
python pipeline/run_rtl_gen.py --spec ot_dma_spec.yml --out output_ot_dma
python pipeline/run_sim.py --spec ot_dma_spec.yml

# 覆盖度分析
python engines/coverage_engine.py --vcd dma_full_test.vcd --clk clk_i
```

## 已验证 IP

| IP | 状态 | 覆盖率 | 说明 |
|:---|:----:|:------:|------|
| OT DMA v4 | ✅ | 93.8% | 22/22 测试全过, 0 stuck |
| I2C Controller | ✅ | 84.2% | 含覆盖度收敛 + RTL bug修复 |
| SPI Slave | ✅ | 65.7% | 完整spec→RTL→仿真流水线 |
| ALU4 | ✅ | — | 小规模验证 |
| Dual Port Stack | ✅ | — | 形式验证通过 |

## 项目架构

```
digital-verify-pro/
├── engines/              # Pro 引擎 (coverage/formal/regression/dashboard)
├── pipeline/             # 流水线脚本 (spec→RTL→env→sim→signoff)
│   ├── agent_skills/     # 12个Agent Skills描述
│   ├── templates/        # UVM/FSM模板
│   └── run_*.py          # 各阶段执行脚本
├── standalone-skills/    # 19个独立化技能包 (全部 Approved)
├── checklists/           # 验证签收清单 (含OpenTitan对齐)
├── examples/             # 示例testbench
├── tools/                # 质量评估/分析工具
└── wiki/                 # 知识库
```

## 核心能力

### 验证流水线
```
spec.yml → spec-analyzer → rtl-gen → env-builder → test-generator
    → tb-compiler → sim-runner → coverage-engine → review → sign-off
```

### 独立化 Skill (standalone-skills/)
每个 skill 包含 SKILL.md + run.py + 代码 + requirements + CHANGELOG + 测试，可独立运行或上传技能市场。

| 类别 | 技能 | 评分 |
|:----|:-----|:----:|
| 覆盖度 | coverage-engine | ✅ Approved |
| 代码审查 | review | ✅ Approved |
| 仿真运行 | sim-runner, tb-compiler | ✅ Approved |
| UVM生成 | env-builder, test-generator, regmodel-gen, scoreboard-gen | ✅ Approved |
| 断言生成 | assertion-gen | ✅ Approved |
| Spec分析 | spec-analyzer, coverage-plan | ✅ Approved |
| 文档生成 | doc-gen | ✅ Approved |
| 形式验证 | formal-check | ✅ Approved |
| RTL生成 | plan-generator, fsm-templates, feature-decomposer | ✅ Approved |
| 其他 | dashboard-gen, regression-manager, waveform-analyzer | ✅ Approved |

### 质量评估
```bash
# 评估任意 skill 质量 (5维度100分制)
python tools/quality_pipeline.py standalone-skills/coverage-engine/

# 结果: Q1功能24/25 Q2代码17/20 Q3安全15/20 Q4运行13/20 Q5兼容10/15 → 79/100 Approved
```

### 覆盖度收敛
```bash
# 分析VCD -> 缺口检测 -> 靶向测试 -> re-sim -> 覆盖度提升
python tools/quality_pipeline.py standalone-skills/coverage-engine/run.py --vcd sim.vcd --gaps gaps.json
python standalone-skills/review/run.py --dir output/rtl/   # RTL审查
python tools/review_to_checklist.py --review review_report.json  # 审查→bug追踪
```

### OpenTitan 对齐
完整的验证清单覆盖 OpenTitan 验证方法论：
- CSR 自动测试生成与签收
- 多种子回归 ≥10
- UVM RAL 单源一致性
- 功能覆盖度逐特征 ≥90%
- 故障注入测试
- X-Propagation 形式检查
- 签收 Tag 与 Release 管理

## 依赖

- **Python**: >= 3.10
- **iverilog**: >= 11.0 (ICARUS Verilog)
- **pyyaml**, **jinja2** (RTL生成)
- **sby** (形式验证, 可选)

## License

MIT
