# SkillOpt 训练报告 #003 — 模拟退火 Gate 实验

> 日期：2026-07-24~25 | 分支：`main` | 对比 #001, #002, #003

---

## 一、动机

报告 #001 发现 `slow_update_gate_with_selection=false` 导致假停滞。报告 #002 验证了 gated slow update 消除退化但峰值更低 (0.7200 vs 0.7350)。

#003 引入**模拟退火 Gate**：当候选分数 ≤ 当前分数时，不再直接拒绝，而是按 Metropolis 准则 `p = exp(Δ/T)` 概率接受，允许探索可能走出局部最优。

---

## 二、实现

### 修改文件

| 文件 | 改动 |
|------|------|
| `skillopt/evaluation/gate.py` | +158 行：`evaluate_gate_with_annealing()`、`compute_temperature()`、`_metropolis_accept()` |
| `skillopt/engine/trainer.py` | +168/-39 行：步骤级和 slow-update 级集成，统计分离 |
| `skillopt/config.py` | +4 行：退火 key 加入 `_FLATTEN_MAP` |

### 温度 schedule

```
T(t) = T0 × 0.92^t, 最后 20% step 线性 ramp-down, 最低 0.001
T0 = 0.02 ≈ 4 条 val 题的分数
```

| Step | T | 行为 |
|------|-----|------|
| 0 | 0.0200 | 接受约 -0.01 以内的下降 (~60%) |
| 10 | 0.0087 | 接受约 -0.005 以内的下降 |
| 20 | 0.0038 | 基本严格 |
| 35+ | 0.001 | ≈ 严格 Gate |

### 三个不变式

1. **`best_skill` 永远不因退火而降级**
2. **`current_skill` 与 `current_score` 始终同步**
3. **温度降到 0 后等价于严格 Gate**

---

## 三、实验设计

| | #001 baseline | #002 gated | #003 退火 |
|------|:--:|:--:|:--:|
| **Optimizer** | deepseek-v4-flash | deepseek-v4-flash | **deepseek-v4-flash** |
| **Target** | qwen-flash | qwen-flash | qwen-flash |
| **slow_update_gate_with_selection** | false | true | true |
| **use_annealing** | false | false | **true (T0=0.02)** |
| **其他参数** | 完全一致 | 完全一致 | 完全一致 |

---

## 四、核心结果

| | #001 baseline | #002 gated | #003 退火 |
|------|:--:|:--:|:--:|
| **Best val** | 0.7350 | 0.7200 | **0.7300** |
| **Best test** | 0.7400 | 0.7157 | **0.7214** |
| **Final test** | 0.7286 | **0.7157** | 0.7107 |
| **退化 (final vs best)** | **-0.0114** 🚫 | **0** ✅ | -0.0107 ⚠️ |
| **Total Accept** | 4 | 6 | 6 (+ 5 annealing) |
| **Epoch 1 Accept** | 4 | 4 | 4 (+ 4 annealing) |
| **Epoch 2 Accept** | 0 | 1 | 2 |
| **Epoch 3 Accept** | 0 | 1 | 0 (+ 1 annealing) |
| **Epoch 4 Accept** | 0 | 0 | 0 |
| **耗时** | 1,795s | 4,309s | 37,818s* |

> *含机器休眠，实际活跃时间约 2 小时

---

## 五、退火行为详细记录

### 退火触发（共 5 次）

| Step | T | 动作 | 说明 |
|------|------|------|------|
| 3 | 0.0169 | annealing_accept | 平手 0.710=0.710，接受避免无意义 tie-reject |
| 8 | 0.0132 | annealing_accept | 轻微下降 0.710→0.700 |
| 9 | 0.0103 | annealing_accept | 继续探索 0.700→0.690 |
| 10 | — | accept | 反弹到 0.705 ✅ |
| 16 | — | accept_new_best | 冲到 0.7300 🏔 |
| 24 | 0.0029 | annealing_accept | 轻微下降 0.730→0.725，后续 16 步无法恢复 ⚠️ |

### Slow update 行为

| Epoch | 动作 | 说明 |
|------|------|------|
| 1 | inject_placeholder | 正常 |
| 2 | reject (hard=0.725) | gated，正确拒绝 |
| 3 | reject (hard=0.690) | gated，正确拒绝 |
| 4 | reject (hard=0.695) | gated，正确拒绝 |

> ✅ 所有 slow update 都经过 Gate 验证，无 force-accept 污染。

---

## 六、三组对比分析

### 6.1 Accept/Reject 分布

```
        #001                  #002                  #003
Epoch│Ac│Rej│Sk│Best   │Ac│Rej│Sk│Best   │Ac│An│Rej│Sk│Best
─────┼──┼───┼──┼───────┼──┼───┼──┼───────┼──┼──┼───┼──┼───────
  1  │ 4│ 6 │ 0│0.7350 │ 4│ 6 │ 0│0.7100 │ 4│ 4│ 2 │ 0│0.7250
  2  │ 0│10 │ 0│0.7350 │ 1│ 9 │ 0│0.7150 │ 2│ 0│ 8 │ 0│0.7300
  3  │ 0│10 │ 0│0.7350 │ 1│ 9 │ 0│0.7200 │ 0│ 1│ 9 │ 0│0.7300
  4  │ 0│ 3 │ 7│0.7350 │ 0│10 │ 0│0.7200 │ 0│ 0│10 │ 0│0.7300
─────┼──┼───┼──┼───────┼──┼───┼──┼───────┼──┼──┼───┼──┼───────
合计 │ 4│29 │ 7│0.7350 │ 6│34 │ 0│0.7200 │ 6│ 5│29 │ 0│0.7300
```

### 6.2 关键信号

| 观察 | #001 | #002 | #003 |
|------|:--:|:--:|:--:|
| E2/3 有 accept（未假停滞）| ❌ | ✅ | ✅ |
| Final=Best（零退化）| ❌ | ✅ | ❌ |
| 退火真正打破了 tie | — | — | ✅ |
| 退火允许探索后反弹 | — | — | ✅ Step 8-10-16 |
| 退火也引入了新退化 | — | — | ⚠️ Step 24 后无法恢复 |

---

## 七、问题分析

### 7.1 退火导致的新退化模式

```
Step 16: best = 0.7300
Step 24: T=0.0029, annealing accept 0.730→0.725
Step 25-40: 全部 reject, 无法回到 0.730
Final test: best=0.7214, final=0.7107 (退化 -0.0107)
```

**根因**：退火接受劣解后，`current_score` 被永久降到了 0.725。后续所有候选只需 > 0.725 即 accept。但问题是模型组合的上限大约就是 0.730，优化器很难再生成超越这个水平的编辑。于是出现了和 #001 类似的退化——不过这次不是因为 slow update force-accept，而是因为退火接受了一个无法恢复的劣解。

### 7.2 模型一致性

三轮均使用 `deepseek-v4-flash`（早期 API 接受 `deepseek-chat` 作为别名），是同一个模型。

---

## 八、建议的退火改进

### 8.1 退火不应永久降级 current_score 锚点

当前逻辑：

```
退火 accept → current_score = 0.725（永久降低 Gate 门槛）
```

建议改为：

```
退火 accept → current_score 锚回退火前的值 0.730
             → current_skill 前进到候选
             → 后续比较用 0.730 而非 0.725
```

这样退火只探索新 skill，但不降低后续 Gate 的门槛。

### 8.2 退火接受后设置"探索窗口"

退火接受后，接下来 N 步（如 3 步）内也允许退火，但窗口关闭后必须回到退火前分数。

### 8.3 退火不应覆盖到 slow update gate

当前实现在 slow update gate 也启用了退火。但 epoch 边界是低频操作，退火风险太高。Epoch 2-4 slow update 全部被正确 reject（分数 0.725, 0.690, 0.695），说明当前实现没出问题，但为了安全，slow update gate 应该始终严格。

---

## 九、结论

| 发现 | 结论 |
|------|------|
| **退火机制有效** | 打破了 tie-reject，允许了探索，Step 8-10-16 是从退火探索中恢复并冲击新高的典型案例 |
| **当前实现有缺陷** | 退火 accept 永久降低 current_score，导致 Step 24 后无法恢复，final 退化 |
| **最佳配置仍是 #002** | `slow_update_gate_with_selection=true`, `use_annealing=false` — 零退化、可复现 |

### 三跑最终排名

| 排名 | 实验 | Test best | Final 退化 | 推荐？ |
|------|------|:--:|:--:|------|
| 🥇 | #001 force-accept | 0.7400 | -0.0114 | ❌ 假停滞，不可复现 |
| 🥈 | #002 gated | 0.7157 | 0 | ✅ 生产推荐 |
| 🥉 | #003 退火 | 0.7214 | -0.0107 | ⚠️ 实验性，需修复 |
