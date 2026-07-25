# 实验记录

| ID | 日期 | 代码分支 | 改动说明 | Optimizer | Target | Gate 最终分数 | 输出目录 | 备注 |
|----|------|---------|---------|-----------|--------|-------------|---------|------|
| 001 | 0724 | main | baseline: 原始 SkillOpt, SearchQA, slow_update_gate_with_selection=**false**(force-accept) | deepseek-v4-flash | qwen-flash | val 0.6200→0.7350, test 0.6336→0.7400, final 退化到 0.7286, 4 accept/29 reject/7 skip | `outputs/skillopt_searchqa_deepseek-chat_20260724_170800` | ⚠️ 假停滞：force-accept slow update 污染 current_skill |
| 002 | 0724 | main | **gated slow update**: slow_update_gate_with_selection=**true**, 其余同 #001 | deepseek-v4-flash | qwen-flash | val 0.6200→0.7200, test 0.6364→0.7157, final=best 零退化, 6 accept/34 reject/0 skip | `outputs/searchqa_gated_slowupdate` | ✅ 消除退化，Epoch 2&3 各多一个 accept，无假停滞 |
| 003 | 0725 | main | **模拟退火 Gate**: use_annealing=true, T0=0.02, gated slow update | deepseek-v4-flash | qwen-flash | val 0.6250→0.7300, test 0.6336→0.7214, final 退化到 0.7107, 6 accept+5 annealing/29 reject | `outputs/searchqa_annealing` | ⚠️ 退火有效（5次触发），但 Step 24 退火接受劣解后无法恢复，导致 final 退化 |
| 004 | 0725 | main | **RAG TF-IDF**: use_rag=true, method=tfidf, top_k=5, budget=2000, gated slow update | deepseek-v4-flash | qwen-flash | val 0.6200→0.7300, test 0.6321→**0.7250**, final=best 零退化, 5 accept/32 reject/3 skip, 31M token | `outputs/searchqa_rag` | ✅🏆 TF-IDF 检索有效 |
| 005 | 0725 | main | **RAG Random 对照**: use_rag=true, method=random, top_k=5, budget=2000 | deepseek-v4-flash | qwen-flash | val 0.6100→0.7300, test 0.6293→0.7193, final=best, 6 accept/34 reject, 34M token | `outputs/searchqa_rag_random` | 🔬 TF-IDF 领先随机 +0.0057，确认检索有增量收益 |
| 006 | 0726 | main | **RAG Core Only**: method=core_only, 无动态规则 | deepseek-v4-flash | qwen-flash | val 0.6050→**0.7350**, test→**0.7336**, final=best, Step 4 之后全部 reject | `outputs/searchqa_rag_coreonly` | 🔬 Core Only 训练分最高，但训练轨迹≠推理能力 |

---
## 推理消融 — 单次运行（固定原子化规则库，无训练，仅推理选择方式不同）

| ID | 方法 | Top-K | Test Hard | 说明 |
|------|------|:--:|:--:|------|
| A01 | Core Only | — | 0.7229 | 纯核心规则（6条） |
| A02 | Core + Random | 5 | 0.7379 | 随机选5条动态规则 |
| **A03** | **Core + TF-IDF** | **5** | **0.7400** | 🏆 原子化 RAG 最优 |
| A04 | Core + TF-IDF | 3 | 0.7364 | |
| A05 | Core + TF-IDF | 8 | 0.7343 | 太多规则=引入噪声 |

## 推理消融 — 3-Seed 稳定性验证

| 方法 | Mean±Std | Min | Max | vs Core Δ | McNemar p |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 0.7279±0.0026 | 0.7250 | 0.7300 | — | — |
| Random Top-5 | 0.7305±0.0023 | 0.7279 | 0.7321 | +0.003 | 不显著 |
| Semantic Top-5 | 0.7310±0.0032 | 0.7279 | 0.7343 | +0.003 | 不显著 |
| **TF-IDF Top-5** | **0.7386±0.0037** | 0.7364 | 0.7429 | **+0.011** | 与 Core Only 在部分 run 显著 |

> - TF-IDF 持续领先。语义向量 (all-MiniLM-L6-v2) 对关键词匹配任务反而不如 TF-IDF
> - Random 方差更大 (0.0054)，TF-IDF 更稳定
> - 目标模型输出波动 (std~0.003) 是主要噪声源
> - 已保存逐题结果到 `outputs/ablation_per_item.json`

> 结论：原子化（24条→6 core + 18 dynamic）是 RAG 生效的关键前提。TF-IDF 检索在 SearchQA 这类关键词匹配任务上最优，语义向量无额外增益。

## 规则级历史贡献评估

| ID | 方法 | 关键发现 |
|------|------|------|
| U01 | IDF 频率惩罚重排序 | 反向惩罚了高频通用规则 (R20-R24)，效果: **-0.0043** |
| U02 | Leave-one-out 逐条消融 (200 val) | 全部 18 条规则 Δ 在 **-0.020~0.000**，0 条正贡献。qwen-flash 噪声 (std~0.003) 覆盖了单规则信号 |

> 结论：当前 6C+18D 规则集已接近最优组合。单独移除/重排任何一条规则都无法产生可测增益。下一步应在**规则文本质量**而非规则选择上做优化。
