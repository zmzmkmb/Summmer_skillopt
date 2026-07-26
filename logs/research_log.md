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

## ⚠️ 训练中断

- Step 6 后千问 API 欠费（DashScope Arrearage）
- 已完成 6/80 步，已确认框架有效（89%→91.5%）
- 需充值后继续

## 初步结论

1. SkillOpt 框架在数学上**有效**：6 步内从 89%→91.5%
2. SearchQA adapter 模板带来 +63% 基线增益（26%→89%），导致优化空间变小
3. 若用数学专用 adapter（不加 SearchQA 的文档查找/答案提取模板），基线会接近 26%，优化空间会更大
4. 待 API 恢复后建议：(a) 用数学专用 prompt 模板重跑，(b) 继续当前训练完成 80 步