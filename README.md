# SkillOpt — Task-Context-Aware Dual-Timescale Skill Optimization

> **Target**: Factual QA, Knowledge Reasoning, and Tool-Execution Tasks
>
> 基于 Microsoft SkillOpt 的独立研究分支，探索原子化规则记忆、双时间尺度更新与跨领域技能迁移。

## 当前进展

| 任务族 | 领域 | 基线→最佳 test | 提升 | 状态 |
|------|------|:--:|:--:|:--:|
| **Factual QA** | SearchQA | 41.7%→73.9% | +31.8pp | ✅ 验证完成 |
| **Knowledge Reasoning** | MMLU-Pro Law | 34.4%→38.4% | +4.0pp | ✅ 验证完成 |
| **Knowledge Reasoning** | MMLU-Pro Philosophy | 56.8%→66.4% | +9.6pp | ✅ 验证完成（含 fast+slow） |
| **Knowledge Reasoning** | MMLU-Pro Math | 88.0%→89.5% | +1.5pp | ✅ 天花板接近 |
| **Knowledge Reasoning** | MMLU-Pro History | 61%→68.4% | +7pp | ✅ 旧 adapter 验证 |
| **Tool-Execution** | SpreadsheetBench | 35.5% baseline | — | 🔄 基线测完，训练待接入 |

### 最新里程碑（2026-07-27）

- ✅ **修复 MMLU-Pro pipeline 两个关键 bug**（analyst 输出协议 + trajectory 上下文缺失）
- ✅ **Step-level optimizer 确认有效**（修复后每步 3-4 patch，Philosophy step 1 gate accept）
- ✅ **Fast + slow update 双时间尺度验证**（report #013）
- ✅ **Unit tests**: 26 pass, evaluator / analyst schema / trajectory context

## 做了什么

1. **搭建 MMLU-Pro 独立 adapter** — 纯格式约束，不依赖 SearchQA 模板
2. **发现并修复两个 pipeline bug** — analyst 协议不兼容 + trajectory 上下文缺失
3. **验证 fast/slow 双时间尺度更新** — step-level patches + epoch-level slow_update
4. **多领域跨领域验证** — 6 domains, SearchQA + MMLU-Pro (Math/Law/History/Philosophy) + SpreadsheetBench
5. **原子化规则检索** — 8 Core + 16 Dynamic，trigger/text 解耦，TF-IDF Top-5 检索

---

# Archived: SearchQA Summer Project (2026-07-24 ~ 07-26)

> 以下为暑期实训期间的 SearchQA 原子化检索实验归档。当前研究方向已转向多任务族双时间尺度优化。

## 核心结果

| 版本 | 方法 | Test |
|------|------|:--:|
| Phase 2 (性能最优) | 6C+18D, text-only TF-IDF | **0.7386 ± 0.0037** |
| Phase 3 (架构规范) | 8C+16D, expanded-trigger TF-IDF, trigger/text 解耦 | **0.7376 ± 0.0036** |

> 两版本差值 0.0010 处于 qwen-flash 输出波动范围内（std≈0.003）。Phase 3 在保持性能的同时实现检索触发与执行规则解耦。

## 最终框架

```
8 条 Core（始终激活）：output format, safety, all-clue matching, answer type, phrase completion, inference
16 条 Dynamic（TF-IDF Top-5 检索）：extraction, disambiguation, entity normalization, question types, special patterns
+ 2000-character instruction budget
+ Gated Slow Update (slow_update_gate_with_selection=true)
+ relevance-rank order retrieval
= 零退化，完全可复现
```

## 快速入口

```bash
# 复现最终结果（1400 条 test，3 次重复推理）
python scripts/retrieval_ablation.py \
  --split valid_unseen --limit 0 --methods tfidf \
  --top-k 5 --budget 2000 --n-seeds 3 --workers 48

# 查看规则
cat skillopt/rule_atomizer.py
```

| 文件 | 说明 |
|------|------|
| `reports/report_008_final.md` | 结项报告 |
| `reports/report_005_atomized_ablation.md` | 原子化消融 + 多 run 验证 |
| `reports/report_002_slowupdate_comparison.md` | Gate 假停滞诊断 |
| `skillopt/rule_atomizer.py` | 原子规则库 (8C+16D) |
| `scripts/retrieval_ablation.py` | 推理消融脚本 |
| `artifacts/final_results.csv` | 逐题预测结果 |
| `artifacts/run_manifest.json` | 运行配置记录 |

## 明确结论

| ✅ 做 | ❌ 不做 |
|------|------|
| 原子化规则库 + Core/Dynamic 分离 | LSTM 遗忘门 |
| TF-IDF Top-5 检索 | 模拟退火 |
| trigger/text 解耦 | Boolean 硬过滤 / 双通道软融合 / 关键词加分 |
| gated slow update | 语义向量 (all-MiniLM-L6-v2 无增益) |

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
