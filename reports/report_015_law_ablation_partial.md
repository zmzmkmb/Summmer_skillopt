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

| 方法 | slow_update | 状态 | Last Step | Best Val | Best Test | Gate Accepts | Skill 增长 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Initial** | — | ✅ | — | 33.33% | 34.42% | — | 323 chars |
| **Fast-only** | ✗ | ⚠️ 截断 | 37/68 | **40.61%** | 待测 | **4** (step 1,3,7,32) | 323→18,156 |
| **Slow-only** | ✓ (step patches=0) | ✅ 完整 | 68/68 | 41.82% | 38.41% | 1 (slow epoch 3) | 323→376 |
| **Fast+Slow** | ✓ | ⚠️ 截断 | 26/68 | 36.97% | 待测 | 3 (step 3,15,16) | 323→14,655 |

> **Slow-only** 来自 `outputs/mmlupro_law_true`（pipeline bug 未修复版本，step patches 为 0，仅 slow_update epoch 3 接受）。
> **Fast-only** 和 **Fast+Slow** 来自修复后代码。

---

## 关键发现

### 1. Step-level optimizer 在 Law 上有效

**Fast-only 仅靠 step-level patches（无 slow update）在 val 上从 33.33%→40.61%（+7.28pp），4 次 gate accept。**

```
Step  1: val=33.94%  ACCEPT  skill 323→6518
Step  3: val=36.36%  ACCEPT  skill 6518→10950
Step  7: val=40.00%  ACCEPT  (epoch 1 内)
Step 32: val=40.61%  ACCEPT  (epoch 2 内)
```

这确认了 pipeline 修复后 step-level optimizer 确实能产生有意义的规则。

### 2. Fast+Slow 增益较小但可能未充分收敛

Fast+Slow 从 32.73%→36.97%（仅 +4.24pp），低于 Fast-only。可能原因：
- 实验被截断在 step 26/68，epoch 2 的 slow_update 还没运行
- Slow_update 与 step patches 的互动需要更多 epoch 才能体现
- Fast+Slow 的 val 基线略低（32.73% vs Fast-only 的 33.33%），噪声效应

### 3. Slow-only 的 val 最高但 test 增益有限

Slow-only val 达到 41.82%（slow_update epoch 3 accept），但 test 仅 38.41%（+3.99pp from baseline 34.42%）。**Val/test 差距达 3.4pp**——这是 Law 165 题 val set 噪声过大的另一个证据。

### 4. Skill 膨胀问题

Fast-only skill 从 323→18,156 chars（56× 膨胀）——质量待检验。

---

## 已知限制

1. **API 余额不足**导致 Fast-only 截断于 step 37, Fast+Slow 于 step 26
2. **无多 seed** — 所有结果 seed=42
3. **Fast-only test 未跑** — API 余额耗尽后无法评估
4. **Slow-only 来自不同代码版本** — pipeline bug 可能影响结果
5. **Fast+Slow 未经历完整 epoch 2 slow_update**

---

## 下一步

1. 充值 DeepSeek 后：跑 Fast-only + Fast+Slow 的 test eval
2. 补 Philosophy + Math 的 Fast/Slow 消融（需 API）
3. 多 seed 重复（seed=43, 44）
4. 分析 Fast-only skill（18156 chars）的规则质量
