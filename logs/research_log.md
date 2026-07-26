# 数学推理能力研究日志

> 基于 SkillOpt 框架，研究 qwen-flash 在 MMLU-Pro Math 上的 skill 优化

## 研究背景

- 前期在 SearchQA 上验证了 SkillOpt + gated slow update 的有效性（test 0.7386）
- 现探索同一框架在数学推理任务上的表现
- 目标：验证原子化规则在数学领域能否通过 SkillOpt 实现 skill 自演化

## 实验环境

- Target: qwen-flash (DashScope)
- Optimizer: deepseek-v4-flash (DeepSeek)
- 数据集: MMLU-Pro Math (1351 题, 10 选 1)
- 数据划分: train=800, val=200, test=351
- 初始 skill: 数学解题通用 skill（179 字符）

## 基线测试

- 无 skill baseline (直接 prompt): 26%
- SkillOpt 训练管道内 baseline (SearchQA adapter 包装): **89.0%**
- 管道包装增益: +63%（SearchQA 的 prompt 模板大幅提升了数学正确率）
- 注意：这和 SearchQA 不同——管道本身的格式指令贡献了大量增益，训练可能提升空间有限

## 训练监控

| Step | 动作 | val | 说明 |
|------|------|:--:|------|
| 基线 | — | 89.0% | SearchQA adapter 模板包装后基线 |
| 1 | accept_new_best | 91.0% | +2% |
| 2 | accept_new_best | **91.5%** | +0.5% |
| 3 | reject | 91.5% | |
| 4 | reject | 91.5% | |
| 5 | reject | 91.5% | |
| 6 | reject | 92.0% | |
| 7 | reject | 92.0% | 续跑 |
| 8 | reject | 92.0% | |
| | | | |

## 续跑 & 截停

- API 充值后从 Step 7 恢复
- 跑至 28/80 步，92.5% 后连续 13 次 reject，已截停

## 最终结论

### 训练结果

| 指标 | 值 |
|------|:--:|
| 基线 (SearchQA adapter) | 89.0% |
| 最高 val | **92.5%** (Step 15) |
| Accept | 3/28 |
| Reject | 18/28 |
| 最终 | 92.5%，13 次连续 reject |

### 关键发现

1. **SkillOpt 训练框架在数学上有效**：28 步从 89.0%→92.5%（+3.5%），但天花板很快来临
2. **SearchQA adapter 是双刃剑**：其 prompt 模板带来 +63% 基线增益（26%→89%），但也会大幅度压缩优化空间
3. **和 SearchQA 相同模式**：前几步快速爬升后连续 reject → 框架本身有效，瓶颈在于 (a) prompt 模板已接近该任务上限 和 (b) 数学解题策略无法通过增加"规则段落"持续提升
4. **若要真正研究数学 skill 优化**：需要数学专用 adapter（去掉 SearchQA 的"从文档提取答案""验证上下文"等干扰指令），让基线接近真实水平（~26%），才有充足的优化空间

### SearchQA vs MMLU-Pro Math 对比

| | SearchQA | MMLU-Pro Math |
|------|:--:|:--:|
| 数据量 | train=400, val=200 | train=800, val=200 |
| 基线 | 41.7% | 89.0% (含+63%模板增益) |
| 峰值 | 73.5% | 92.5% |
| 提升 | +31.8% | +3.5% |
| Accept 数 | 4-6 | 3 |
| Gate 行为 | 前几步 accept，后期 reject | 同 |
| 模板效果 | 模板帮助大 | 模板把基线抬太高→空间不够 |