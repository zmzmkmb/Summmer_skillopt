# SkillOpt-Sleep 😴 — deployment-time companion (preview)

**SkillOpt-Sleep** applies SkillOpt's discipline to your *own daily usage*. It gives a
local coding agent a nightly **sleep cycle** that reviews your past sessions, replays
your recurring tasks on your own API budget, and consolidates what it learns into
**validated** long-term memory and skills — behind a held-out gate, staged for your
review. The agent gets better the more you use it, with **no weight training** and
**zero inference-time overhead**.

> **Preview.** This is an early preview we are actively iterating on; interfaces and
> defaults may change. The engine lives in the top-level [`skillopt_sleep/`](../../skillopt_sleep)
> package with **zero dependency** on the paper's `skillopt/` code (the validation gate
> is vendored).

## How it works

One "night":

```
harvest Claude Code / Codex transcripts → mine recurring tasks → replay offline
   → consolidate (reflect → bounded edit → GATE on real held-out tasks)
   → stage proposal → (you) adopt
```

It synthesizes **SkillOpt** (validation-gated bounded text edits), **Claude Dreams**
(offline consolidation; review-then-adopt), and the **agent-sleep** idea (short-term
experience → long-term competence).

## How to use it

One engine, thin per-agent shells (see [`plugins/`](../../plugins)):

| Platform | Folder | Install |
|---|---|---|
| **Claude Code** | [`plugins/claude-code`](../../plugins/claude-code) | `/plugin marketplace add ./plugins/claude-code` → `/skillopt-sleep` |
| **Codex** | [`plugins/codex`](../../plugins/codex) | `bash plugins/codex/install.sh` → `skillopt-sleep` skill |
| **Copilot** | [`plugins/copilot`](../../plugins/copilot) | register `plugins/copilot/mcp_server.py` as an MCP server |

Deterministic proof (no API key):
`python -m skillopt_sleep.experiments.run_experiment --persona researcher --assert-improves`.

### Opt-in: experience replay & dream rollouts

Two consolidation mechanisms, both default **off** (behavior is unchanged unless you
enable them). They strengthen the nightly update when your tasks have a clean
correctness signal; the validation gate still governs what ships.

| Config knob | Default | Effect |
|---|---|---|
| `dream_rollouts` | `1` | Run each task K times → learn from the good-vs-bad contrast (contrastive reflection). |
| `recall_k` | `0` | Associative recall — pull the K most-similar past tasks (from a persisted archive) into tonight's dream. |
| `dream_factor` | `0` | Add N lightweight synthetic variants of each task. |

## Results

- **End-to-end on real agents.** On the public
  [gbrain-evals](https://github.com/garrytan/gbrain-evals) `skillopt-v1` benchmark,
  deficient seed skills go **0.00 → 1.00** on held-out sets with **both Claude and
  Codex** (all 4 seeds, including a real tool-use loop).
- **Experience replay scales the gain on a clean signal** (deployment protocol:
  5 nights × 10 new real tasks/night, full held-out test, GPT-5.5, gated):

  | Config | Δ vs baseline |
  |---|---|
  | `recall_k=10, dream_rollouts=5` | +3.1 pts |
  | `recall_k=20, dream_rollouts=5` | **+4.5 pts** |
  | full-history replay (reference) | +5.6 pts |

  A second benchmark (SpreadsheetBench, GPT-5.4-nano, gate-free) gives **+3.6 pts**.
- **Honest scope.** Gains are real where tasks recur and have a checkable correctness
  signal; on saturated or noisy tasks the effect is flat within run-to-run noise
  (±1–2 pts, single seed). The validation gate keeps the downside bounded — keep it on.

## Learn more

Full reference (pipeline, the three plugins, the experience-replay knobs) is in the
**[Documentation & Reproduction Guide](https://microsoft.github.io/SkillOpt/docs/guideline.html#sleep)**.
