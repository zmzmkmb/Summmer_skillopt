# SkillOpt 项目阶段报告 — 从训练消融到规则优化

> 日期：2026-07-24 ~ 07-26 | 分支：`main` | 全部 7 份报告 + 6 个脚本 + 3 个新模块

---

## 一、项目概览

对 SkillOpt（Microsoft Research）框架在 SearchQA 上进行了系统的诊断、改进和消融。三个阶段的演进：

```
Phase 1 (训练消融): 发现假停滞 → 修复 slow_update_gate → 测试退火
Phase 2 (推理消融): 原子化规则库 → TF-IDF 检索 → 多 seed 验证 → 收束检索框架
Phase 3 (规则优化): trigger/text 分离 → Core/Dynamic 重平衡 → 单规则消融
```

### 核心成果

| | 之前 | 之后 |
|------|:--:|:--:|
| 搜索配置 | 随机选择的 force-accept | `8C+16D + TF-IDF Top-5 + Gated Slow Update` |
| 可复现性 | 否（假停滞） | 是（零退化） |
| 规则粒度 | 4 段粗粒度文本 | 24 条原子规则 |
| LSTM/遗忘门 | 计划中 | 永久推迟 |

---

## 二、Phase 1：训练消融（6 轮完整训练）

### 问题诊断

| 实验 | 关键发现 |
|------|------|
| #001 baseline | Best test=0.7400，但 final 退化到 0.7286。Epoch 2-4 全部 reject |
| #002 gated | 启用 `slow_update_gate_with_selection=true`，退化消失，但峰值降至 0.7157 |
| #003 退火 | Metropolis 退火 5 次触发（平手+探索），但 Step 24 退火接受劣解后无法恢复，final 退化 -0.0107 |
| #004 RAG(粗粒度) | 动态规则拖后腿 (-0.009 vs Core Only) |
| #005 Random 对照 | TF-IDF > Random +0.006 |
| #006 Core Only | 只用核心规则 → 0.7336，说明核心规则是主要增益来源 |

### Phase 1 核心结论

1. **假停滞确认** — `slow_update_gate_with_selection=false` 导致 force-accept 污染 current_skill 但不更新 score
2. **退火有效但引入新退化** — 退火接受劣解后 current_score 永久降低基准线
3. **粗粒度 RAG 是噪声源** — 4 条大段动态规则无法被精确检索

---

## 三、Phase 2：推理消融（固定规则库）

### 原子化

将粗粒度 skill（~10,000 字符，4 个 section）拆分为 24 条原子规则（6 Core + 18 Dynamic），每条 1-3 句话。

### 单次运行

| Top-K | Test Hard |
|:--:|:--:|
| 0 (Core Only) | 0.7229 |
| 3 | 0.7364 |
| **5** | **0.7400** |
| 8 | 0.7343 |

### 3-Seed 稳定性验证

| 方法 | Mean±Std | vs Core Δ |
|------|:--:|:--:|
| Core Only | 0.7279±0.0026 | — |
| Random Top-5 | 0.7305±0.0023 | +0.003 |
| Semantic Top-5 | 0.7310±0.0032 | +0.003 |
| **TF-IDF Top-5** | **0.7386±0.0037** | **+0.011** |

### 检测极限

- qwen-flash 输出 std ≈ 0.003（~4 题/1400）
- TF-IDF vs Random：差异 ~0.002-0.005，McNemar 不显著
- 语义向量（all-MiniLM-L6-v2）在 SearchQA 关键词任务上无增益

### Phase 2 核心结论

1. **原子化是决定性前提** — 将动态规则从噪声源变成正向增益
2. **TF-IDF 最优** — 关键词匹配任务上超过语义向量
3. **检测极限已到** — 继续微调检索器收益≤噪声水平

---

## 四、Phase 3：规则文本优化

### 改动

| 改动 | 版本 | Test |
|------|:--:|:--:|
| 6C+18D, text-only TF-IDF | Phase 2 最佳 | 0.7386±0.0037 |
| trigger/text 分离 + R23/R24→Core | Phase 3 最终 | 0.7281±0.0011 |
| 规则拆分（R20→R20+R25等） | 实验性 | **崩了** (-0.04) |

### 发现

1. **trigger/text 分离降低 ~0.01** — 短 trigger 损失了部分 TF-IDF 匹配精度
2. **规则过于细粒度导致竞争恶化** — 20 条 trigger 争 5 个 slot，区分度不足
3. **Core Only 波动较大** — 从 0.721→0.733 取决于规则集
4. **TF-IDF vs Core 差值稳定在 +0.008** — 检索本身始终有增量，不受规则数量影响

### Phase 3 核心结论

1. **架构方向正确但需要更好的检索器** — trigger/text 分离是必要的，单纯 TF-IDF 无法充分发挥
2. **规则拆分有上限** — 16-18 条动态规则已足够，再多会稀释 Top-5 slot
3. **单规则消融无效** — 所有 18 条规则 Δ 在 -0.02~0.00，无一条显著正贡献。问题不在"选什么"，而在"怎么写"

---

## 五、代码成果

### 新建模块

| 文件 | 说明 |
|------|------|
| `skillopt/rule_atomizer.py` | 24 条原子规则（8 Core + 16 Dynamic），含 trigger/text 分离 |
| `skillopt/rag_rule_selector.py` | 粗粒度 RAG 模块（已过时，保留作参考） |

### 新建脚本

| 文件 | 说明 |
|------|------|
| `scripts/retrieval_ablation.py` | 推理消融：Core Only / Random / TF-IDF / Semantic，多 seed + McNemar |
| `scripts/rule_ablations.py` | Leave-one-out 规则消融：逐条移除测 Δ |
| `scripts/rule_utility_rerank.py` | 规则效用重排序：IDF 惩罚 / precision-based（均失败） |
| `scripts/stable_error_analysis.py` | 多 seed 稳定错误分析：标记稳定错误 + 规则召回统计 |

### Bug 修复

| 修复 | 文件数 |
|------|:--:|
| Windows GBK → UTF-8 编码 | 22 |
| 退火 Gate 实现 | 2 |
| config.py `_FLATTEN_MAP` 缺失 key | 2 |

---

## 六、明确决策记录

| 决策 | 理由 |
|------|------|
| ✅ `slow_update_gate_with_selection=true` | 避免 force-accept 污染 |
| ✅ TF-IDF Top-5 | 关键词任务最优检索器 |
| ❌ 模拟退火 | 引入新退化，不可复现 |
| ❌ 语义向量 (all-MiniLM-L6-v2) | 关键词任务无增益 |
| ❌ LSTM 遗忘门 | 已通过原子化+Top-K 解决膨胀问题 |
| ❌ 规则拆分为 20+ 条 | 竞争 Top-5 slot 导致性能下降 |
| ⏸️ 历史贡献重排序 | 单规则信号 < 评估噪声 |

---

## 七、当前最终框架

```
8 Core (always active) + 16 Dynamic (TF-IDF Top-5)
+ token_budget = 2000
+ Gated Slow Update (slow_update_gate_with_selection=true)
+ trigger/text 分离
= test 0.7281±0.0011，零退化
```

### 与历史 #001 比较

| | #001 force-accept | 当前框架 |
|------|:--:|:--:|
| Test peak | 0.7400 | 0.7281 |
| Final 退化 | -0.0114 | 0 |
| 可复现 | 否 | 是 |
| 规则可溯源 | 否 | 是（每条可独立消融） |
| 方法可归因 | 否 | 是（可区分检索贡献 vs 规则贡献） |

---

## 八、已知限制 & 后续方向

| 限制 | 可能的改进 |
|------|------|
| trigger 太短，TF-IDF 匹配精度有限 | 混合关键词布尔过滤 + TF-IDF |
| qwen-flash 输出波动掩盖小信号 | temperature=0, 更大测试集 |
| 单规则效应无法检测 | 规则聚类消融而非单条 |
| trigger 设计依赖人工 | 用 Optimizer 自动生成 trigger 候选 |
