# report #014: MOAR — Multi-Objective Atomic Rule Selection 对照实验

> 日期：2026-07-27 | 分支：`main` | SearchQA 全量推理对照实验

---

## 一、方法

将固定 TF-IDF Top-5 检索升级为 NSGA-II 多目标进化算法：

Score(q,r) = α·R_rel + β·R_utility + γ·R_coverage − λ·R_redundancy − μ·R_cost

在 token 预算约束下，同时对相关性、历史效用、覆盖度、冗余度和成本进行 Pareto 优化。

### 实验设置

| 参数 | 值 |
|------|:--|
| 技能 | outputs/searchqa_rag/best_skill.md (13772 chars, 1 core + 8 dynamic) |
| 数据 | SearchQA test set (1400 items, valid_unseen) |
| 目标模型 | qwen-flash (DashScope) |
| Top-K | 5 |
| 字符预算 | 2000 characters（仅作用于检索的动态规则拼接部分） |
| NSGA-II 参数 | pop=30, gen=15 (smoke); pop=50, gen=30 (full) |
| 目标权重 | [0.4, 0.3, 0.2, 0.1] (relevance, utility, cost, redundancy) |

---

## 二、结果

### 全量对照实验（1400 条）

| 方法 | Accuracy | 动态规则字符数 | 完整系统 Prompt 字符数 | 规则数 | 构建时间 |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 62.79% | 0 | 513 | 0 | 0ms |
| TF-IDF Top-5 | 66.86% | ~1,405 | 1,918 | 1.0 | 1ms |
| **MOAR** | **69.07%** | ~1,599 | 2,112 | 1.7 | 347ms |

> 2,000-character 预算仅作用于检索得到的动态规则拼接部分。完整系统 Prompt 还包含 Core 规则（~513 chars）和系统提示模板，因此可超过 2,000 字符。

| 对比 | Δ Accuracy | 含义 |
|------|:--:|------|
| MOAR vs TF-IDF | **+2.21pp** | 多目标优化超越词法相关性 |
| MOAR vs Core Only | **+6.29pp** | 动态规则整体贡献 |
| TF-IDF vs Core Only | +4.07pp | 简单检索的收益 |

### 中间验证（500 条）

| 方法 | Accuracy |
|------|:--:|
| Core Only | 61.80% |
| TF-IDF Top-5 | 65.20% |
| **MOAR** | **69.20%** (+4.0pp vs TF-IDF) |

---

## 三、分析

### MOAR 的改进来源

1. **规则选择更多样**：MOAR 平均激活 1.7 条规则（TF-IDF 仅 1.0 条），因为反冗余目标鼓励选择互补规则
2. **字符预算利用更充分**：MOAR 在动态规则部分使用 ~1,599 字符（TF-IDF ~1,405），更接近 2,000 字符预算，但未突破
3. **NSGA-II 搜索有效**：Pareto 优化的 30 代足够探索二进制选择空间
4. **单次查询开销可接受**：347ms vs 1ms——在批量推理中可忽略

### 当前限制

1. 该 skill 仅有 8 条动态规则，NSGA-II 的搜索空间有限（2^8 = 256）
2. 效用追踪仅在本轮推理中累积（无跨运行持久化）
3. 权重为启发式设定（0.4/0.3/0.2/0.1），未经调优

---

## 四、结论

**MOAR 在 SearchQA 全量测试集上以 +2.21pp 超越 TF-IDF 基线。**

这是该项目对 MOAR 方法的首次实证验证。结果支持：
1. 多目标规则选择的可行性
2. NSGA-II 在离散组合优化中的有效性
3. 反冗余正则化促进规则多样性

### 与项目历史基线的关系

| 方法 | Test Accuracy |
|------|:--:|
| Full Skill（Phase 2-3 峰值） | 73.86% |
| MOAR with trained skill | 69.07% |
| TF-IDF Top-5 | 66.86% |

> MOAR 在 2000-character 字符预算约束下达到 full skill (~13k chars) 的 93.5% 性能。Full skill 使用 6.8× 的上下文但仅高出 4.8pp——这证实了预算约束下选择性检索的价值。
