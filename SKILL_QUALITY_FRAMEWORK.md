# 🔬 单 Skill 质量评估框架

> 适用于 digital-verify-pro 的 Agent Skills
> 对标 IC Agent Hub 的 5 步管线 + 芯片验证领域特有的质量要求

---

## 一、评分总览（100 分制）

| 维度 | 权重 | 满分 | 说明 |
|------|:----:|:----:|------|
| **Q1 功能完备性** | 25% | 25 | Skill 声称的能力是否真正实现 |
| **Q2 代码/文档质量** | 20% | 20 | 代码风格、文档完整性、可读性 |
| **Q3 安全与合规** | 20% | 20 | 安全扫描、依赖验证、License |
| **Q4 运行可靠性** | 20% | 20 | 实际运行是否稳定、edge case 处理 |
| **Q5 兼容性** | 15% | 15 | 跨工具/跨环境/跨版本适配 |

---

## 二、各维度详细评分标准

### Q1 — 功能完备性 (25 分)

| 评分项 | 分值 | 检查方法 | 说明 |
|--------|:----:|----------|------|
| **1.1 输入/输出声明完整** | 3 | 阅读 SKILL.md | inputs/outputs 表格中存在，格式清晰 |
| **1.2 核心功能实现度** | 10 | 运行实际测试 | 声称的每个功能点都能真实工作 |
| **1.3 异常/边界处理** | 4 | 注入特殊输入 | 空输入、格式错误、非法值时是否优雅降级 |
| **1.4 功能点覆盖率** | 5 | 对照 spec | 技能 scope 内的功能点覆盖百分比 |
| **1.5 输出可消费性** | 3 | 检查输出质量 | 生成代码是否可直接编译/文档是否可直接阅读 |

**评分示例**：

| Level | 得分 | 描述 |
|-------|:----:|------|
| 🥇 Excellent | 10/10 | 全部功能完美工作，有 regression 测试证明 |
| 🥈 Good | 7-9/10 | 主要功能工作，少量 edge cases 未覆盖 |
| 🥉 Fair | 4-6/10 | 基础功能可用但不够完善 |
| ❌ Poor | 0-3/10 | 功能未实现或不可用 |

### Q2 — 代码/文档质量 (20 分)

| 评分项 | 分值 | 检查方法 |
|--------|:----:|----------|
| **2.1 SKILL.md 完整性** | 4 | name/description/inputs/outputs/capabilities 齐全 |
| **2.2 代码注释率** | 3 | >20% 注释行 = 满分, 10-20% = 2, <10% = 1 |
| **2.3 代码风格一致** | 3 | 命名规范、缩进一致、无 magic number |
| **2.4 Run 脚本质量** | 4 | 命令行 argparse、错误处理、日志输出 |
| **2.5 示例/测试用例** | 3 | 有最小工作示例、有单元测试 |
| **2.6 版本/变更记录** | 3 | SKILL.md 有版本号、changelog |

### Q3 — 安全与合规 (20 分)

| 评分项 | 分值 | 检查方法 |
|--------|:----:|----------|
| **3.1 无高危代码模式** | 5 | 静态扫描：无 eval/exec/shell 注入/文件覆盖风险 |
| **3.2 依赖声明完整** | 4 | requirements.txt / 依赖列表完整，无隐式依赖 |
| **3.3 依赖 vs 实际一致性** | 4 | 声明的依赖 = 代码实际 import |
| **3.4 License 合规** | 3 | 每个文件有 License header，无 GPL 传染问题 |
| **3.5 文件操作安全性** | 3 | 写入路径受限、无目录遍历风险 |
| **3.6 敏感信息泄露** | 1 | 无硬编码 token/password/path |

### Q4 — 运行可靠性 (20 分)

| 评分项 | 分值 | 检查方法 |
|--------|:----:|----------|
| **4.1 基础运行通过率** | 5 | 3 次运行均成功 |
| **4.2 超时处理** | 3 | 长时间运行有 timeout，不会卡死 |
| **4.3 错误信息可读性** | 3 | 失败时有明确的错误信息和修复建议 |
| **4.4 幂等性** | 3 | 重复运行不产生副作用（不报错、不做重复操作） |
| **4.5 输入校验** | 3 | 对非法输入有校验和拒绝，不崩溃 |
| **4.6 清理机制** | 3 | 临时文件正确清理，不残留 |

### Q5 — 兼容性 (15 分)

| 评分项 | 分值 | 检查方法 |
|--------|:----:|----------|
| **5.1 Python 版本兼容** | 3 | 声明支持的 Python 版本，实际测试 |
| **5.2 操作系统兼容** | 3 | Win/Linux/Mac 至少 2 个平台通过 |
| **5.3 仿真器兼容** | 5 | iverilog + Questa + VCS 至少 2 个通过（验证类 skill） |
| **5.4 模板/格式兼容** | 2 | 输出格式标准化（YAML/MD/SV） |
| **5.5 前后 skill 接口兼容** | 2 | 输出格式与流水线中上下游 skill 匹配 |

---

## 三、质量等级标签

| 总分区间 | 等级 | 标签 | 说明 |
|:--------:|:----:|:----:|------|
| **90-100** | A+ | 🏆 **Certified** | 生产级，可上架市场 |
| **75-89** | A | ✅ **Approved** | 功能完整，少量改进点 |
| **60-74** | B | ⚠️ **Beta** | 可用但需完善，不建议生产使用 |
| **40-59** | C | 🔧 **In Development** | 开发中，核心功能可以但不够成熟 |
| **0-39** | D | ❌ **Unstable** | 不稳定或未完成 |

---

## 四、当前 Skills 评估示例

### spec-analyzer v2 (`run_spec_analyzer.py`)
```
Q1 功能完备性  ┃ 22/25  ┃ 协议感知场景生成、寄存器增强、stress 场景; 空输入处理可加强
Q2 代码/文档   ┃ 17/20  ┃ SKILL.md 完整, 代码注释良好; 缺少版本号
Q3 安全与合规   ┃ 18/20  ┃ 无高危模式; 依赖声明缺 requirements.txt
Q4 运行可靠性   ┃ 16/20  ┃ 幂等性好; 超时处理未覆盖
Q5 兼容性       ┃ 13/15  ┃ Python 3.14 + iverilog 已验证
───────────────────────────────────────────
Total: 86/100  →  ✅ Approved (A级)
```

### coverage_engine.py (VCDParser)
```
Q1 功能完备性  ┃ 24/25  ┃ 全信号 toggle, gap检测, 0 stuck证明
Q2 代码/文档   ┃ 18/20  ┃ 代码结构清晰; SKILL.md 未独立写
Q3 安全与合规   ┃ 19/20  ┃ 纯 Python 无外部依赖; 无高危
Q4 运行可靠性   ┃ 18/20  ┃ 多轮 i2c/dma 验证过; 大 VCD 性能待优化
Q5 兼容性       ┃ 14/15  ┃ 跨平台
───────────────────────────────────────────
Total: 93/100  →  🏆 Certified (A+级)
```

### test-generator (`run_test_generator.py`)
```
Q1 功能完备性  ┃ 20/25  ┃ 差异化测试生成良好; 边界场景可补
Q2 代码/文档   ┃ 16/20  ┃ 大量注释; SKILL.md 完整
Q3 安全与合规   ┃ 17/20  ┃ 模板注入无明显风险; 缺依赖声明
Q4 运行可靠性   ┃ 15/20  ┃ I2C 验证过; 超时/清理待完善
Q5 兼容性       ┃ 12/15  ┃ 输出标准 SV; 上下游已验证
───────────────────────────────────────────
Total: 80/100  →  ✅ Approved (A级)
```

---

## 五、质量检查自动化工具

对应 `tools/quality_pipeline.py` 应该做什么：

```python
# 伪代码：一次检查一个 skill
class SkillQualityChecker:
    def __init__(self, skill_dir: Path):
        self.skill_dir = skill_dir
        self.scores = {}
        self.report = {}

    def check_functional(self) -> dict:      # Q1
        # 1. 解析 SKILL.md 提取 inputs/outputs
        # 2. 检查所有输出文件是否存在
        # 3. 运行最小测试验证功能
        pass

    def check_code_quality(self) -> dict:     # Q2
        # 1. 行数/注释率
        # 2. 命名规范 (snake_case)
        # 3. 无 magic number
        # 4. SKILL.md 字段完整性
        pass

    def check_security(self) -> dict:         # Q3
        # 1. 静态扫描 (grep for eval/exec/os.system/subprocess)
        # 2. 读 requirements.txt vs 实际 import
        # 3. License 头部检查
        pass

    def check_reliability(self) -> dict:      # Q4
        # 1. 运行 3 次统计通过率
        # 2. 输入各种 edge cases
        # 3. 检查清理
        pass

    def check_compatibility(self) -> dict:    # Q5
        # 1. 检查 .python-version
        # 2. 检查输出格式与上下游匹配
        pass

    def run_all(self) -> SkillQualityReport:
        # 汇总 100 分制评分
        pass
```

---

## 六、质量报告的交付格式

### JSON 格式 (机器可读)
```json
{
  "skill": "spec-analyzer",
  "version": "2.0",
  "score": {
    "total": 86,
    "functional": 22,
    "code_docs": 17,
    "security": 18,
    "reliability": 16,
    "compatibility": 13
  },
  "grade": "A",
  "label": "Approved",
  "checked_at": "2026-05-19T08:00:00+08:00",
  "checks": {
    "has_skilmd": true,
    "has_requirements": false,
    "security_issues": 0,
    "test_pass_rate": 1.0
  },
  "recommendations": [
    "添加 requirements.txt",
    "补充超时处理",
    "添加 SKILL.md 版本号"
  ]
}
```

### Markdown 格式 (人类可读)
```markdown
## 🧪 spec-analyzer — Quality Report

| 维度 | 得分 | 评级 |
|------|:----:|:----:|
| 功能完备性 | 22/25 | 🥇 |
| 代码/文档 | 17/20 | 🥈 |
| 安全与合规 | 18/20 | 🥇 |
| 运行可靠性 | 16/20 | 🥈 |
| 兼容性 | 13/15 | 🥇 |
| **总分** | **86/100** | **✅ A级** |

### 改进建议
1. 添加 requirements.txt
2. 补充超时处理
3. 添加 SKILL.md 版本号
```
