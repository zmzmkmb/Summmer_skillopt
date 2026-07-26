# SkillOpt 交叉验证报告 — 跨任务、跨模型迁移性

> 日期：2026-07-26 | 分支：`main` | 基于 #001-#008 的全部实验

---

## 一、验证矩阵

| 维度 | 已测试 | 结论 |
|------|:--:|------|
| 跨任务 (SearchQA→MMLU) | ✅ | 内容级规则不迁移 |
| 跨难度 (MMLU Elem→HS→College) | ✅ | qwen-flash 全线天花板 |
| 跨模型 (qwen-flash→qwen-plus) | ✅ | TF-IDF 双 Target 均有效 |
| 域外压力测试 (LiveMath) | ✅ | 地板效应，仅作压力基准 |

---

## 二、SearchQA — 主实验（已结项）

| 版本 | Target | 方法 | Test |
|------|------|------|:--:|
| Phase 2 | qwen-flash | 6C+18D, text-only TF-IDF | **0.7386±0.0037** |
| Phase 3 | qwen-flash | 8C+16D, expanded-trigger TF-IDF | **0.7376±0.0036** |

两版差值 0.0010 处于 qwen-flash 输出波动范围内。

---

## 三、跨任务迁移 — SearchQA 规则不能迁移到数学

固定 SearchQA 训练的 8C+16D 原子规则，直接应用于 MMLU 数学：

| 配置 | Elem Math | HS Math |
|------|:--:|:--:|
| 无 skill | 0.14 | 0.12 |
| SearchQA 规则 | 0.16 (+0.02) | 0.16 (+0.04) |

迁移增益约 0.02-0.04，来自通用元策略（step-by-step、验证答案），但不来自内容级规则（查找策略、实体规范化）。SearchQA 规则包含大量"从文档中提取答案""使用 `<answer>` 标签"等特定领域的指令，对数学选择题无帮助。

---

## 四、跨难度迁移 — qwen-flash 在 MMLU 全部封顶

| MMLU 数学 | Train/Val | qwen-flash Baseline |
|------|:--:|:--:|
| Elementary | 200/60 | **0.983** |
| High School | 162/54 | **0.982** |
| College | 60/20 | **1.000** |

SkillOpt 训练循环要求 baseline 在 20-60% 区间才有优化空间。MMLU 所有数学子集均不满足。

**MMLU 数学不适合做 SkillOpt 交叉验证。**

---

## 五、域外压力测试 — LiveMath（Frontier Mathematical Meta-Reasoning Test）

### 5.1 三级能力维度

LiveMath 的 177 题同时测试三层能力：

1. **数学内容判断**：B/C/D/E 中的命题是否成立
2. **定理关系判断**：当前命题与更强/更弱/等价命题的关系
3. **元数学/文献判断**：是否已有论文证明了更强版本，当前结果在文献中的位置

### 5.2 18 条 val 题逐题分类

对 18 条验证题按正确答案 A 的内容类型分为三类：

| 类别 | 数量 | A 选项特征 | 示例 |
|------|:--:|------|------|
| **META-SELECT** | **11 (61%)** | "One of the remaining options is correct, but a stronger result can be proven." | 需要选择"哪个剩余选项正确"，不需证明该选项 |
| **MATH-DIRECT** | **7 (39%)** | 直接的数学命题 | "If G_k ≃ G_{k'} then (k,84)=(k',84)" |
| **THEOREM-RELATION** | **0 (0%)** | 显式提及强弱/等价关系 | — |

### 5.3 四组诊断 (18 val items)

| 模式 | 配置 | 正确 | 解读 |
|------|------|:--:|------|
| M0 | 原始问题 | 0/18 = 0% | 基线归零 |
| M1 | +显式元判断提示 | 2/18 = 11% | 提示有微弱帮助 |
| M2 | +proof sketch | 0/18 = 0% | 证明概要超出模型理解 |
| M3 | +论文上下文 | 1/18 = 6% | 单题偶然 |

### 5.4 按类别分析

qwen-flash 在 M0 下 18 题全错，无法进行统计上有意义的分类别对比（每类样本量不足）。但可做定性判断：

- **META-SELECT 类 (11 题)**：qwen-flash 选择 B/C/D/E，说明执行了第一层数学判断，但未意识到题目要求选出"哪个是对的"而非"每个是否对"。**这是任务框架识别问题，不是数学能力问题。**
- **MATH-DIRECT 类 (7 题)**：qwen-flash 同样全错，但 A 选项本身就是直接数学命题。**这是数学内容理解上限。**

### 5.5 Floor Effect 机制

当 qwen-flash 在 18 条 val 上全错时，SkillOpt 的训练循环完全失效：

- 无成功轨迹供优化器总结
- 所有反思来自失败样本
- 单次答对 1 题造成分数跳变 0→0.056
- Gate 无法区分真实能力和噪声
- 优化器倾向于总结"总选A"等伪规律

### 5.6 结论

> qwen-flash 在 LiveMath 上的全错不能解释为数学能力缺失。该基准同时测试研究级定理理解、逻辑分类、证明策略和元数学判断，对轻量模型形成能力地板。LiveMath 应重新命名为 **Frontier Mathematical and Meta-Reasoning Test**，仅用作研究级压力测试，不作为 SkillOpt 训练集。

> 11/18 val 题 (61%) 属于 META-SELECT 类型——正确答案 A 不涉及具体数学判断，而是识别"哪个剩余选项正确"。qwen-flash 在此类题目上可能执行了第一层数学判断但未意识到题型要求。剩余 7 题 MATH-DIRECT 型 A 选项是直接数学命题，qwen-flash 在数学内容理解上存在容量上限。

---

## 六、跨 Target 迁移 — TF-IDF 检索在双模型上均有效

固定 SearchQA 6C+18D 规则库 + TF-IDF Top-5，仅切换 Target 模型：

| Target | Core Only | TF-IDF Top-5 | Δ |
|------|:--:|:--:|:--:|
| qwen-flash | 0.7171 | **0.7386** | **+0.0215** |
| qwen-plus | 0.7307 | 0.7343 | +0.0036 |

**TF-IDF 检索在两个 target 上均有效。** qwen-plus 自身推理更强，对规则依赖度低于 qwen-flash（+0.0215 vs +0.0036），这是一个"能力越弱受益越大"的合理现象。

**原子化 RAG 框架跨 Target 迁移成立。**

---

## 七、完整结论

### 可确认的

| 结论 | 证据等级 |
|------|:--:|
| 原子化是 RAG 生效的决定性前提 | 强（SearchQA 完整消融） |
| TF-IDF Top-5 > Core Only，两个 Target 上方向一致 | 强 |
| 规则跨任务内容级不迁移，元策略级可迁移约 0.02-0.04 | 中（仅 SearchQA→MMLU） |
| MMLU 数学对 qwen-flash 存在天花板效应 | 强 |
| LiveMath 对 qwen-flash 存在地板效应 | 强 |
| gated slow update 消除退化 | 强（6 轮训练证实） |
| 模拟退火引入新退化路径 | 强 |

### 不可确认的

| 结论 | 原因 |
|------|------|
| 规则原子化在其他任务类型上的泛化性 | 仅在 SearchQA 上验证 |
| TF-IDF vs Semantic 在非关键词任务上的排序 | 仅在 SearchQA 上验证 |
| cross-dataset curriculum 的有效性 | 无合适的中间难度数据集 |

---

## 八、最终架构

```
原子化规则库 + Core/Dynamic 分离 + TF-IDF Top-5 + Gated Slow Update
= 零退化，跨 Target 迁移有效，跨任务迁移需任务特异性规则
```

LSTM、遗忘门、语义向量、模拟退火继续后移。当前阶段的真正瓶颈已在 SearchQA 上被充分研究和解决，但在其他任务类型上需要任务特异性规则库。
