# report #012: 纯 MMLU-Pro Adapter 实验 — 去掉 SearchQA 模板

> 日期：2026-07-27 | 分支：`main` | 3 领域纯 adapter 消融

---

## 一、研究问题

去掉 SearchQA adapter 的 prompt 模板后：
1. 基线如何变化？
2. Step-level 优化器还能产出规则吗？
3. Slow update 能否单独支撑改进？

---

## 二、实验结果总览

| | Math | Law | Philosophy |
|------|:--:|:--:|:--:|
| train/val/test | 800/200/351 | 660/165/276 | 299/75/125 |
| 基线 val | 49.00% | 38.79% | 58.67% |
| 基线 test | 0% (bug) | 34.42% | 56.80% |
| **最佳 val** | 89.00% | 41.82% | 62.67% |
| **最佳 test** | 0% ⚠️ | **38.41%** | **63.20%** |
| Test Δ | — | **+4.0pp** | **+6.4pp** |
| Step patches | 0 | 0 | 0 |
| Step accepts | 0 | 0 | 0 |
| Slow update accepts | 1/4 | 1/4 | 2/4 |

---

## 三、与 SearchQA adapter 对比

| 领域 | 指标 | SearchQA adapter | 纯 adapter | 差异 |
|------|------|:--:|:--:|:--:|
| Math | baseline val | 89.0% | 49.0% | **-40pp** |
| | step patches | 3 accepts | **0** | patches 消失 |
| Law | baseline val | ~43% | 38.8% | -4.2pp |
| | step patches | 3 accepts | **0** | patches 消失 |
| Philosophy | baseline val | ~63% | 58.7% | -4.3pp |
| | step patches | 4 accepts | **0** | patches 消失 |

---

## 四、核心发现

### 4.1 Step-level patches 全部消失

**deepseek 分析器在纯 initial_skill 下无法产出任何规则。**

旧的 SearchQA adapter 模板包含 "从文档提取答案""验证上下文"等指令，这些指令实际上在**帮助分析器理解任务结构**，而不是在污染。去掉后，分析器面对 76 字符的通用指令完全无法产出领域特定的规则。

**结论反转**：report #011 认为 SearchQA adapter 是污染源——但实验证明相反。它提供的任务 context 对分析器至关重要。

### 4.2 Slow Update 独立有效

所有改进均来自 epoch 间 slow update：
- Law: epoch 3 注入法律特定 guidance → +3.4pp
- Philosophy: epoch 2+4 注入哲学特定 guidance → +6.4pp total
- Math: epoch 2 注入 "show your reasoning" guidance → val 49%→89%

### 4.3 Math test=0% bug

Slow update 注入的 guidance 把 val 从 49% 拉回 89%（和旧 adapter 持平），但 test set 评估全崩（0%）。很可能是 slow_update 的 guidance 改变了 answer format，evaluator 无法解析。

### 4.4 纯 slow_update 是一条可行路径

不依赖 step-level patches 的训练方式：
- 优点：更少 API 调用、更稳定
- 缺点：改进粒度粗（epoch 粒度 vs step 粒度）、不能 incremental refinement

---

## 五、Slow Update Guidance 质量分析

Math slow_update (epoch 2) 产出的 guidance（3472 chars）包含了针对 10 种数学题型的**具体解法**：
- 概率连续区域 → 面积比法
- 线性代数 → 具体反例法
- 拉格朗日乘子 → 代入约束法
- 财务 → 有效年利率公式
- 指数化简 → 质因数分解
- 正态分布 → z-score 法
- 组合 → Stirling 数
- ...

**这些是非常具体、高质量的领域知识**——deepseek 在 slow_update 模式下可以产出，但在 step-level 的 minibatch 分析中不行。可能原因：
1. slow_update 有 20 个 longitudinal pair 做对比，context 更丰富
2. slow_update 的 prompt 明确要求 "反思跨 epoch 差异"
3. step-level 的 minibatch 只有 8 个样本，信息不足

---

## 六、结论

1. **SearchQA adapter 模板不是污染** — 它对分析器理解任务至关重要
2. **纯 initial_skill 下 step-level 优化器失效** — 分析器需要任务 context 才能产出规则
3. **Slow update 独立有效** — 是当前纯 adapter 的唯一改进来源
4. **混合方案最有前景** — SearchQA adapter（给分析器 context）+ slow_update（epoch 级高质量 guidance）
5. **Math test bug 需修复** — slow_update guidance 破坏了 output format

---

## 附录：P0 实现错误修正及验证（2026-07-27）

### A. 本报告结论的错误

报告正文第 1-2 条结论：

> 1. SearchQA adapter 模板不是污染 — 它对分析器理解任务至关重要
> 2. 纯 initial_skill 下 step-level 优化器失效 — 分析器需要任务 context 才能产出规则

**在代码审查后发现这两个结论均不成立**。step-level patches=0 的根本原因是两个确定性的实现 bug：

| Bug | 位置 | 影响 |
|-----|------|------|
| **Bug 1: 轨迹上下文缺失** | `rollout.py:67` | Analyst 只看到答案字母 "B"，看不到题目、选项、gold answer、system prompt |
| **Bug 2: 输出协议不兼容** | `analyst_error.md` / `analyst_success.md` | Prompt 要求 JSON 数组 `[{op,...}]`，但 `reflect.py:344` 只接受 `{"patch": {"reasoning": "...", "edits": [...]}}`。模型正确生成的编辑因 `"patch" in result` 对 list 为 False 而被静默丢弃 |
| **Bug 3: Math test=0%** | 非代码 bug | 训练后 test eval 阶段 API 连接全部失败 (351/351 Connection error) |

### B. 修复验证结果

复现环境：Law + Philosophy，小数据（train=40, val=30），batch=20，2 epochs，4 steps。

| 指标 | 修复前 | 修复后 |
|------|:--:|:--:|
| Step-level patches | 0/180 steps | **3-4 patches per step** ✓ |
| Philosophy gate accept | 0 | **Step 1 ACCEPT** ✓ |
| Philosophy test Δ | 仅 slow_update | **Step 1 +5.60pp** ✅ |
| Law gate accept | 0 | 0（30-item val 噪声太大） |

**修复前 3 个实验 180 步全部 zero patches；修复后每步都产出合法 patch。**

### C. 修正后的结论

1. **Step-level optimizer 可以产出规则** — Bug 由输出协议不兼容 + 轨迹上下文缺失导致，不是 adapter 问题
2. **纯 initial_skill 下 step-level 优化器依然有效** — Philosophy step 1 产出了 6 个高质量编辑，直接带来 +5.60pp test gain
3. **SearchQA 模板的作用需重新评估** — 模板确实提供了 task context，但现有代码无法区分 "context 内容帮助" 和 "输出协议的确定性崩溃"。修复后用纯 adapter 重新做四组消融才能判断
4. **Slow update 独立有效** — Law +4.0pp, Philosophy +4.0pp 仅来自 slow_update。修复后 slow_update + step patches 可能更好
5. **Math test 重跑结果：初始 88.03%, 最佳 89.46% (+1.43pp)** — 基线已接近天花板，增益确实有限

### D. 修复 Commits

| Commit | 内容 |
|--------|------|
| `5c70cae` | P0 fix: rollout trajectory context + analyst output protocol |
| `8dac6a4` | P1: Math test=0% 诊断 + test re-eval |
| `0ed38f7` | P0 verification: step patches confirmed |
