# 暑期实训项目结项总报告

> **项目**: 基于 SkillOpt 的原子化技能自演化与多目标规则选择研究
>
> **时间**: 2026-07-13 ~ 2026-07-27（v1.1 修订: 2026-08-02）
>
> **仓库**: https://github.com/zmzmkmb/Summmer_skillopt
>
> **结项版本**: `summer-project-final-v1.1` (commit `b6ac2a7`)

---

## v1.1 修订说明（2026-08-02）

> v1.0 提交后，以下问题已在 v1.1 中修复。标记为 ~~删除线~~ 的限制项不再适用。

| 修复项 | v1.0 状态 | v1.1 状态 |
|------|------|------|
| `--seed` 传入 MOAR | 硬编码 42 | 通过 `_make_query_seed(base_seed, query)` 参与每 query 随机种子 |
| 预算计量统一 | NSGA-II 用 token，拼接用字符 | `_text_cost()` 统一，TF-IDF/MOAR/BM25/Greedy 全部使用同一 cost 函数 |
| API 错误静默处理 | `except Exception: resp=""` | 结构化错误信息 + 1% 阈值保护 |
| 规则计数 | `count("## ")` 遗漏 `###` | `len(selected_indices)` 结构化计数 |
| MOAR CLI 参数化 | 硬编码 pop=30, gen=15 | `--moar-pop-size` 等全参数 CLI + 写入结果 JSON |
| NSGA-II Top-K 约束 | 无硬性 Top-K | `_repair_topk()` + `_constraint_violations()` 双重保证 |
| 真实 tokenizer | `len(rule_text)` 字符估算 | 默认 `tiktoken cl100k_base`，FeatureCache + MOARMemory 全程 token 计数 |
| 规则效用持久化 | 无跨运行持久化 | `UtilityTracker` 按规则文本 hash 做 JSON 持久化 |
| MOAR delivered indices | `_last_selections` 记录原始选择 | `_concat_rules` 返回 `(text, delivered)`，`_last_selections` 存实际拼接成功的规则 |
| Streamlit 展示视频 | YouTube iframe 嵌入 | 占位保留，视频已移除 |

---

## 一、项目目标

基于 Microsoft SkillOpt 框架，研究：

1. LLM Agent 技能的自动化演化（反思-聚合-选择-更新循环）
2. 原子化规则库的构建与检索（Core + Dynamic 双层架构）
3. 有限上下文预算下的最优规则子集选择问题
4. 跨领域技能迁移的有效性与限制

---

## 二、原始方法问题诊断

在复现 SkillOpt 的过程中，发现并修复了以下问题：

| # | 问题 | 影响 | 修复 |
|:--:|------|------|:--:|
| 1 | `slow_update_gate_with_selection=false` | Gate 强制 accept 但不更新分数 → 假停滞 | 启用 selection-set 验证 |
| 2 | Metropolis 退火引入退化路径 | 接受劣化解 → 性能随机波动 | 回归严格 Gate |
| 3 | 粗粒度 RAG 是噪声源 | 动态规则以"大段文本"形式检索无效 | 原子化：trigger/text 解耦 |
| 4 | MMLU-Pro analyst 输出协议不兼容 | 180 步全部 zero patches | 修正 `analyst.md` 输出 schema |
| 5 | MMLU-Pro rollout 不写轨迹上下文 | Analyst 只看到答案字母 | 补全 context 写入 |
| 6 | Math test=0% | 351 条全部 API 连接失败 | 诊断 + 重新 eval |

其中 4-6 是 7月27日代码审查发现的关键 pipeline bug，修复后 step-level optimizer 确认有效（Philosophy step 1 gate accept, test +5.60pp）。

---

## 三、主要技术改进

### 3.1 训练框架修复与验证

- **Gate 机制修复**: Gated Slow Update 使用 selection-set 验证，避免滚动平均引入的假停滞
- **退火局限性分析**: 证明 Metropolis 退火有效但引入新退化路径，回归严格 Gate
- **Fast/Slow 双时间尺度发现**: 修复 pipeline bug 后，step-level fast update 与 epoch-level slow update 均确认有效

### 3.2 原子化规则库

```
8 Core（始终激活）: output format, safety, all-clue matching, answer type,
                     phrase completion, inference, 等
16 Dynamic（检索式）: extraction, disambiguation, entity normalization,
                      question types, special patterns, 等
+ trigger/text 解耦
+ TF-IDF Top-5 检索
+ relevance-rank order
= 零退化，完全可复现
```

### 3.3 多领域适配

实现了三个独立的环境 adapter：

| 任务族 | Adapter | 领域 | 特点 |
|------|------|------|------|
| Factual QA | SearchQA | 百科问答 | 4 选 1, 文本提取 |
| Knowledge Reasoning | MMLU-Pro | Math/Law/History/Philosophy | 10 选 1, 纯格式 prompt |
| Tool-Execution | SpreadsheetBench | 电子表格操作 | openpyxl 代码生成 + 执行 |

### 3.4 MOAR: 多目标原子规则选择（扩展原型）

基于 NSGA-II 的多目标进化算法，同时优化：
- 查询相关性、历史效用、上下文成本、规则冗余
- 在 token 预算约束下进行 Pareto 优化
- 35 个子模块测试通过，训练管线完整集成

> **状态**: 方法原型已完成。大规模基准验证作为后续期刊研究工作。

---

## 四、实验结果

> ⚠️ 以下结果来自不同实验阶段、不同 adapter 版本、不同数据规模。正式论文需在统一条件下重现。

### SearchQA 正式实验（8C+16D, TF-IDF Top-5, 3 轮重复推理）

| 版本 | 方法 | Test Accuracy |
|------|------|:--:|
| Phase 2 | 6C+18D, text-only TF-IDF | **0.7386 ± 0.0037** |
| Phase 3 | 8C+16D, expanded-trigger TF-IDF | **0.7376 ± 0.0036** |
| Baseline | No Skill | ~0.4170 |
| Baseline | Full Skill | ~0.7350 |

### MMLU-Pro 探索性结果（SearchQA adapter 复用，2026-07-25~26）

| 领域 | 基线→峰值 (val) | 提升 | 备注 |
|------|:--:|:--:|------|
| Math | 89.0%→92.5% | +3.5pp | +63% 模板增益，天花板接近 |
| History | 61%→68.4% | +7pp | 有效但空间有限 |
| Law | 43.0%→45.5% | +2.5pp | 最接近 SearchQA 甜区间 |
| Philosophy | 63%→72.0% | +9pp | 有效但空间有限 |

### 管线修复验证（纯 MMLU-Pro adapter, 2026-07-27）

| 领域 | 基线 test | 最佳 test | 提升 | 改进来源 |
|------|:--:|:--:|:--:|------|
| Law | 34.42% | 38.41% | **+3.99pp** | Epoch-level slow update |
| Philosophy | 56.80% | 66.40% | **+9.60pp** | Fast + slow update |
| Math | 88.03% | 89.46% | **+1.43pp** | Epoch-level slow update (天花板) |

> Philosophy 首个 step-level gate accept（修复 pipeline bug 后）：单步 test +5.60pp。后续慢更新完成了进一步的技能整合。
> 由于尚未进行 Fast-only 与 Slow-only 的严格消融实验，目前无法精确分解二者对最终 9.60pp 增益的独立贡献。

### SpreadsheetBench 基线（2026-07-25）

| 指标 | 值 |
|------|:--:|
| Mean hard (400 题) | 0.355 |
| Mean soft | 0.570 |
| 执行成功率 | ~62% |
| 完美率 (≥99%) | ~32% |
| 训练状态 | 未接入 SkillOpt 训练循环 |

### MOAR 对照实验（早期探索，1400 题 × 1 seed, 2026-07-27）

| 方法 | Accuracy | 动态规则字符数 | 说明 |
|------|:--:|:--:|------|
| Core Only | 62.79% | 0 | 仅核心规则 |
| TF-IDF Top-5 | 66.86% | ~1,405 | 字符预算，早期版本 |
| **MOAR (原型)** | **69.07%** | ~1,599 | pop=30, gen=15 |

> 早期实验使用字符预算 `len()` 截断。v1.1 已统一为 `tiktoken` token 预算。

### MOAR 正式实验（200 题 × 3 seeds, SearchQA test, qwen-flash, 2026-07-29）

| 方法 | Acc +/- SD | 规则数 | Sel Tokens | 检索延迟 | 预算违规 |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 63.00% +/- 0.50% | 0 | 0 | 0ms | 0 |
| TF-IDF Top-5 | 67.00% +/- 1.00% | 0* | 0* | ~1ms | 0 |
| **MOAR (NSGA-II)** | **70.67% +/- 0.29%** | 5.0 | ~1918 | ~300ms | 0 |
| BM25 | 72.50% +/- 0.50% | 4.5 | ~1947 | ~2ms | 极少量边界 |
| Greedy-Cold | 71.50% +/- 0.50% | 5.0 | ~1207 | ~3ms | 0 |
| Greedy-Utility | 71.67% +/- 0.29% | 5.0 | ~1204 | ~3ms | 0 |

> \* TF-IDF selected_indices 未在原始 formal run 中保存（v1.1 已修复）。
> NSGA-II 配置: pop=30, gen=15, 2000-token budget (tiktoken cl100k_base)。
>
> **配对 McNemar**: MOAR vs TF-IDF p=0.0012 (significant), MOAR vs BM25 p=0.050 (borderline)。
> **规则稳定性**: MOAR 跨 seed Jaccard = 0.999（极端稳定）。
> **详见**: [report #014](reports/report_014_moar_comparison.md) 和 [artifacts/jos_experiment_v1/](artifacts/jos_experiment_v1/)。

---

## 五、工程成果

| 成果 | 详情 |
|------|------|
| 代码 | ~5000 lines 新增/修改（Python） |
| 配置 | 结构化 YAML + CLI override，3 个 adapter |
| 测试 | 60+ 单元测试/集成测试通过（MOAR 35, MMLU-Pro 26） |
| 文档 | 14 篇正式报告 + 研究日志 |
| 版本控制 | 20 个有意义的 commit，完整 Git 历史 |
| 环境 | Windows 10, Python 3.11, qwen-flash + deepseek-v4-flash |
| 实验追踪 | 所有实验输出保存在 `outputs/`，日志在 `logs/` |

---

## 六、已知限制

以下为 v1.1 修订后仍然存在的限制：

1. **MOAR 规则库规模**: 当前仅测试 8 条动态规则，NSGA-II 的规模优势未被验证
2. **规则效用归因**: 所有同批次选中规则共享相同 credit（尚未实现逐规则独立归因）
3. **Fast/Slow 消融**: 四组正式对比尚未完成（仅小规模验证）
4. **SpreadsheetBench**: 仅完成基线，训练未进行
5. **实验复现**: 不同实验使用了不同 adapter 版本和参数
6. **统计显著性**: 除 MOAR 200×3seed 外，多数实验为单次运行

> 以下 v1.0 中的限制已在 v1.1 中解决，不再适用：
> - ~~没有 Top-K 硬约束~~ → NSGA-II 已有 `_repair_topk()` + constraint violation 双重保证
> - ~~使用字符数而非 tokenizer~~ → 默认 `tiktoken cl100k_base`，`_text_cost()` 统一计量
> - ~~规则效用缺少稳定 ID 和持久化~~ → `UtilityTracker` 按规则文本 hash 做 JSON 持久化

---

## 七、后续期刊计划

### 论文方向

> **Online Multi-Objective Atomic Rule Retrieval for Evolving LLM Agent Skills**

### 待完成工作（按优先级）

1. ~~修正 MOAR token 预算约束、效用归因和规则稳定 ID~~（v1.1 已完成：Top-K、tokenizer、持久化全部到位）
2. ~~完成 TF-IDF / BM25 / Greedy / Exact / MOAR 公平比较~~（v1.1 已完成 200×3seed 六方法对比）
3. 完成 Fast/Slow 四组消融（至少 MMLU-Pro 3 domain × 3 seed）
4. 扩大规则库规模（8→16→50→100→200）
5. 四目标消融表
6. 完成 SpreadsheetBench 训练循环
7. 跨任务 Non-Regression Gate
8. 最终大规模多 seed 正式实验 + 统计报告

### 目标期刊

目标为人工智能、智能系统或软计算方向的 JCR 三区/四区期刊。具体投稿期刊根据投稿年度最新分区、收稿范围及实验完成度综合确定。

---

## 八、版本信息

| 项目 | 值 |
|------|:--|
| 结项 commit | `b6ac2a7` (main HEAD, 2026-08-02) |
| Python | 3.11.9 |
| Target 模型 | qwen-flash (DashScope, `2026-07-27`) |
| Optimizer 模型 | deepseek-v4-flash (DeepSeek, `2026-07-27`) |
| 关键配置 | `configs/searchqa/default.yaml`, `configs/mmlupro/default.yaml`, `configs/_base_/default.yaml` |
| 测试命令 | `pytest tests/ -v` |
| 结果目录 | `outputs/` (实验输出), `reports/` (报告), `logs/` (运行日志) |
