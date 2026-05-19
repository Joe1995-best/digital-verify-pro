# OpenTitan Verification Alignment [COMMON] — Checklist Supplement

对照 OpenTitan (lowRISC) 验证方法论，填补 digital-verify-pro checklist 缺口。

---

## OT-S1: CSR 自动测试生成与签收 [COMMON]

OpenTitan 从统一 spec 生成 CSR 测试序列，逐字段验证 RW/RO/W1C/WO。

### 检查项

- [ ] **CSR 测试覆盖率 100%**: 每个寄存器每个字段至少有一个测试
  - RW 字段: 写任意值 → 读回一致
  - RO 字段: 写任意值 → 读回复位值（写忽略）
  - W1C 字段: 写 1 → 对应位清 0，其他位不变
  - WO 字段: 写后读回复位值（写后立即清 0）
- [ ] **保留字段 (reserved)**: 写 0 读回 0，写非 0 读回 0（不可写）
- [ ] **>16-bit 字段**: 测试高位写入与回读（边界值检测）
- [ ] **CSR 测试脚本**: `run_csr_test_gen.py` 生成，自动编译+运行

### 命令
```bash
# 一键跑 CSR 测试
python pipeline/run_csr_test_gen.py --spec spec.yml --out output/
```

---

## OT-S2: 多种子回归 (Multi-Seed Regression) [COMMON]

OpenTitan 每个测试用 100+ 随机种子运行，确保随机稳定性。

### 检查项

- [ ] **最小种子数 ≥10 个**: 每个测试至少 10 个不同的随机种子
- [ ] **种子列表可配置**: `--seeds <N>` 或 `--seed-list <file>`
- [ ] **无种子相关失败**: 随机约束不依赖种子值
- [ ] **无 timeout 种子**: 所有种子在合理时间内完成
- [ ] **回归流水线**: `run_dma_convergence.py` 支持多种子运行

| 回归类型 | 种子数 | 频率 | 通过标准 |
|---------|:------:|:----:|:--------:|
| smoke | 1 | 每次提交 | 100% PASS |
| full | 10 | 每天 | 100% PASS |
| stress | 100 | 每周 | ≥99% PASS, 无 timeout |
| nightly | 1000 | CI nightly | ≥99% PASS |

### 命令
```bash
# 多种子回归
python run_sim.py --spec spec.yml --seeds 100 --out regression/
```

---

## OT-S3: Verilator Lint 与代码质量门禁 [COMMON]

OpenTitan 对生成的 RTL 运行 Verilator lint 检查。

### 检查项

- [ ] **Verilator lint 0 error**: `verilator --lint-only —top-module <module>`
- [ ] **无 `always_comb` 读取 `always_ff` 变量**: iverilog 兼容检查 (S2.1)
- [ ] **无 `case` 缺失兜底**: default case 存在
- [ ] **无未连接端口 (unconnected port)**: review skill `FIFO_PORT_UNCONNECTED` 检查
- [ ] **信号位宽匹配**: 所有赋值位宽一致 (review skill 位宽检查)

### 命令
```bash
verilator --lint-only --top-module spi_slave -f rtl.f
python run.py --dir output/rtl/rtl/           # review skill
```

---

## OT-S4: UVM RAL 单源一致性 [COMMON]

OpenTitan 保证 UVM RAL (寄存器抽象层) 与 RTL 来自同一份 spec。

### 检查项

- [ ] **RAL 生成**: `run_ral_gen.py --spec spec.yml --out output/`
- [ ] **RAL 地址 vs RTL 地址一致**: 从 spec 提取地址列表，对比 RTL 和 RAL
  ```bash
  python tools/check_regs_vs_rtl.py --spec spec.yml --rtl output/rtl/ --ral output/ral/
  ```
- [ ] **RAL 位域 vs RTL 位域一致**: 每个字段的位范围相同
- [ ] **RAL 复位值 vs RTL 复位值一致**: 每个寄存器复位值相同
- [ ] **RAL access 类型 vs RTL access 类型一致**: RW/RO/W1C 等

### 签收标准

| 一致性项目 | 标准 |
|-----------|:----:|
| 地址偏移 | 100% 匹配 |
| 字段位宽 | 100% 匹配 |
| 复位值 | 100% 匹配 |
| 访问类型 | 100% 匹配 |

---

## OT-S5: 功能覆盖度逐特征分组 [COMMON]

OpenTitan 将覆盖度按特征分组，每个 feature 独立达标。

### 检查项

- [ ] **每特征覆盖组**: 每个 spec feature 映射到独立的 covergroup
- [ ] **每特征目标 ≥90%**: 每个 feature 的覆盖度 ≥90%
- [ ] **交叉覆盖 (cross coverage)**: 协议相关特征的交叉覆盖
- [ ] **FSM 状态覆盖**: 每个 FSM 状态至少被访问一次
- [ ] **FSM 转移覆盖**: 每个状态转移至少被触发一次
- [ ] **中断覆盖**: 每个中断源从置位到输出的完整路径

### 覆盖度报告模板

```
Feature Coverage Report
────────────────────────────────────────
Feature              Goal    Measured    Status
ctrl_reg RW          ≥90%     100%       ✅ PASS
config_reg RW        ≥90%     100%       ✅ PASS
SPI write xfer       ≥90%      80%       ⚠️ LOW
SPI read xfer        ≥90%       0%       ❌ FAIL
SPI loopback         ≥90%       0%       ❌ FAIL
Interrupt path       ≥90%      50%       ⚠️ LOW
```

### 命令
```bash
# 功能覆盖度报告
python coverage_check.py --spec spec.yml --vcd results/*.vcd
```

---

## OT-S6: 故障注入 (Fault Injection) [COMMON]

OpenTitan 验证错误路径：协议错误、超时、数据损坏。

### 检查项

- [ ] **PSLVERR 测试**: 读/写保留地址，验证 pslverr 置位
- [ ] **TX FIFO 下溢**: FIFO 空时读取，验证 underflow 标志
- [ ] **RX FIFO 上溢**: FIFO 满时继续写，验证 overflow 标志
- [ ] **协议错误**: SPI 模式下 CS 中途释放 → 状态恢复
- [ ] **中断超时**: 中断等待超时后系统恢复
- [ ] **仲裁丢失**: 多主机仲裁失败场景 (I2C multi-master)

### 命令
```bash
# 故障注入测试
python run_test_generator.py --spec spec.yml --error-inject --out output/
```

---

## OT-S7: X-Propagation Formal 检查 [COMMON]

OpenTitan 运行正式 X 传播分析确保无 X 影响功能。

### 检查项

- [ ] **X 初始化仿真**: 运行 `+vcs+initreg+random` 或等价选项
- [ ] **X 传播路径**: 数据路径上的 X 不会传播到控制寄存器
- [ ] **CDC X 容忍**: 同步器的 2-flop 防止 X 传播
- [ ] **复位顺序 X**: 异步复位释放时无比 X 问题
- [ ] **FSM X 恢复**: FSM 从 X 状态能回到有效状态（兜底 default）

### 命令
```bash
# X-prop 检查（iverilog 不支持 +vcs+initreg，使用形式验证）
sby -f xprop.sby
```

---

## OT-S8: 代码覆盖度合并 [COMMON]

OpenTitan 合并多轮运行的覆盖度数据用于签收。

### 检查项

- [ ] **多 VCD 合并**: `coverage_engine.py` 支持多个 `--vcd` 输入
- [ ] **每测试独立 VCD**: 每个种子每个测试生成单独 VCD
- [ ] **合并报告**: 合并后的覆盖度反映整体收敛状态
- [ ] **收敛迭代**: 最近 3 轮回归覆盖率提升 < 1%

### 命令
```bash
# 多 VCD 合并分析
python engines/coverage_engine.py \
  --vcd reg_test.vcd --vcd smoke_test.vcd \
  --clk clk_i --module dma \
  --report merged_coverage.json
```

---

## OT-S9: DV Plan 文档化 [COMMON]

OpenTitan 每 IP 有完整 DV 计划文档。

### DV Plan 必需章节

- [ ] **Scope**: 验证目标、不验证项 (exclusions)
- [ ] **Test List**: 所有测试用例及其描述
- [ ] **Coverage Plan**: 功能覆盖点定义
- [ ] **Testbench Architecture**: 环境结构图
- [ ] **Environment Configuration**: 参数化配置
- [ ] **Assumptions**: 验证假设（什么由设计保证）
- [ ] **Signed-off Checklist**: 签收标准
- [ ] **Bug List**: 已知 issue 追踪

### 命令
```bash
# DV 计划自动生成 (由 spec-analyzer 输出)
cat output/verification-plan.md

# 签收报告 (由 doc-gen 输出)
cat output/verification-close-report.md
```

---

## OT-S10: 签收 Tag 与 Release 管理 [COMMON]

OpenTitan 使用 git tag 和 CI 门禁确保可追溯性。

### 检查项

- [ ] **Git tag**: 验证签收后打 tag (`v<ip>_<date>_<version>`)
- [ ] **所有 artifact 归档**:
  - [ ] spec (YAML/IP-XACT)
  - [ ] 生成的 RTL
  - [ ] 仿真 log
  - [ ] VCD 波形
  - [ ] 覆盖度报告
  - [ ] Review 报告
  - [ ] DV 计划 / 签收报告
- [ ] **CI 门禁**: review → 自动运行 → coverage 检查 → 门禁通过

### 命令
```bash
# 签收后归档
git tag -a "spi_slave_v1.0_2026-05-19" -m "SPI Slave sign-off: 9/9 PASS, 65.7% cov"
```

---

## 缺口汇总 (OpenTitan vs Current) [COMMON]

| # | 实践 | Our Checklist | 优先级 |
|:-:|:-----|:-------------|:------:|
| S1 | CSR 自动测试签收 | ✅ 已有 `run_csr_test_gen.py`，需加签收标准 | 🔴 P0 |
| S2 | 多种子回归 ≥10 | ⚠️ 提及种子，无最小计数 | 🟡 P1 |
| S3 | Verilator Lint | ❌ 无 lint 阶段 | 🟡 P1 |
| S4 | UVM RAL 单源一致性 | ✅ 已有 `run_ral_gen.py`，需加一致性检查 | 🟡 P1 |
| S5 | 功能覆盖度逐特征 | ✅ 已有 Phase 2 特征映射，需加 per-feature 目标 | 🟡 P1 |
| S6 | 故障注入测试 | ⚠️ 有 error_test 但无系统化故障注入 | 🟡 P1 |
| S7 | X-Propagation Formal | ⚠️ S7 中提及 X-prop 但非正式检查 | 🟡 P1 |
| S8 | 代码覆盖度合并 | ❌ 仅单 VCD 分析 | 🟠 P2 |
| S9 | DV Plan 文档化 | ⚠️ 隐式存在，无显式文档标准 | 🟠 P2 |
| S10 | 签收 Tag 与 Release | ❌ 无 release 管理流程 | 🟠 P2 |
