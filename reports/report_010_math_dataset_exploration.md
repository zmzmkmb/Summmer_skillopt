# SkillOpt 数学数据集探索报告

> 日期：2026-07-26 | 分支：`main` | 交叉验证阶段

---

## 一、探索动机

SearchQA 主实验已结项。需要找一个数学推理数据集用于跨任务交叉验证，其 baseline 应处于 20-60% 区间以确保 SkillOpt 训练循环有充足的正负样本对比信号。

---

## 二、测试的全部数学数据集

| 数据集 | 题型 | 题数 | qwen-flash 基线 | 判定 |
|------|------|:--:|:--:|:--:|
| LiveMath | 研究级定理+元判断 | 177 | 0% / 11%* | ❌ 地板效应 |
| MMLU Elementary | 4-5 选 1 | 378 | 98.3% | ❌ 天花板 |
| MMLU High School | 4-5 选 1 | 270 | 98.1% | ❌ 天花板 |
| MMLU College | 4-5 选 1 | 100 | 100% | ❌ 天花板 |
| MMLU-Pro Math | 10 选 1 | 1351 | 40% / 90.5%* | ⚠️ 管道模板污染 |
| MATH (hendrycks) | 开放式 | 12,500 | — | ⬜ 无法加载 |

> * 40% = 直接 prompt 测试。90.5% = SkillOpt SearchQA adapter 包装后的训练基线。
> * 11% = 训练管道内带元判断提示的基线。

---

## 三、重点发现

### 3.1 MMLU 数学全系列天花板

qwen-flash 在 MMLU 三个难度级别上的无 skill 基线均 > 98%。MMLU 数学题对当前模型能力已无区分度。

### 3.2 LiveMath 地板效应

LiveMath 177 题全部有正确答案 A，其中 61% 是元判断题（"以下选项之一正确但可证更强结论"）。qwen-flash 在训练管道内基线为 0%（原始模板）或 11%（精简模板+元判断提示）。直接 prompt 测试可达 72%。

瓶颈不在数学能力，而在：
- 训练管道使用 SearchQA adapter 的 `_build_system` 包装 skill，扭曲了 LiveMath 所需的元判断格式
- LiveMath 只适合作为 prompt-level meta-reasoning 测试，不适合当前 SkillOpt 训练管道

### 3.3 MMLU-Pro Math — 最优候选但有管道污染

直接测试 qwen-flash：**40%** — 精确命中 SkillOpt 目标区间（20-60%）。

但 SkillOpt 训练基线为 **90.5%** — SearchQA adapter 的 prompt 模板在包装 skill 时附加了更好的格式指令，使基线大幅提升。

SkillOpt 训练结果：90.5% → 93.0%（仅 +2.5%），13 步后（共 80 步）连续 10 次 reject 停滞。

### 3.4 管道模板污染问题

所有 MMLU 系列数据集通过 SkillOpt 的 SearchQA adapter 训练时，prompt 被 `_build_system` + `rollout_system.md` 模板包装，包含解题策略、输出格式等指令。这套包装对 SearchQA 有正面作用，但对数学选择题造成了 ~50% 的"prompt 增益"——使 40% 的原始能力变为 90%+。

**这意味着：用当前 SkillOpt 管道测任何 MMLU 系数学数据集，基线都会偏高，无法获得有效的训练信号。**

---

## 四、结论

| 问题 | 结论 |
|------|------|
| MMLU 数学适合交叉验证吗？ | **不适合** — 全线天花板 |
| LiveMath 适合交叉验证吗？ | **不适合** — 地板效应，需专用 adapter |
| MMLU-Pro Math 适合交叉验证吗？ | **数据可行**（原始 40%），**管道不可行**（模板污染至 90.5%） |
| 当前 SkillOpt 能否在数学上做有效交叉验证？ | **否** — 所有候选数据集或被管道污染（MMLU 系），或有地板效应（LiveMath），或无法加载（MATH） |

## 五、要真正在数学上做交叉验证需要

1. **使用 SkillOpt 的 livemathematicianbench adapter 或新建数学专用 adapter**，而非复用 SearchQA 的 prompt 模板
2. **或使用开放式答案的数据集**（如 MATH），评分用 exact match 而非选项标签
3. **或直接以 MMLU-Pro 的原始 prompt（40%）作为推理消融基线**，跳过 SkillOpt 训练管道，仅做推理层面的检索方法对比
