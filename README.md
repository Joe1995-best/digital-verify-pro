# digital-verify-pro

**专业级数字芯片验证框架** — Spec-YAML 驱动，全自动 UVM 流水线：从 spec 到签收报告，12 阶段全自动生成。

纯 SystemVerilog + iverilog 兼容，不需要商业 EDA 工具。

---

## 快速开始

```bash
# 安装依赖
pip install pyyaml jinja2

# 一键运行 I2C 全流水线 (12 阶段, ~3s)
python pro_verify.py --pipeline i2c_spec.yml

# 只跑前 3 阶段看效果
python pro_verify.py --pipeline i2c_spec.yml --phases spec-analyzer,rtl-gen,ral-gen

# 查看所有流水线阶段
python pro_verify.py --list-pipeline-phases
```

## 已验证 IP

| IP | Pipeline | 阶段 | 状态 |
|:---|:--------:|:----:|:----:|
| I2C Controller | 12 阶段全自动 | 2.7s | ✅ PASS |
| SPI Slave | 12 阶段全自动 | 2.7s | ✅ PASS |
| UART | 12 阶段全自动 | 2.7s | ✅ PASS |
| OT DMA v4 | 独立仿真 | 12/12 测试 | ✅ 93.8% toggle |
| ALU4 | 独立仿真 | 66/66 测试 | ✅ PASS |
| Dual Port Stack | 形式验证 | — | ✅ 通过 |

---

## Pipeline 全景

```
spec.yml ──→ spec-analyzer ──→ rtl-gen ──→ ral-gen ──→ env-builder ──→
  (输入)     (解析/场景生成)    (RTL生成)   (UVM RAL)   (UVM骨架)
  
──→ test-generator ──→ assertion-gen ──→ scoreboard-gen ──→ tb-gen ──→
   (测试序列)          (SVA断言)          (记分板)          (TB生成)

──→ coverage-plan ──→ doc-gen ──→ sw-header-gen ──→ formal-check
   (覆盖计划)          (签收报告)    (C头文件)          (形式验证)
```

**中间文件皆可审可改：**
```
ip_spec.yml → port_map.yml + reg_map.yml + test_plan.yml → regression_list.yml
```

每个阶段结束后生成 YAML 中间文件，可人工审查修改后 `--resume` 续跑。

---

## 项目架构

```
digital-verify-pro/
├── pipeline/               # 12 阶段流水线编排
│   ├── run_*.py            # 各阶段执行脚本
│   ├── tb_gen.py           # 测试生成器 (feature → UVM case)
│   ├── validators.py       # 阶段间契约验证 (含 Lint 门/CDX 检查)
│   ├── template_engine.py  # Jinja2 模板引擎
│   └── templates/          # UVM/FSM 模板
│
├── verify/                 # 仿真运行与回归管理
│   ├── run_sim.py          # 统一仿真入口 (--case / --regression)
│   ├── build_iverilog.py   # 编译配置 (独立可执行)
│   ├── compare_runs.py     # 回归结果对比 (--latest / --baseline)
│   ├── regression_list.py  # 回归清单 (auto + manual)
│   ├── cases/              # 单条 case 定义
│   │   └── manual/         # 手动追加 case (tb_gen 不覆盖)
│   ├── port_map.yml        # 端口连接映射表
│   ├── reg_map.yml         # 寄存器映射表
│   └── test_plan.yml       # 测试点分解表
│
├── standalone-skills/      # 19 个独立化技能包
│   ├── coverage-engine/    # VCD toggle 覆盖率分析
│   ├── spec-analyzer/      # Spec 解析与验证规划
│   ├── env-builder/        # UVM 环境骨架生成
│   ├── test-generator/     # UVM 测试序列生成
│   ├── assertion-gen/      # SVA 断言生成
│   ├── scoreboard-gen/     # UVM Scoreboard 生成
│   ├── regmodel-gen/       # UVM RAL 模型生成
│   ├── coverage-plan/      # 功能覆盖组生成
│   ├── doc-gen/            # 验证签收文档生成
│   ├── dashboard-gen/      # HTML 仪表盘
│   ├── formal-check/       # 形式验证
│   ├── fsm-templates/      # FSM RTL 模板
│   ├── plan-generator/     # RTL 反向分析验证计划
│   ├── feature-decomposer/ # 功能分解 → 测试点
│   ├── regression-manager/ # 回归历史追踪
│   ├── review/             # RTL 代码审查
│   ├── sim-runner/         # 仿真执行
│   ├── tb-compiler/        # 编译 (不运行)
│   ├── waveform-analyzer/  # 后处理分析
│   └── skill_common/       # 共享库 (日志/退出码/结果输出/契约验证)
│
├── engines/                # 专业引擎
│   ├── coverage_engine.py  # VCD toggle 覆盖度
│   ├── cdc_checker.py      # 跨时钟域分析
│   ├── compile_cache.py    # 增量编译缓存
│   ├── spec_rtl_tracker.py # Spec-RTL 一致性
│   ├── crv_generator.py    # 约束随机生成
│   ├── field_coverage.py   # 字段级覆盖度
│   ├── fault_injector.py   # 故障注入
│   ├── contract_checker.py # CI 契约兼容性
│   └── plan_generator.py / formal_check_gen.py / ...
│
├── benchmark/              # 性能基准测试
│   └── vcd_parse_benchmark.py
│
├── checklists/             # 验证签收清单 (OpenTitan 对齐)
├── examples/               # 示例 testbench
├── wiki/                   # 知识库
└── tools/                  # 质量评估工具
    └── quality_pipeline.py # 5 维度 100 分制 skill 质量评估
```

---

## 使用场景

### 1. 全自动 IP 验证
```bash
python pro_verify.py --pipeline i2c_spec.yml
# 12 阶段全自动，产出 RTL + UVM env + 测试 + 断言 + 覆盖率 + 签收报告
```

### 2. 回归测试
```bash
# 单 case
python verify/run_sim.py --build build_iverilog --case ctrl_rw

# 全量回归
python verify/run_sim.py --build build_iverilog --regression

# 对比两轮回归
python verify/compare_runs.py --latest
```

### 3. 手动加一条 case
```python
# verify/cases/manual/my_test.py
NAME = "my_test"
BASE_SEQ = "i2c_base_seq"
PRIORITY = "p1"
DESCRIPTION = "手动添加的测试"
PLUSARGS = ["+UVM_TESTNAME=my_test", "+MY_PARAM=1"]
```

在 `regression_list.py` 的 `manual_cases` 加一行引用即可。

### 4. 评估 skill 质量
```bash
python tools/quality_pipeline.py standalone-skills/coverage-engine/
# 输出: Q1 功能/ Q2 代码/ Q3 安全/ Q4 运行/ Q5 兼容 → 总分/100
```

---

## 设计哲学

**管道固定，填充可变** — 流程本身不绑定 AI 还是人。中间文件格式对就行，来源不管。

| 角色 | 职责 |
|:----|------|
| **顶层 Owner** | 维护管道流程、审查中间文件、管理回归清单 |
| **IP Owner** | 写 spec.yml、填 port_map.yml、定义 feature、补充手动 case |

---

## 依赖

- **Python**: >= 3.10
- **iverilog**: >= 11.0 (ICARUS Verilog, 用于仿真)
- **pyyaml**, **jinja2** (RTL/UVM 模板生成)
- **sby** (形式验证, 可选)
- **verilator** (Lint 门, 可选)

## License

MIT
