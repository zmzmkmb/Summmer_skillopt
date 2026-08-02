# 暑期实训项目结项总报告

> **项目**: 基于 SkillOpt 的原子化技能自演化与多目标规则选择研究
>
> **时间**: 2026-07-13 ~ 2026-07-27（修订 2026-08-02）
>
> **仓库**: https://github.com/zmzmkmb/Summmer_skillopt
>
> **结项版本**: `summer-project-final-v1.1` (commit `2735a65`)

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

### MOAR 对照实验（1400 题, SearchQA 全量 test, 2026-07-27）

| 方法 | Accuracy | 动态规则字符数 | 完整系统 Prompt 字符数 |
|------|:--:|:--:|:--:|
| Core Only | 62.79% | 0 | 513 |
| TF-IDF Top-5 | 66.86% | ~1,405 | ~1,918 |
| **MOAR (原型)** | **69.07%** | ~1,599 | ~2,112 |

> 2,000-character 预算仅作用于检索得到的动态规则拼接部分，不包含 Core 规则和系统提示模板。
> 因此完整系统 Prompt 可超过 2,000 字符。两者均未突破各自的预期范围。

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

1. **MOAR 规则库规模**: 当前仅测试 8 条动态规则，NSGA-II 的规模优势未被验证
2. **规则效用归因**: 所有同批次选中规则共享相同 credit
3. **Fast/Slow 消融**: 四组正式对比尚未完成（仅小规模验证）
4. **SpreadsheetBench**: 仅完成基线，训练未进行
5. **实验复现**: 不同实验使用了不同 adapter 版本和参数
6. **统计显著性**: 多数实验为单次运行，缺乏多 seed 置信区间

---

## 七、后续期刊计划

### 论文方向

> **Online Multi-Objective Atomic Rule Retrieval for Evolving LLM Agent Skills**

### 待完成工作（按优先级）

1. ~~修正 MOAR token 预算约束、效用归因和规则稳定 ID~~（v1.1 已完成预算统一）
2. 完成 Fast/Slow 四组消融（至少 MMLU-Pro 3 domain × 3 seed）
3. 完成 TF-IDF / BM25 / Greedy / Exact / MOAR 公平比较
4. 扩大规则库规模（16→50→100→200→500）
5. 四目标消融表
6. 完成 SpreadsheetBench 训练循环
7. 跨任务 Non-Regression Gate
8. 最终多 seed 正式实验 + 统计报告

### 目标期刊

目标为人工智能、智能系统或软计算方向的 JCR 三区/四区期刊。具体投稿期刊根据投稿年度最新分区、收稿范围及实验完成度综合确定。

---

## 八、版本信息

| 项目 | 值 |
|------|:--|
| 结项 commit | `2735a65` (main HEAD, 2026-08-02) |
| Python | 3.11.9 |
| Target 模型 | qwen-flash (DashScope, `2026-07-27`) |
| Optimizer 模型 | deepseek-v4-flash (DeepSeek, `2026-07-27`) |
| 关键配置 | `configs/searchqa/default.yaml`, `configs/mmlupro/default.yaml`, `configs/_base_/default.yaml` |
| 测试命令 | `pytest tests/ -v` |
| 结果目录 | `outputs/` (实验输出), `reports/` (报告), `logs/` (运行日志) |
