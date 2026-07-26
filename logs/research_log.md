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

---

## 跨领域验证：History, Law, Philosophy

### 实验配置

- 同 SearchQA adapter + gated slow update
- 初始 skill: SearchQA 通用初始 skill
- train_size=0 (自动匹配数据集大小)

### 结果

| | History | Law | Philosophy |
|------|:--:|:--:|:--:|
| 数据量 | train=228, val=57 | train=660, val=165 | train=299, val=75 |
| 基线 | ~61% | **43.0%** | ~63% |
| 峰值 | **68.4%** | **45.5%** | **72.0%** |
| Accept 数 | 3 | 3 | 4 |
| 提升 | +7% | +2.5% | +9% |

### 发现

1. **SkillOpt 框架在三个新领域均有效** — 全部正向提升
2. **Law 基线最低 (43%)**——这和 SearchQA 的 42% 非常接近，是"甜区间"数据集
3. **Philosophy 和 History 均在 60-70% 区间**——有提升但空间有限
4. **和数学不同**：这三个领域和 SearchQA 同属"文本理解"任务，SearchQA adapter 模板不会造成 +63% 的偏差

---

## 表格操作验证：SpreadsheetBench

### 实验配置

- qwen-flash 生成 Python + openpyxl 代码
- 本地 subprocess 执行
- 对比 gold xlsx 按单元格逐格评分（分档评分）
- 50 题 baseline

### 评分标准

| 分数 | 条件 |
|:--:|------|
| 1.0 | 完美匹配 (≥99%) |
| 0.5 | 极小差异 (≥90%) |
| 0.25 | 显著差异 (≥70%) |
| 0.1 | 大差异 (≥40%) |
| 0 | 执行失败或完全错误 |

### 50 题结果

| 指标 | 值 |
|------|:--:|
| Mean hard | **0.379** |
| Mean soft | 0.522 |
| 完美 (1.0) | 16/50 = 32% |
| 极小差异 (0.5) | 8/50 = 16% |
| 显著差异 (0.25) | 5/50 = 10% |
| 大差异 (0.1) | 2/50 = 4% |
| 执行失败 (0) | 19/50 = 38% |

### 发现

1. **qwen-flash 能生成可执行的表格操作代码** — 62% 的题至少产出有效 xlsx
2. **32% 完美率**——和 SearchQA 基线 (42%) 接近，说明有优化空间
3. **执行失败主要集中在复杂任务**（多 sheet 操作、条件格式、大文件超时）
4. **需接入 SkillOpt 训练循环**——deepseek 分析失败代码模式 → 优化规则