# IP 级验证改进路线图

> 记录于 2026-05-20，按优先级分层

## P0 — 立即补充（IP 签收硬性门槛）

### 1. Lint / 可综合性检查
- 现状: validators.py 只做语法检查，无 lint 门
- 目标: RTL 生成后自动做 lint + 可综合性检查
- 做法: pipeline/validators.py 增加 verilator --lint-only / yosys synth
- 验收: lint warning > 0 时阶段状态为 WARNING

### 2. CDC 检查（多时钟域 IP）
- 现状: 只分析单时钟域 toggle
- 目标: 静态检测异步信号路径
- 做法: 新增 engines/cdc_checker.py
- 验收: 0 未同步路径时 PASS

## P1 — 测试质量提升

### 3. Integration 测试验证输出内容
- 现状: 只验证 result.json 存在，不验证字段值
- 目标: 验证 metrics 数值合理
- 验收: 修改计算逻辑后测试能 catch

### 4. Unit 测试接入真实引擎
- 现状: test_stuck_signal 手动构造数据
- 目标: 全部调用引擎类方法
- 验收: 删除所有手动赋值断言

### 5. Fixtures 增加边界场景
- 现状: 只有 minimal_spec.yml + minimal.vcd
- 目标: empty.vcd / corrupt.vcd / multi_clock_spec.yml / max_reg_spec.yml
- 验收: 每种 fixture 都有对应测试函数

## P2 — 流程自动化

### 6. 增量编译缓存
### 7. Spec-RTL 一致性自动追踪
### 8. 版本基线与覆盖度对比

## P3 — 功能增强

### 9. 约束随机生成（Constraint Random）
### 10. 寄存器字段级覆盖度
### 11. 轻量故障注入

## P4 — 工程化

### 12. 全部 skill 的 Python 测试覆盖
### 13. CI 契约兼容性检查
### 14. 性能基准回归

---

## 一句话建议

快速验证原型: P0(Lint门) + P1(测试深度) = 从可用到可信
交付级IP验证: 再加 P3(约束随机 + 字段级覆盖度) = 对标 OpenTitan DV
