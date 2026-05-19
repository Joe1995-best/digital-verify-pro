# 🧾 digital-verify-pro 技能清单

> 整理日期: 2026-05-19
> 共 12 个 Agent Skill + 6 个 Pro Engine + 6 个 UVM 模板 + 7 个 Pipeline Run 脚本

---

## 一、Agent Skills (pipeline/agent_skills/)

共 13 个，含 1 个编排器和 12 个功能技能。

### 1. digital-verify-pipeline — Pipeline 编排器
- **描述**: 主编排器，定义 10 阶段完整流水线（spec → RTL → UVM → SW → 签收）
- **类型**: 编排/skill 容器
- **依赖**: 所有其他 skills
- **流程**: Parse → Generate Design → Generate VIP → Document → SW Interface → CSR Test → Sim
- **核心设计**: 单一 spec.yml 源，多输出（RTL + UVM + C headers + 文档）
- **状态追踪**: `.pipeline_state.json` 支持断点续跑

### 2. spec-analyzer — Spec 解析 & 验证计划生成
- **阶段**: Phase 1 — 解析
- **输入**: `spec.yml` / `spec.md` / IP-XACT
- **输出**: `verification-plan.md`, `interface-list.yml`, `register-map.yml`, `test-scenarios.yml`
- **能力**: 协议识别、接口提取、寄存器映射、场景规划、FSM 分析、协议感知场景生成 (I2C/APB)
- **Run 脚本**: `pipeline/run_spec_analyzer.py` (28KB)

### 3. env-builder — UVM 环境骨架生成
- **阶段**: Phase 2 — VIP 生成
- **输入**: verification-plan, interface-list, register-map
- **输出** (到 `rtl/verification/env/`):
  - `tb_top.sv` — testbench 顶层
  - `interfaces/<iface>_if.sv` — 各协议接口
  - `agents/<iface>_agent.sv` — UVM agent
  - `agents/<iface>_driver.sv` — 协议 driver
  - `agents/<iface>_monitor.sv` — 协议 monitor
  - `env_pkg.sv` — UVM 包
- **模板**: `templates/uvm-env/`
- **Run 脚本**: `pipeline/run_env_builder.py` (12KB)

### 4. test-generator — UVM 测试序列生成
- **阶段**: Phase 2 — VIP 生成
- **输入**: test-scenarios, interface-list
- **输出** (到 `rtl/verification/env/sequences/`):
  - `<test>_seq.sv` — 每个场景的序列类
  - `stress_seq.sv`, `error_seq.sv`, `reg_access_seq.sv`, `interrupt_seq.sv`
- **模板**: `templates/test-sequence/`
- **Run 脚本**: `pipeline/run_test_generator.py` (49KB)

### 5. assertion-gen — SVA 断言生成
- **阶段**: Phase 2 — VIP 生成
- **输入**: interface-list, spec.yml
- **输出** (到 `rtl/verification/env/assertions/`):
  - `<iface>_assert.sv` — 接口协议断言
  - `register_assert.sv` — 寄存器时序断言
  - `reset_assert.sv`, `clk_assert.sv`
- **模板**: `templates/assertion/`
- **支持协议**: APB, AHB, AXI, I2C, SPI, UART, 用户自定义
- **Run 脚本**: `pipeline/run_assertion_gen.py` (1.8KB)

### 6. coverage-plan — 功能覆盖率组生成
- **阶段**: Phase 2 — VIP 生成
- **输入**: verification-plan, test-scenarios
- **输出** (到 `rtl/verification/env/coverage/`):
  - `cov_groups.sv` — 总 covergroup 定义
  - `cov_iface.sv` — 接口覆盖
  - `cov_reg.sv` — 寄存器覆盖
  - `cov_cross.sv` — 交叉覆盖
- **覆盖类型**: 接口协议覆盖、寄存器覆盖、FSM 状态覆盖、交叉覆盖、功能缺口覆盖
- **Run 脚本**: `pipeline/run_coverage_plan.py` (1.7KB)

### 7. regmodel-gen — UVM 寄存器模型 (RAL) 生成
- **阶段**: Phase 3 — RAL 生成
- **输入**: register-map, interface-list
- **输出** (到 `rtl/verification/env/regmodel/`):
  - `<module>_reg_block.sv` — 顶层 register block
  - `reg/<reg_name>_reg.sv` — 每个寄存器类
- **模板**: `templates/regmodel/`
- **Run 脚本**: `pipeline/run_ral_gen.py` (13KB)

### 8. scoreboard-gen — Scoreboard & Checker 生成
- **阶段**: Phase 2 — VIP 生成
- **输入**: verification-plan, interface-list, register-map
- **输出** (到 `rtl/verification/env/scoreboard/`):
  - `sb.sv` — 主 scoreboard (TLM analysis ports)
  - `sb_compare.sv` — 数据比较逻辑
  - `sb_predictor.sv` — 预测逻辑
- **架构**: UVM Scoreboard with predictor + comparator + coverage
- **模板**: `templates/scoreboard/`
- **Run 脚本**: `pipeline/run_scoreboard_gen.py` (1.5KB)

### 9. tb-compiler — 编译脚本生成
- **阶段**: Phase 4 — 编译
- **输入**: 生成的 UVM env + DUT RTL
- **输出**: `Makefile` / `CMakeLists.txt` / TCL 脚本
- **支持工具**: VCS, Xcelium, Questa, Verilator, Icarus iverilog
- **Run 脚本**: — (由 pro_verify.py 集成)

### 10. sim-runner — 仿真运行器
- **阶段**: Phase 5 — 仿真
- **输入**: simv/可执行文件, test list, seeds
- **支持**: 多种子回归、日志采集、pass/fail 判定、波形追溯
- **Run 脚本**: `pipeline/run_sim.py` (20KB)

### 11. waveform-analyzer — 波形 & 日志分析
- **阶段**: Phase 6 — 后处理
- **输入**: 仿真日志, VCD 波形, 覆盖率数据库
- **能力**:
  - 日志分析 (UVM_ERROR/UVM_FATAL 提取, pass/fail 统计)
  - 覆盖率分析 (covergroup 百分比、toggle 分析)
  - 波形分析 (VCD 到 FST 转换、波形可视化指导)
  - 回归分析 (pass/fail 矩阵、失败复现)
- **Run 脚本**: — (由 coverage_engine 承接)

### 12. doc-gen — 验证文档生成
- **阶段**: Phase 10 — 文档
- **输入**: 所有 pipeline 产出
- **输出**:
  - `verification-close-report.md` — 签收报告
  - `test-specification.md` — 测试规范
  - `coverage-analysis.md` — 覆盖率分析
  - `bug-list.md` — 已发现 bug
  - `regression-summary.md` — 回归矩阵
- **Run 脚本**: `pipeline/run_doc_gen.py` (3.7KB)

### 13. review — AI 交叉审查
- **阶段**: 可选 — 代码审查
- **输入**: 所有生成代码 + `reviewers.yml`
- **默认审查模型**: GPT-4o (主审), Claude (副审), Kimi/K2 (协议专家)
- **审查清单**: SV/UVM 正确性、测试完整性、协议合规
- **Run 脚本**: — (AI agent 直接调用)

---

## 二、Pro Engines (engines/ )

共 5 个 + 1 个 feature_decomposer（共享组件）

### 1. plan_generator.py — 验证计划生成器 (66KB)
- **定位**: 深度 RTL 分析引擎，替代 spec-analyzer 的轻量模式
- **能力**: DeepRTL 分析 (FSM 提取、编码检测、data path 分析)、差异化测试生成、复杂度评分
- **适用场景**: 已有 RTL 无完整 spec

### 2. coverage_engine.py — 覆盖率引擎 (45KB)
- **定位**: VCD 解析 + toggle 覆盖率分析
- **能力**: 纯 Python VCD 解析器、全信号逐 bit toggle、分级活跃度 (NONE-LOW-MED-HIGH-VHIGH)、覆盖缺口检测+排序、0 stuck 证明
- **亮点**: 不依赖 vdump/gcov，纯 Python 实现

### 3. formal_check_gen.py — 形式验证生成器 (14KB)
- **定位**: Formal property + sby 集成
- **能力**: 正式属性生成、SymbiYosys (sby) 脚本生成、bounded/unbounded proof
- **已验证**: dual_port_stack 形式验证全过

### 4. regression_manager.py — 回归管理器 (9KB)
- **定位**: 回归测试编排
- **能力**: 测试分组、并行调度、结果汇总

### 5. dashboard_gen.py — Dashboard 生成器 (13KB)
- **定位**: HTML dashboard 报告
- **能力**: 从回归结果生成可视化 HTML 报告

### 6. feature_decomposer.py — 功能分解器 (30KB)
- **定位**: 共享组件 — 功能点分解
- **能力**: 从 spec 分解功能点、建立 feature-to-test 映射矩阵

---

## 三、Pipeline Run 脚本 (pipeline/ )

| 脚本 | 大小 | 对应 Skill | 描述 |
|------|:----:|:----------:|------|
| `run_spec_analyzer.py` | 28KB | spec-analyzer | v2: 协议感知场景 + 寄存器增强 + stress 场景 |
| `run_env_builder.py` | 12KB | env-builder | UVM env 骨架生成 |
| `run_test_generator.py` | 49KB | test-generator | 差异化测试序列生成 |
| `run_assertion_gen.py` | 1.8KB | assertion-gen | SVA 断言生成 |
| `run_coverage_plan.py` | 1.7KB | coverage-plan | 覆盖率计划 |
| `run_ral_gen.py` | 13KB | regmodel-gen | UVM RAL 生成 |
| `run_scoreboard_gen.py` | 1.5KB | scoreboard-gen | Scoreboard 生成 |
| `run_sim.py` | 20KB | sim-runner | 仿真运行 |
| `run_doc_gen.py` | 3.7KB | doc-gen | 文档生成 |
| `run_formal.py` | 27KB | (形式验证) | 形式验证 + sby |
| `run_rtl_gen.py` | 48KB | (RTL 生成) | spec → 可综合 RTL |
| `run_csr_test_gen.py` | 6KB | (CSR 测试) | CSR 复位/RW 自动测试 |
| `run_sw_header_gen.py` | 6KB | (SW header) | C 寄存器头文件生成 |
| `run_coverage_closure.py` | 5KB | (覆盖闭合) | 覆盖度收敛分析 |
| `coverage_converge.py` | 13KB | (收敛流水线) | 覆盖度收敛流水线 |
| `render_verification_plan.py` | 9KB | (计划渲染) | 验证计划渲染 |
| `validators.py` | 26KB | (验证器) | spec/RTL/env 验证器 |
| `template_engine.py` | 16KB | (模板引擎) | 通用模板引擎 |
| `fsm_templates.py` | 39KB | (FSM 模板) | FSM 控制器模板引擎 |

---

## 四、UVM 模板 (templates/ )

| 模板目录 | 描述 |
|---------|------|
| `uvm-env/` | UVM env 模板 (tb_top, agents, interfaces, pkg) |
| `assertion/` | SVA 断言模板 |
| `covergroup/` | 覆盖率组模板 |
| `regmodel/` | UVM RAL 模型模板 |
| `scoreboard/` | Scoreboard 模板 |
| `test-sequence/` | 测试序列模板 |

---

## 五、P0（计划中/缺失项，相对 IC Agent Hub 对标）

| 缺失 | 描述 | 优先级 |
|------|------|:------:|
| 质量管线 | 自动格式检查+安全扫描+依赖验证+运行时基线 | 🔴 P0 |
| 安全扫描器 | SV 静态代码分析、X 检测、综合风格检查 | 🔴 P0 |
| 依赖检查 | 声明依赖 vs 实际依赖交叉验证 | 🟡 P1 |
| License 合规 | 自动检测 SV/Python 文件 License 头 | 🟡 P1 |
| 跨 session 覆盖度合并 | 多轮仿真积累覆盖率数据 | 🟡 P1 |
| 上行适配脚本 | `export_skill.py` → 打包成 IC Agent Hub 兼容格式 | 🟢 P2 |
| 多语言文档 | 英文版 SKILL.md | 🟢 P2 |
