# 数字验证技能开发规范 v1.0

> 适用于 digital-verify-pro 所有 standalone skills
> 生效日期: 2026-05-20

---

## 1. 行为统一规则

### 1.1 日志
- 使用 `skill_common.get_logger(__name__)`，不要直接 `print()` 或 `logging.basicConfig()`
- 日志输出到 **stderr**（stdout 保留给结构化数据输出）
- 日志级别: `debug` → `info` → `warn` → `error`
- 格式: `[LEVEL] module_name: message`

### 1.2 退出码
所有技能退出码必须遵循 `skill_common.ExitCode` 定义：

| 码 | 常量 | 含义 |
|:--:|------|------|
| 0 | SUCCESS | 成功 |
| 1 | INPUT_ERROR | 输入参数错误 |
| 2 | SPEC_ERROR | spec YAML 解析失败 |
| 3 | RUNTIME_ERROR | 运行时异常 |
| 4 | VALIDATION_ERROR | 输出验证失败 |
| 5 | DEPENDENCY_ERROR | 缺少依赖（工具/库） |
| 6 | TIMEOUT | 执行超时 |
| 7 | CONFIG_ERROR | 配置文件错误 |
| 99 | INTERNAL_ERROR | 未知 bug |

### 1.3 输出结构
每次运行必须生成 `result.json`（路径可配置），格式：

```json
{
  "status": "pass|fail|error|skip",
  "timestamp": "2026-05-20T07:00:00",
  "module": "<skill-name>",
  "summary": "Human readable summary",
  "metrics": { ... },
  "outputs": { "file1": "path1", ... },
  "errors": [{"code": 3, "message": "..."}],
  "warnings": [{"message": "..."}]
}
```

- `result.json` 使用 `skill_common.write_result()` 生成

### 1.4 入口签名
每个技能的 `run.py` 必须:
```
run.py --spec <file> --out <dir> [--config <file>] [--log-level <level>] [--result <path>]
```
额外参数可以追加，但上述基础参数必须支持。

### 1.5 config.yaml 支持
技能若需要用户配置（如仿真器路径、超时时间），必须默认读取 `config.yaml`，使用 `skill_common.load_config()`。

---

## 2. 技能边界定义

### 2.1 技能职责矩阵

| 技能 | 职责 | 不做的 |
|------|------|--------|
| **spec-analyzer** | 解析 YAML spec，产出接口/寄存器/场景定义 | 不生成任何 RTL/SV 代码 |
| **plan-generator** | 从 RTL 源码分析产生验证计划 | 不解析 YAML spec |
| **rtl-gen** *(from pipeline)* | 从 spec 生成可综合 RTL | 不做仿真验证 |
| **env-builder** | 生成 UVM 环境骨架（agent/interface/tb_top） | 不生成测试序列或断言 |
| **test-generator** | 生成 UVM 测试序列 | 不搭建环境骨架 |
| **assertion-gen** | 生成 SVA 断言 | 不生成测试或环境 |
| **scoreboard-gen** | 生成 UVM scoreboard | 不生成环境其他部分 |
| **regmodel-gen** | 生成 UVM RAL 模型 | 不生成测试序列 |
| **coverage-plan** | 生成覆盖率组定义 | 不运行仿真或不分析结果 |
| **tb-compiler** | **只编译**：源文件 → 编译脚本 + 可执行文件 | **不运行仿真** |
| **sim-runner** | **只运行**：编译产物 → 运行测试 → 收集结果 | **不编译** |
| **waveform-analyzer** | 后处理：日志/VCD → 分析报告 | 不运行仿真 |
| **coverage-engine** | VCD toggle 覆盖度分析 | 不做功能覆盖率分析 |
| **formal-check** | 形式验证属性生成 + sby 执行 | 不替代动态仿真 |
| **doc-gen** | 文档聚合：收集所有产出写签收报告 | 不生成代码 |
| **dashboard-gen** | 可视化：数据 → HTML 面板 | 不生成验证内容 |
| **regression-manager** | 回归跟踪：历史记录 → 趋势 | 不运行回归 |
| **review** | RTL 代码审查 | 不修改代码 |
| **feature-decomposer** | 功能分解：spec → 测试点分解 | 不生成 UVM 代码 |
| **fsm-templates** | FSM RTL 模板生成 | 不做验证环境 |

### 2.2 tb-compiler vs sim-runner 边界明确

**tb-compiler 的职责上限是编译**：
- 输入: 源文件列表（RTL + UVM env + test sequences + assertions + scoreboard + coverage）
- 功能: 生成 compile scripts (Makefile/DO file)，可选执行编译生成 simv
- 输出: 编译脚本 + 编译日志 + simv（可选）
- 输出标记: `result.json` 中的 `outputs.simv` 指向编译产物

**sim-runner 的职责从编译产物之后开始**：
- 输入: simv 路径 + test list + seeds
- 功能: 运行 simv 各 test × seed，收集 pass/fail，提取 coverage 日志
- 输出: 仿真日志 + `sim_results.yml` + VCD dump（可选）
- 依赖 tb-compiler 先完成: `depends_on: [tb-compiler]`

如果 `sim-runner` 检测到 simv 不存在，**报错退出**（ExitCode.DEPENDENCY_ERROR），不尝试自己编译。

---

## 3. 契约文档要求

每个技能必须在根目录提供 2 个文档：

### 3.1 skill_spec.json
机器可读的接口契约，必须包含:
- `name`, `version`, `quality_score`, `description`
- `inputs`: 每个 CLI 参数的 JSON Schema
- `outputs`: result.json schema + 报告文件列表
- `depends_on`: 上游依赖技能列表
- `config`: config.yaml 中可配置参数
- `error_codes`: 错误码 + 修复指引
- `tags`: 分类标签
- `lifecycle`: 状态 (development/beta/stable/deprecated)

### 3.2 SKILL.md
人可读的完整文档，必须包含:

```
# <name> v<version>

## Overview
<段落描述，说明技能解决什么问题、不解决什么问题>

## Quick Start
<可复制的命令行示例>

## Inputs
<表格: 参数名 | 类型 | 必填 | 说明>

## Outputs
<表格: 输出文件 | 格式 | 说明>

## Dependencies
<Python / OS / 外部工具 / 内部库>

## Config
<config.yaml 可配置参数表格>

## Effort Levels
<lite / standard / intensive / exhaustive 四级>

## Upstream / Downstream
<依赖链关系>

## Validation
<已验证示例表格>

## Known Limitations
<已知限制或边界条件>
```

---

## 4. 自测规范

每个 `tests/` 目录必须包含:
- `test_minimal.py`: 以最少输入（空 spec 或最小 YAML）验证不崩溃
- `test_smoke.py`: 以标准输入（已验证的 spec）验证输出正确
- 用 `pytest` 框架，确保 `cd <skill> && python -m pytest tests/` 能通过

自测用例使用最小化输入（不依赖完整的 DUV），让 CI 可以在无仿真器环境下验证 skill 接口契约是否被破坏。

---

## 5. 技能生命周期

```
development → beta → stable → deprecated
   (开发中)   (可用)  (生产级)  (不再维护)
```

- **development**: 接口可能变化，不可依赖
- **beta**: 接口冻结，功能可测试
- **stable**: 生产级，100 分制 ≥ 75
- **deprecated**: 依旧可用但推荐迁移
