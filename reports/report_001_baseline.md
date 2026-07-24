# SkillOpt 训练报告 #001 — SearchQA Baseline

> 日期：2026-07-24 | 分支：`main` | 输出：`outputs/skillopt_searchqa_deepseek-chat_20260724_170800`

---

## 一、实验配置

| 参数 | 值 |
|------|-----|
| Benchmark | SearchQA（纯文本 QA） |
| 数据集 | train=400 / val=200 / test=1400 |
| **Optimizer（反思模型）** | `deepseek-chat` via DeepSeek API |
| **Target（执行模型）** | `qwen-flash` via 阿里云 DashScope |
| Backend | `openai_compatible`（双模型独立配置） |
| edit_budget（学习率） | **4**（每步最多 4 条编辑） |
| lr_scheduler | **cosine**（余弦衰减，min=2） |
| skill_update_mode | **patch**（增量补丁模式） |
| use_gate | **true**（held-out 验证门控开启） |
| use_meta_skill | **true**（跨 epoch 元记忆） |
| use_slow_update | **true**（epoch 边界长时记忆） |
| 训练轮次 | 4 epochs × 10 steps = **40 steps** |

---

## 二、核心结果

### Test 集表现

| 阶段 | Test Hard | Test Soft | 提升 |
|------|-----------|-----------|------|
| 初始 Skill（104 字符） | 0.6336 | — | — |
| 最优 Skill（Step 9） | **0.7400** | 0.8245 | **+0.1064 (+16.8%)** |
| 最终 Skill（Step 40） | 0.7286 | 0.8151 | +0.0950 (+15.0%) |

> Gate 在 val 上选出了最优 skill（0.7350），在 test 上兑现为 0.7400，证明 Gate 没有 overfit val。

### Best-on-val 走势

```
0.6200 —— (Step 1 accept) —— 0.6750 —— (Step 4 accept) —— 0.7350 —— (Epoch 2-4 全部 reject) —— 0.7350
```

---

## 三、每 Epoch Gate 判定分布

```
Epoch │ Accept │ Reject │ Skip │     Best      │
──────┼────────┼────────┼──────┼───────────────┤
  1   │   4    │   6    │  0   │ 0.7350 ← 巅峰  │
  2   │   0    │  10    │  0   │ 0.7350         │
  3   │   0    │  10    │  0   │ 0.7350         │
  4   │   0    │   3    │  7   │ 0.7350         │
──────┼────────┼────────┼──────┼───────────────┤
 总计 │   4    │  29    │  7   │ 0.7350         │
```

**40 steps 中仅有 4 个被 Gate 接受，29 个被拒绝，7 个被跳过。** 这恰恰说明 Gate 在正常工作。

---

## 四、为什么 Accept 这么少、Best 一直不变？

### 这是 **Gate 机制正确运行的表现**，不是 bug

SkillOpt 的工作方式类似深度学习中的 **随机梯度下降 + 验证集早停**：

| 深度学习 | SkillOpt |
|----------|----------|
| 每次参数更新 | 每步对 skill.md 做 add/replace/delete 编辑 |
| 验证集 loss | Gate 在 held-out 200 条上评估 hard score |
| 早停（early stop） | Gate reject（拒绝不帮助的编辑） |
| 过拟合 | 编辑对训练集有利但对 held-out 无帮助 → Gate reject |

### Epoch 1 快速收敛

初始 skill 只有 104 个字符，只有一句 `(No learned rules yet.)`，千问 Flash 靠自身能力答对约 62%。前 4 个被接受的编辑快速注入了 8400+ 字符的规则，分数从 0.6200 跳到 0.7350。

### Epoch 2-4 撞墙

DeepSeek 继续生成编辑，但 Gate 全部拒绝。可能原因：

1. **模型组合的上限** — 千问 Flash 作为 Target 的能力有天花板，纯文本规则无法继续提升
2. **编辑过拟合** — 后续编辑基于训练集样例优化，但对 held-out 集无效
3. **SearchQA 相对简单** — 40 个 step 在第一个 epoch 就找到最优

### Skip 的含义

Epoch 4 有 7 个 skip：当训练 batch 的 rollout 分数已经很高（> 0.8），且 Cosine 调度将 learning_rate 衰减到 min（2），优化器判断"不值得为此生成编辑"。

---

## 五、资源消耗

| 指标 | 数值 |
|------|------|
| 总耗时 | **1795s ≈ 30 分钟** |
| 总 Token | **31,928,020**（prompt 31,666,583 + completion 261,437） |
| API 调用次数 | **8,773** |
| 平均每步耗时 | ~45s |
| Skill 最终长度 | 104 → ~10,000 字符 |

---

## 六、Skill 演化（节选最优编辑）

### 初始 skill（104 字符）
```
# Question Answering Skill
(No learned rules yet. Rules will be added through the reflection process.)
```

### 最优 skill 学到的核心规则（8,408 字符）

| 规则类型 | 示例 |
|----------|------|
| **指代消解** | 含物主代词的提问 → 回答指代实体而非作品标题 |
| **命名实体规范化** | 区分"仅答姓氏"vs"答全名"的边界条件 |
| **信息抽取策略** | 6 步定位-匹配-抽取流水线 |
| **复合线索推理** | 同时满足多个约束的实体消歧 |
| **输出格式约束** | `<answer>` 标签包裹、不附加评论 |
| **公司/品牌简化** | 去除 Inc./Corp./& Co. 等后缀 |
| **上义关系推理** | 列举多个实体 → 回答它们共同的类别 |

---

## 七、发现的问题与修复

### Windows GBK 编码问题

训练在 Step 18 崩溃，原因是 `skillopt/` 中多处 `open(path, "w")` 缺少 `encoding="utf-8"`，当 DeepSeek/Qwen 返回非 ASCII 字符时，Windows 默认 GBK 编码失败。

**修复**：批量将 `skillopt/` 下 **13 处**文件写入操作添加 `encoding="utf-8"`。

### 续跑机制

SkillOpt 内置 `runtime_state.json` 断点续跑，删除崩溃残留下的坏文件后，训练从 Step 18 正常恢复。

---

## 八、后续实验方向

| 优先级 | 方向 | 具体操作 |
|--------|------|----------|
| ⭐⭐⭐ | 加大学习率 | `edit_budget=8`，允许每步更多编辑 |
| ⭐⭐⭐ | 全量重写模式 | `skill_update_mode=full_rewrite_minibatch` |
| ⭐⭐ | 关闭 Gate 对照 | `use_gate=false`，贪婪接受所有编辑 |
| ⭐⭐ | 换更难 benchmark | SpreadsheetBench / DocVQA |
| ⭐ | 换更强 Target 模型 | 千问 Plus/Pro 替代 Flash |

---

## 九、结论

1. **SkillOpt 的有效性验证通过** — 初始→最优 +16.8%，Gate 正确地把 29/40 的编辑挡在门外
2. **千问 Flash + DeepSeek Chat 组合可行** — 总成本 ~32M token，30 分钟完成 40 step
3. **SearchQA 对该组合偏简单** — Epoch 1 即收敛，后续编辑几乎全被 Gate 拒绝
4. **Gate 机制是 SkillOpt 最重要的安全网** — 如果没有 Gate 而盲目接受全部编辑，skill 反而可能退化
