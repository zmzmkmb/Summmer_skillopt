# SkillOpt — LLM Agent 技能自演化与多目标规则选择

> 暑期实训项目 | 2026-07-13 ~ 2026-07-27
>
> 基于 Microsoft SkillOpt，研究原子化规则记忆、双时间尺度更新、多领域技能迁移与多目标规则选择。
>
> **结项报告**: [SUMMER_FINAL_REPORT.md](SUMMER_FINAL_REPORT.md)

---

## 实验结果总览

> ⚠️ 以下结果来自不同实验阶段、adapter 版本和数据规模。各表内部条件一致，**表间不可直接横比**。

### ① SearchQA 正式实验（8C+16D, TF-IDF Top-5, 3 轮重复）

| 方法 | Test Accuracy | 备注 |
|------|:--:|------|
| No Skill | ~0.4170 | 基线 |
| Full Skill | ~0.7350 | 13k+ chars |
| Phase 2 (6C+18D, text-only TF-IDF) | **0.7386 ± 0.0037** | 性能最优 |
| Phase 3 (8C+16D, trigger/text 解耦) | **0.7376 ± 0.0036** | 架构规范 |

### ② MMLU-Pro 探索性结果（SearchQA adapter 复用）

| 领域 | 基线 val | 最佳 val | 提升 | 说明 |
|------|:--:|:--:|:--:|------|
| Math | 89.0% | 92.5% | +3.5pp | +63% 模板增益，天花板接近 |
| History | 61.0% | 68.4% | +7pp | 有效 |
| Law | 43.0% | 45.5% | +2.5pp | 甜区间 |
| Philosophy | 63.0% | 72.0% | +9pp | 有效 |

### ③ 管线修复验证（纯 MMLU-Pro adapter, 修复后, 2026-07-27）

| 领域 | test 基线 | test 最佳 | Δ | 改进来源 |
|------|:--:|:--:|:--:|------|
| Philosophy | 56.80% | **66.40%** | **+9.60pp** | Step-level accept + slow update |
| Law | 34.42% | 38.41% | +3.99pp | Slow update |
| Math | 88.03% | 89.46% | +1.43pp | Slow update (天花板) |

> **Philosophy step 1 首次 gate accept**: pipeline bug 修复后单步 test +5.60pp。所有增益来自 epoch-level slow update。

### ④ SpreadsheetBench 基线

| 指标 | 值 | 状态 |
|------|:--:|:--:|
| 400 题 Mean hard | 0.355 | 基线完成 |
| 执行成功率 | ~62% | — |
| 训练循环 | 未接入 | 后续工作 |

### ⑤ MOAR: 多目标原子规则选择（扩展原型）🆕

| 方法 | Test Accuracy (1400 题) | 说明 |
|------|:--:|------|
| Core Only | 62.79% | 仅 1 条核心规则 |
| TF-IDF Top-5 | 66.86% | 当前基线 |
| **MOAR (NSGA-II)** | **69.07%** | 原型，待正式验证 |

> **MOAR 状态**: 方法原型已完成（34 个子模块测试通过，训练管线集成）。当前仅测试了 8 条动态规则——大规模规则库 + 多 seed 验证作为后续期刊工作。详见 [report #014](reports/report_014_moar_comparison.md)。

---

## 主要技术工作

1. **Gate 修复 + 退火分析**: 发现并修复 validation gate 假停滞，证明 Metropolis 退火局限性
2. **原子化规则库**: 8C+16D, trigger/text 解耦, TF-IDF Top-5 检索 — 零退化
3. **Pipeline bug 修复** (2026-07-27): analyst 输出协议不兼容 + trajectory 上下文缺失 — 修复后 step-level optimizer 确认有效
4. **MMLU-Pro 独立 adapter**: 纯格式约束，不依赖 SearchQA 模板
5. **多领域验证**: SearchQA + MMLU-Pro (Math/Law/History/Philosophy) + SpreadsheetBench
6. **MOAR 原型**: NSGA-II 多目标进化算法，同时优化相关性/效用/成本/冗余
7. **测试**: 60+ tests pass (MOAR 34, MMLU-Pro 26)

## 快速入口

```bash
# 复现 SearchQA 最终结果
python scripts/retrieval_ablation.py --split valid_unseen --limit 0 --methods tfidf

# MOAR 对照实验
python scripts/moar_searchqa_eval.py --skill outputs/searchqa_rag/best_skill.md --limit 500

# 运行所有测试
pytest tests/ -v
```

---

## 基于的原始项目

> 以下为 Microsoft SkillOpt 原始 README。
# SkillOpt: Executive Strategy for Self-Evolving Agent Skills

*Train agent skills like you train neural networks — with epochs, (mini-)batchsize, learning rates, and validation gates — but without touching model weights.*

[![Project Page](https://img.shields.io/badge/Project%20Page-SkillOpt-8dbb3c)](https://microsoft.github.io/SkillOpt/) [![Paper](https://img.shields.io/badge/Paper-arXiv-b31b1b)](https://arxiv.org/abs/2605.23904) [![Project Video](https://img.shields.io/badge/Project%20Video-Watch%20Demo-ff0000)](https://youtu.be/JUBMDTCiM0M) [![PyPI](https://img.shields.io/badge/PyPI-skillopt-green.svg)](https://pypi.org/project/skillopt/) [![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/38498?utm_source=trendshift-badge&utm_medium=badge&utm_campaign=badge-trendshift-38498" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/38498/daily?language=Python" alt="microsoft%2FSkillOpt | Trendshift" width="250" height="55"/></a>
  <a href="https://trendshift.io/repositories/38498?utm_source=trendshift-badge&utm_medium=badge&utm_campaign=badge-trendshift-38498" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/38498/weekly?language=Python" alt="microsoft%2FSkillOpt | Trendshift" width="250" height="55"/></a>
</p>

> 📖 **For installation, data preparation, training/eval commands, configuration, and framework internals, start with the versioned [SkillOpt documentation](https://github.com/microsoft/SkillOpt/blob/main/docs/index.md). A concise rendered overview is available in the [Documentation & Reproduction Guide](https://microsoft.github.io/SkillOpt/docs/guideline.html), and longer-form engineering analysis appears on the [Technical Blog](https://microsoft.github.io/SkillOpt/blog/). We also maintain a [Changelog](CHANGELOG.md) for released and unreleased changes.**

---

## News 🔥🔥🔥
- **[2026-07-02]** 🚀 **SkillOpt [v0.2.0](https://github.com/microsoft/SkillOpt/releases/tag/v0.2.0) is out on [PyPI](https://pypi.org/project/skillopt/)!** Headline feature: **SkillOpt-Sleep**, a nightly offline self-evolution engine (harvest → mine → replay → consolidate behind a held-out validation gate), now shipped as the `skillopt-sleep` CLI. It also includes experimental multi-objective, replay, and dream-rollout controls; the main CLI keeps conservative defaults and does not expose every experiment-harness control as a flag. The release source adds integration shells for **Claude Code, Codex, Copilot, and Devin**, plus an **OpenClaw reference adaptation**; these plugin/MCP files live in the repository rather than the PyPI wheel. It also adds SearchQA split materialization, Windows robustness, and hardened JSON parsing. See the [release notes](https://github.com/microsoft/SkillOpt/releases/tag/v0.2.0) for full release details and contributor acknowledgements.
- **[2026-06-15]** 😴 **SkillOpt-Sleep (preview)** — a nightly offline self-evolution companion for local coding agents (Claude Code / Codex / Copilot): review past sessions, replay recurring tasks, and consolidate validated skills behind a held-out gate. See **[`docs/sleep/README.md`](docs/sleep/README.md)** for what it is, how to use it, and results.
- **[2026-06-03]** 🎉 **[gbrain](https://github.com/garrytan/gbrain), [gbrain-evals](https://github.com/garrytan/gbrain-evals/blob/main/docs/benchmarks/2026-06-03-skillopt.md), and [darwin-skill](https://github.com/alchaincyf/darwin-skill) have all integrated SkillOpt.**
- **[2026-06-02]** 🎉 **SkillOpt [v0.1.0](https://github.com/microsoft/SkillOpt/releases/tag/v0.1.0) is now available on [PyPI](https://pypi.org/project/skillopt/)!** Install with `pip install skillopt`. This initial release includes the full training loop (rollout → reflect → aggregate → select → update → evaluate), multi-backend support (OpenAI / Azure / Claude / Qwen / MiniMax), six built-in benchmarks, and WebUI dashboard.

---

## Overview

Modern agent skills are usually hand-crafted, generated one-shot by a strong
LLM, or evolved through loosely controlled self-revision — none of which
behaves like a deep-learning optimizer for the skill itself, and none of
which reliably improves over its starting point under feedback.

**SkillOpt treats the skill document as the trainable state of a frozen
agent**, and trains it with the discipline that makes weight-space
optimization reproducible. A separate optimizer model turns scored rollouts
into bounded add / delete / replace edits on a single skill document; in the
default paper-style path, a candidate edit is accepted only when it strictly
improves a held-out validation score. A textual learning-rate budget, a rejected-edit buffer,
and an epoch-wise slow / meta update make skill training stable while
adding **zero inference-time model calls** at deployment.

The deployed artifact is a compact `best_skill.md` (typically 300–2,000
tokens) that runs against the unchanged target model. Across **six
benchmarks, seven target models, and three execution harnesses** (direct
chat, Codex CLI, Claude Code CLI), SkillOpt is best or tied-best on **all
52 evaluated (model, benchmark, harness) cells** and on GPT-5.5 lifts the
average no-skill accuracy by **+23.5 points in direct chat, +24.8 inside
the Codex agentic loop, and +19.1 inside Claude Code**. Optimized skill
artifacts transfer across model scales, between Codex and Claude Code
harnesses, and to nearby benchmarks without further optimization.

For the full method, ablations, and per-cell results see the [paper](https://arxiv.org/abs/2605.23904); for a visual walkthrough of the loop see the [project page](https://microsoft.github.io/SkillOpt/); for deeper API / backend / benchmark docs see [`docs/`](docs/).

## 🎬 Demo Video

https://github.com/user-attachments/assets/eb12d3bc-371c-467f-904d-91b61f339ed7

<p align="center">
  <a href="https://youtu.be/JUBMDTCiM0M"><b>▶ Watch the full demo on YouTube</b></a>
</p>

---

## Extensibility & WebUI

### Adding a new backend

A backend = a chat / exec target (e.g. `openai_chat`, `claude_chat`,
`qwen_chat`, `minimax_chat`, `openai_compatible`, `codex_exec`,
`claude_code_exec`). If a provider implements the OpenAI Chat Completions
protocol, try the built-in `openai_compatible` backend before adding code. See
[`docs/guide/new-backend.md`](docs/guide/new-backend.md) for the full
contract; in short you add a `skillopt/model/<name>_backend.py` module,
register it in `skillopt/model/common.py` + `backend_config.py`, and wire
it through the router in `skillopt/model/__init__.py`. `qwen_backend.py`
and `minimax_backend.py` are good templates.

### Adding a new benchmark

A benchmark = a `skillopt/envs/<name>/` package with an adapter, a data loader,
a scored rollout helper, a YAML config, and optionally an initial seed skill.
See
[`docs/guide/new-benchmark.md`](docs/guide/new-benchmark.md) for the full
contract; the simplest reference is `skillopt/envs/searchqa/`.

### WebUI

Launch the monitoring dashboard (optional):

```bash
pip install -e ".[webui]"
python -m skillopt_webui.app
```

| Flag | Default | Description |
|---|---|---|
| `--port` | 7860 | Server port |
| `--host` | `0.0.0.0` | Bind address |
| `--share` | off | Create a public Gradio share link |

The default host listens on every network interface. Use
`--host 127.0.0.1` for local-only access.

---

## Citation

```bibtex
@article{yang2026skillopt,
  title={Skillopt: Executive strategy for self-evolving agent skills},
  author={Yang, Yifan and Gong, Ziyang and Huang, Weiquan and Yang, Qihao and Zhou, Ziwei and Huang, Zisu and Li, Yan and Gao, Xuemei and Dai, Qi and Liu, Bei and others},
  journal={arXiv preprint arXiv:2605.23904},
  year={2026}
}
```
