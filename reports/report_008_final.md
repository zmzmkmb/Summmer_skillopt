# SkillOpt 项目结项报告

> 日期：2026-07-24 ~ 07-26 | 分支：`main`
>
> 3 个阶段，8 份报告，6 轮完整训练，30+ 次推理消融

---

## 一、最终保留版本

### 性能最优版本（Phase 2）

```
6C + 18D, text-only TF-IDF Top-5
= 0.7386 ± 0.0037，零退化
```

### 架构规范版本（Phase 3）

```
8C + 16D, expanded-trigger TF-IDF Top-5, trigger/text 解耦
= 0.7360 ± 0.0034，零退化
```

两者差值 0.0026 在 qwen-flash 噪声范围（std≈0.003）内，可表述为：
> Phase 3 在基本保持 Phase 2 性能的同时，实现了检索触发文本与执行规则文本的解耦，提高了规则系统的可维护性和可扩展性。

---

## 二、完整实验链

| 阶段 | 关键发现 | 决策 |
|------|------|------|
| #001 baseline | test=0.7400，但 final 退化 -0.0114 | 发现假停滞 |
| #002 gated | 退化消失，峰值 0.7157 | ✅ 启用 gated slow update |
| #003 退火 | 5 次退火触发，final 退化 -0.0107 | ❌ 退火引入新退化 |
| #004 粗粒度 RAG | 0.7250，动态规则拖后腿 (-0.009) | 发现需要原子化 |
| #005 Random 对照 | TF-IDF > Random +0.006 | 确认检索有效 |
| #006 Core Only | 0.7336，核心规则是主要增益 | Core/Dynamic 分离 |
| — **原子化转折** — | — | — |
| A01-A03 | 原子化后 TF-IDF 0.7386±0.0037 | **原子化是关键前提** |
| A04-A05 | Top-3=0.7364, Top-8=0.7343 | Top-5 最优 |
| Semantic | 0.7310±0.0032 < TF-IDF | 关键词任务上语义无增益 |
| Leave-one-out | 0 条正贡献，Δ 全部 ≤ 噪声 | 单规则信号无法检测 |
| Phase 3 trigger | trigger/text 分离→0.7281 | 架构升级，性能小幅下降 |
| Expanded trigger | 0.7360±0.0034 | 追回 Phase 2 性能 |
| Dual-channel | 0.7329±0.0007 | 双通道不互补 |
| Keyword bonus | 0.7345±0.0039 | expanded trigger 已内含关键词 |

---

## 三、明确决策记录

| 决策 | 状态 | 依据 |
|------|:--:|------|
| `slow_update_gate_with_selection=true` | ✅ 永久 | 消除退化 |
| 原子化规则库 | ✅ 永久 | 决定性能的关键前提 |
| TF-IDF Top-5 | ✅ 当前最优 | 关键词任务 > Semantic |
| trigger/text 解耦 | ✅ 架构保留 | Phase 3 基线 |
| 模拟退火 | ❌ 废弃 | 引入新退化 |
| Boolean 硬过滤 | ❌ 废弃 | 损失召回 |
| 双通道软融合 | ❌ 废弃 | text 通道引入噪声 |
| 关键词软加分 | ❌ 废弃 | expanded trigger 已内含 |
| LSTM 遗忘门 | ⏸️ 无限期推迟 | 单规则信号 < 评估噪声 |
| 语义向量 | ⏸️ 保留方向 | 关键词任务当前不需要 |

---

## 四、检测极限

qwen-flash 在 1400 条 test set 上的输出波动 std ≈ 0.003（约 4 条题）。

这意味着：
- 方法间差异 < 0.003 无法稳定检测
- 单规则贡献 < 0.02 被噪声覆盖
- 连续微调检索器/权重已无意义

---

## 五、代码成果

| 类别 | 文件 | 说明 |
|------|------|------|
| 新模块 | `skillopt/rule_atomizer.py` | 原子化规则库（8C+16D，trigger/text 解耦） |
| 新模块 | `skillopt/rag_rule_selector.py` | 粗粒度 RAG（已过时，保留参考） |
| 新脚本 | `scripts/retrieval_ablation.py` | 推理消融：Core/Random/TF-IDF/Semantic/Dual/Keyword，多 seed + McNemar |
| 新脚本 | `scripts/rule_ablations.py` | Leave-one-out 规则消融 |
| 新脚本 | `scripts/stable_error_analysis.py` | 多 seed 稳定错误分析 |
| 新脚本 | `scripts/rule_utility_rerank.py` | 规则效用重排序（失败，保留为参考） |
| 核心修复 | 22 个文件 | Windows GBK → UTF-8 编码 |
| 新功能 | `skillopt/evaluation/gate.py` | `evaluate_gate_with_annealing()` + `compute_temperature()` |
| 配置扩展 | `skillopt/config.py` | 新增 8 个 `_FLATTEN_MAP` key |

---

## 六、未来工作

### 近期可做（检测极限允许的前提下）

- 更大测试集或更强 target 模型以降低噪声
- 规则触发条件进一步细化（每个 trigger 2-3 个判别样例词）
- 用 Optimizer (deepseek) 自动生成 trigger 候选

### 远期方向（规则库 > 100 条时可重新考虑）

> 当规则库扩展至数百条、积累充足的规则调用与收益轨迹后，可进一步引入基于时序状态的学习型门控机制，根据规则历史贡献、调用频次、冲突记录和任务相关性，自适应学习规则的写入、保留与激活权重。

### 方向性结论

当前最有价值的成果不是继续挤出约 0.001 的可能提升，而是**用完整消融证明了：原子化规则、Core/Dynamic 分层和 Query 级稀疏检索能够在降低 Token 与消除退化的同时，维持接近历史峰值的性能。**
