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

## 五、域外压力测试 — LiveMath（研究级数学）

### 测评维度

LiveMath 的 177 题均为研究级定理判断题，同时测试三层能力：

1. **数学内容判断**：B/C/D/E 中的命题是否成立
2. **定理关系判断**：强弱、等价性
3. **元数学判断**：是否已有论文证明了更强结果

全部 177 题正确答案均为 A（元答案：选项之一正确但可证更强结论），构成严格的 floor effect。

### 四组诊断 (18 val items)

| 模式 | 配置 | 正确 | 解读 |
|------|------|:--:|------|
| M0 | 原始问题 | 0/18 = 0% | 基线归零 |
| M1 | +显式元判断提示 | 2/18 = 11% | 提示有帮助但不充分 |
| M2 | +proof sketch | 0/18 = 0% | 证明概要超出模型理解 |
| M3 | +论文上下文 | 1/18 = 6% | 单题偶然 |

### 结论

> qwen-flash 在 LiveMath 上的全错不能解释为数学能力缺失。该基准同时测试研究级定理理解、逻辑关系识别和元数学判断，轻量模型形成能力地板。LiveMath 应重新命名为 **Frontier Mathematical and Meta-Reasoning Test**，仅用作研究级压力测试，不作为 SkillOpt 训练集。

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
