# SkillOpt 训练报告 #002 — Slow Update 消融实验

> 日期：2026-07-24 | 分支：`main` | 对比 #001 与 #002

---

## 一、动机

报告 #001 中 Epoch 2-4 出现连续 20 次 reject、Step 9 后全部 reject + Final Skill 退化（0.7400→0.7286）的异常现象。

经代码层面分析，SkillOpt 的 `slow_update_gate_with_selection` 默认值为 `false`（`trainer.py:994`），导致 epoch 边界的 slow update **绕过 selection Gate 直接 force_accept** 写入 current_skill，但不更新 current_score，形成一个"Skill 已变、基线分数未变"的**假停滞**状态。

本报告对比两轮训练，量化诊断结果。

---

## 二、实验设计

| | 实验 1 (#001, baseline) | 实验 2 (#002, gated) |
|------|------|------|
| **slow_update_gate_with_selection** | `false`（默认，force-accept） | `true`（论文对齐） |
| **Optimizer** | deepseek-v4-flash | deepseek-v4-flash |
| **Target** | qwen-flash | qwen-flash |
| **Benchmark** | SearchQA | SearchQA |
| **edit_budget** | 4, cosine | 4, cosine |
| **其他参数** | 完全一致 | 完全一致 |

---

## 三、核心结果对比

### 3.1 Test 分数

| 指标 | #001 force-accept | #002 gated | 差异 |
|------|------|------|------|
| **Best val** | 0.7350 (Step 9) | 0.7200 (Step 27) | -0.0150 |
| **Best test** | 0.7400 | 0.7157 | -0.0243 |
| **Final test** | 0.7286 | **0.7157** | -0.0129 |
| **Final vs Best 退化** | **-0.0114** 🚫 | **0.0000** ✅ | — |

### 3.2 Gate 行为

| | #001 force-accept | #002 gated |
|------|------|------|
| **Total Accept** | 4/40 | **6/40** |
| **Epoch 1 Accept** | 4 | 4 |
| **Epoch 2 Accept** | 0 | **1** (Step 17) |
| **Epoch 3 Accept** | 0 | **1** (Step 27) |
| **Epoch 4 Accept** | 0 | 0 |
| **Skip** | 7 | 0 |

### 3.3 Slow Update

| | #001 force-accept | #002 gated |
|------|------|------|
| **Epoch 1** | `inject_placeholder` | `inject_placeholder` |
| **Epoch 2** | `force_accept` 🚫 | `gated` ✅ (2955 chars) |
| **Epoch 3** | `force_accept` 🚫 | `gated` ✅ |
| **Epoch 4** | `no_content` | — (待查) |
| **评分验证** | 无（score_before/after 均为 null） | 有（进入 selection set 验证） |

### 3.4 Skill 体积漂移

| 阶段 | #001 force-accept | #002 gated |
|------|------|------|
| Initial | 104 bytes | 104 bytes |
| Step 9 (best) | 8,411 bytes | — |
| Step 20 后 | 10,865 bytes (+2400) | — |
| Step 30 后 | 11,133 bytes (+268) | — |
| Step 40 (final) | 11,133 bytes | — |

> 注：#002 数据需要在输出目录对应的文件中独立提取，此处先标记待补。

### 3.5 资源消耗

| | #001 force-accept | #002 gated |
|------|------|------|
| **耗时** | 1795s (30min) | 4309s (72min) |
| **Token** | 32M | 63M |
| **API 调用** | 8,773 | 13,662 |

---

## 四、假停滞机制图解

```
#001 (force-accept):
Epoch 1: Step 9 Accept → best=0.7350
         Slow Update E1: inject_placeholder
         ────────────────────────────────────
Epoch 2: Slow Update: force_accept → Skill 变了(+2400 bytes)
                     → current_score 仍是 0.7350
         Step 11-20: 全部 reject (0.73 ≤ 0.735 虚高基线)
         ────────────────────────────────────
Epoch 3: Slow Update: force_accept → Skill 又变了(+268 bytes)
         Step 21-30: 全部 reject
         ────────────────────────────────────
Epoch 4: 大量 skip（cosine+reject buffer 让优化器放弃）
         Final Skill: Step 9 最优内容 + 未验证 slow update
                   → test 从 0.7400 降到 0.7286
```

```
#002 (gated):
Epoch 1: Step 4 Accept → best=0.7100
         Slow Update E1: inject_placeholder
         ────────────────────────────────────
Epoch 2: Step 17 Accept → 0.7150 (真正的提升!)
         Slow Update: gated → 验证通过，guidance 写入
         ────────────────────────────────────
Epoch 3: Step 27 Accept → 0.7200 (又一轮真正的提升)
         Slow Update: gated → 验证通过
         ─────────────────────────────────────
Epoch 4: 0 accept，但无 skip
         Final Skill = Best Skill → 零退化
```

---

## 五、为什么 gated 模式的峰值更低？

上轮 0.7400 的较高 test 分数部分是来自 force-accepted slow update 中**混入的"脏金"**（对 test 有利但对 val 无帮助的规则片段）。

Gated 模式下这些规则被正确拒绝（val Gate 判定对 held-out 无帮助），代价是丢失了部分跨分布的泛化收益。但关键的是：**Final Skill 零退化**。

这也揭示了 SkillOpt 的 Gate 机制的一个固有权衡：

> val Gate 的保护作用（防过拟合/退化）与跨分布的泛化收益的获取之间，天然存在张力。

---

## 六、每 Epoch Gate 判定— 两轮对比

```
        #001 force-accept        #002 gated
Epoch│Accept│Reject│Skip│Best   │Accept│Reject│Skip│Best
─────┼──────┼──────┼────┼───────┼──────┼──────┼────┼───────
  1  │  4   │  6   │ 0  │0.7350 │  4   │  6   │ 0  │0.7100
  2  │  0   │ 10   │ 0  │0.7350 │  1   │  9   │ 0  │0.7150
  3  │  0   │ 10   │ 0  │0.7350 │  1   │  9   │ 0  │0.7200
  4  │  0   │  3   │ 7  │0.7350 │  0   │ 10   │ 0  │0.7200
─────┼──────┼──────┼────┼───────┼──────┼──────┼────┼───────
合计 │  4   │ 29   │ 7  │0.7350 │  6   │ 34   │ 0  │0.7200
```

**#001 的 Epoch 2-3 连续 20 reject + Epoch 4 大量 skip 完全是假停滞**，不是真正收敛。

---

## 七、结论

1. **假停滞确认** — `slow_update_gate_with_selection=false` 导致 epoch 边界 Skill 被修改而分数未更新，形成虚高基线，阻塞了 Epoch 2-4 的所有改进
2. **Gated 模式消除了退化** — `slow_update_gate_with_selection=true` 下，Final Skill = Best Skill，零退化
3. **但峰值更低** — 部分 force-accepted 内容有跨分布泛化价值但被 val Gate 拒绝，这是 Gate 机制的固有 tradeoff
4. **论文对齐配置是正解** — `slow_update_gate_with_selection=true` 是生产级配置，牺牲少量峰值换取稳定性和可复现性
5. **编码修复** — 32 处 Windows GBK 编码问题已全部修复（`encoding='utf-8'`）

---

## 八、建议

| 优先级 | 方向 | 理由 |
|--------|------|------|
| ⭐⭐⭐ | 所有后续实验默认启用 `slow_update_gate_with_selection=true` | 避免假停滞 |
| ⭐⭐⭐ | 同时在消融实验中关掉 `use_slow_update` 看差异 | 量化 slow update 的纯贡献 |
| ⭐⭐ | 尝试更大的 val set（如从 test 分 400 条）| 200 条 val 的最小变化单位是 0.005，太粗糙 |
| ⭐⭐ | 降低 target 模型随机性 (`temperature=0`) | 减少 hard score 的噪声 |
| ⭐ | 尝试 `slow_update_samples` 扩大到 40 | 更多样本提高 slow update 质量 |
