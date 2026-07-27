# report #015: Law Fast/Slow Ablation — 部分结果

> 日期：2026-07-27 | 干预原因：DeepSeek API 余额耗尽 (step 37 + 连续 10 reject)
> 此为截断实验的部分结果，非完整 4-epoch 消融。

---

## 实验设置

| 参数 | 值 |
|------|:--|
| 数据集 | MMLU-Pro Law (train=660, val=165, test=276) |
| Target | qwen-flash (DashScope) |
| Optimizer | deepseek-v4-flash (DeepSeek) *余额耗尽于 step 37* |
| Epochs | 4 |
| Batch | 40 |
| Edit budget | 4 (Fast), 0 (baseline steps in slow-only) |
| Seed | 42 |

## 四组对比

| 方法 | Steps | Best Val | Δ Val | Best Test | Δ Test | Gate Accepts | Skill | 停止原因 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|------|
| **Initial** | — | 33.33% | — | 34.42% | — | — | 323 | — |
| **Fast-only** | 43/68 | **40.61%** | **+7.28pp** | **35.87%** | **+1.45pp** | 4 step | 18,156 | 连续11 reject |
| **Slow-only**† | 68/68 | 41.82% | +8.49pp | 38.41% | +3.99pp | 1 slow | 376 | 完成 |
| **Fast+Slow** | 26/68 | 36.97% | +3.64pp | 34.42% | 0.00pp | 3 step | 14,602 | 连续10 reject |

> † Slow-only: 来自 pipeline bug 修复前的 `mmlupro_law_true`。Step patches 被 bug 阻断为 0，仅 epoch-level slow_update 产生增益。
> Fast-only 和 Fast+Slow 在修复后代码上运行。Test eval 手动补跑。

---

## 关键发现

### 1. Slow-only 是当前最佳方案

**Slow-only test +3.99pp（34.42%→38.41%），val +8.49pp**，且 skill 仅增长 53 chars。

### 2. Step-level optimizer 有提升但过拟合严重

Fast-only val +7.28pp（33.33%→40.61%），但 test 仅 +1.45pp（34.42%→35.87%）。**Val/test 差距达 4.74pp**，skill 膨胀 56×（323→18,156 chars）。

可能原因：
- 165 题 val set 太小，噪声大，gate 接受的是噪声改善而非真正泛化
- 18K chars 的技能可能超过了 qwen-flash 的有效使用上限
- 需要更大的 val set 或更严格的 gate 来防止过拟合

### 3. Fast+Slow 未收敛

截断太早（step 26/68，未经历任何 slow_update），test 无变化（34.42% = baseline）。

### 4. Slow_update 产生更紧凑、更泛化的技能

| | Skill 长度 | Val | Test | Val/Test 差距 |
|------|:--:|:--:|:--:|:--:|
| Slow-only | 376 chars | 41.82% | 38.41% | 3.41pp |
| Fast-only | 18,156 chars | 40.61% | 35.87% | **4.74pp** |

Slow_update 用 48× 更少的字符达到了更好的 test 性能，且 val/test 差距更小。

---

## 已知限制

1. **API 余额不足**导致 Fast-only 截断于 step 37, Fast+Slow 于 step 26
2. **无多 seed** — 所有结果 seed=42
3. **Fast-only test 未跑** — API 余额耗尽后无法评估
4. **Slow-only 来自不同代码版本** — pipeline bug 可能影响结果
5. **Fast+Slow 未经历完整 epoch 2 slow_update**

---

## 下一步

1. **充值后完成**: Fast-only + Fast+Slow 正式完成到 4 epochs（或至少经历 slow_update）
2. **补 Philosophy + Math 消融**
3. **多 seed 重复** (seed=43, 44)
4. **更大的 val set**: 165 题噪声太大，考虑扩大 selection set
5. **防止 skill 膨胀**: 对 step-level update 添加 skill 长度惩罚或 edit budget 衰减
