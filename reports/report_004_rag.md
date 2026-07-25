# SkillOpt 训练报告 #004 — RAG 规则检索实验

> 日期：2026-07-25 | 分支：`main` | 对比 #001, #002, #003, #004

---

## 一、动机

前三轮实验中，skill 从 104 字符膨胀到 ~10,000 字符，全部规则在每次 rollout 中被塞进 system prompt。这导致三个问题：

1. **Prompt 膨胀** — token 消耗线性增长（#002 用了 63M, #003 用了 90M）
2. **规则冲突** — 矛盾规则同时可见（如"用全名" vs "用最短形式"）
3. **注意力稀释** — 与当前 query 无关的规则干扰模型

本实验引入 **RAG 式向量检索**，在推理时根据 query 动态选择 Top-K 最相关规则，而非全部注入。

---

## 二、架构

```
Optimizer → Skill Markdown → RuleMemory
                               ├─ Core Rules (always active)
                               └─ Dynamic Rules (TF-IDF 嵌入)
                                    ↓
                              Per-query retrieval
                                    ↓
                              Core + Top-K → Active Skill → Target Model
```

### 实现（5 个文件）

| 文件 | 改动 |
|------|------|
| `skillopt/rag_rule_selector.py` | **新建**：`Rule` dataclass + `RuleMemory`（解析/分类/TF-IDF/检索） |
| `skillopt/envs/searchqa/rollout.py` | `_build_active_skill()` 按 query 动态构建；`process_one()` + `run_batch()` 接受可选 `rule_selector` |
| `skillopt/envs/searchqa/adapter.py` | `rollout()` 通过 `**kwargs` 透传 `rule_selector` |
| `skillopt/engine/trainer.py` | `_build_rule_selector()` 辅助函数；训练和评估 rollout 传参 |
| `skillopt/config.py` | 新增 4 个 key: `use_rag`, `rag_top_k`, `rag_method`, `rag_token_budget` |

### 零新依赖

`sklearn` (TfidfVectorizer + cosine_similarity) + `numpy` 已安装，无需下载。

---

## 三、实验设计

| | #001 baseline | #002 gated | #003 退火 | **#004 RAG** |
|------|:--:|:--:|:--:|:--:|
| **Optimizer** | deepseek-v4-flash | deepseek-v4-flash | deepseek-v4-flash | deepseek-v4-flash |
| **Target** | qwen-flash | qwen-flash | qwen-flash | qwen-flash |
| **slow_update_gate** | force-accept | gated | gated | **gated** |
| **use_annealing** | false | false | T0=0.02 | **false** |
| **use_rag** | false | false | false | **true (top_k=5, budget=2000)** |

---

## 四、核心结果

| | #001 | #002 | #003 | **#004** |
|------|:--:|:--:|:--:|:--:|
| **Best val** | 0.7350 | 0.7200 | 0.7300 | **0.7300** |
| **Best test** | 0.7400 | 0.7157 | 0.7214 | **0.7250** |
| **Final test** | 0.7286 | 0.7157 | 0.7107 | **0.7250** |
| **退化** | -0.0114 🚫 | 0 ✅ | -0.0107 🚫 | **0** ✅ |
| **Total Accept** | 4 | 6 | 6+5退火 | **5** |
| **Total Token** | 32M | 63M | 90M | **31M** |
| **耗时** | 1,795s | 4,309s | 37,818s | **7,251s** |

---

## 五、每 Epoch Gate 行为

```
Epoch │ Accept │ Reject │ Skip │     Best      │
──────┼────────┼────────┼──────┼───────────────┤
  1   │   3    │   7    │  0   │ 0.6900        │
  2   │   2    │   8    │  0   │ 0.7050        │
  3   │   0    │  10    │  0   │ 0.7200        │
  4   │   0    │   7    │  3   │ 0.7300        │
──────┼────────┼────────┼──────┼───────────────┤
 合计 │   5    │  32    │  3   │ 0.7300        │
```

### 关键跳跃点

| Step | 事件 | 说明 |
|------|------|------|
| 20→21 | 0.7050→0.7200 | Epoch 2→3 slow update (gated) 注入了有效的纵向 guidance |
| 30→31 | 0.7200→0.7300 | Epoch 3→4 slow update (gated) 再次提升 |

两次 slow update 都经过了 Gate 验证，没有 force-accept 污染。

---

## 六、RAG 效果分析

### 6.1 Prompt 压缩

RAG 模式下每条 query 注入的规则体积：

```
Full skill:        ~10,000 字符
RAG active skill:  ~2,000 字符 (core + top-5 dynamic)
压缩比:            80%
```

对应 token 消耗从 63M (#002) → 31M (#004)，减半。

### 6.2 规则解析质量

使用 `searchqa_gated_slowupdate/best_skill.md`（5 个 section）测试：

```
### 1. Direct Answer Extraction         → DYN
### 2. Phrase Matching                   → DYN
### 3. Multi-Document Filtering          → DYN
### 4. Confirmation with Sources         → DYN
### 5. Concise Answer Format             → CORE
```

分类合理：前 4 条是内容相关的动态规则，第 5 条（包含 `<answer>` 标签要求）被正确标记为核心规则。

### 6.3 和退火对比

| | #003 退火 | #004 RAG |
|------|:--:|:--:|
| Best test | 0.7214 | **0.7250** |
| Final 退化 | -0.0107 | **0** |
| Token | 90M | **31M** |
| 机制 | 全局随机探索 | **每 query 精准选择** |

RAG 在更低成本下拿到了更好的结果，且没有退火的退化风险。

---

## 七、四跑排名

| 排名 | 实验 | Test best | Final 退化 | Token | 推荐？ |
|------|------|:--:|:--:|:--:|------|
| 🥇 | **#005 原子化** | 0.7386 | **0** | — | ✅🏆 最终推荐 |
| 🥈 | #006 Core Only (训练) | 0.7336 | 0 | — | ✅ 规则贡献清晰 |
| 🥉 | #004 RAG (粗粒度) | 0.7250 | 0 | 31M | ⚠️ 已过时 |
| 4 | #002 gated | 0.7157 | 0 | 63M | ✅ 保守选择 |
| 5 | #003 退火 | 0.7214 | -0.0107 | 90M | ⚠️ |
| — | #001 force-accept | 0.7400 | -0.0114 | 32M | ❌ 不可复现 |

> 注：#004 的"最佳配置"结论已过时。原子化后的推理消融 (#005) 达到 0.7386，且规则可独立计分。

---

## 八、已知限制

1. **Core rules still large** — 规则分类后，core 部分本身仍有 ~5,700 字符（来自 `### 5. Concise Answer Format` section 的巨大体量）。这需要优化规则原子化粒度
2. **TF-IDF is keyword-only** — 不支持语义相似度（"company" 不会匹配 "corporation"）。后续可用 ChromaDB 内置 `all-MiniLM-L6-v2` 升级
3. **RAG 不影响训练优化** — RAG 只在 rollout 推理时生效，Optimizer 仍然看到完整 skill。后续可在 reflect 阶段也注入 RAG
4. **Token budget 是硬截断** — 2000 字符可能对某些 query 不够，应改为动态预算

---

## 九、结论

1. **RAG 有效但粗粒度拖后腿** — 动态规则只有 4 个大段，检索无法精确选择
2. **RAG 比退火更有效** — 每 query 精准选规则胜过全局随机探索
3. **Prompt 减半** — 从 10,000 → 2,000 字符/query，token 消耗减半
4. **后续 #005 证明关键瓶颈是规则粒度** — 原子化后 TF-IDF 从 0.7250 跃升至 0.7386
5. **此文结论已被 #005 替代** — 详见 `report_005_atomized_ablation.md`
