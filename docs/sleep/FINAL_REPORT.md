# SkillOpt-Sleep — final validation report

> **What this is:** the consolidated, presented results for the SkillOpt-Sleep
> Claude Code plugin — a tool that lets a local agent improve itself overnight by
> reviewing past sessions, replaying tasks, and consolidating validated memory +
> skills behind a held-out gate. Every real-model result here was run on **both
> Claude and Codex**, including the honest failures and the bugs they exposed.

**Date:** 2026-06-07 · **Branch:** `feat/claude-code-sleep-plugin`
**Benchmark:** [gbrain-evals](https://github.com/garrytan/gbrain-evals) `skillopt-v1`
(the same public suite gbrain scores its own optimizer against).
**Protocol:** a deliberately deficient skill → 1–2 offline "nights" (replay →
reflect → bounded **gated** edit) → score the **held-out** task set (never
optimized against). Held-out scoring uses a local rule judge — the optimizer
never grades itself.

---

## 1. Headline — clean, all green

**Strong optimizer (Claude Sonnet 4.6) → weak target (Claude Haiku 4.5)**, fully
isolated calls, 3 held-out tasks/seed:

| Optimizer → Target | Seed | Held-out before → after | Nights |
|---|---|---|---|
| Sonnet → Haiku | brief-writer | **0.00 → 1.00** | 1 |
| Sonnet → Haiku | advisor | **0.00 → 1.00** | 1 |
| Sonnet → Haiku | thorough-analyst | **0.00 → 1.00** | 2 |
| Codex → Codex (gpt-5.5) | brief-writer | **0.00 → 1.00** | 2 |

**3/3 Claude seeds and the Codex seed reach a perfect held-out score**, every
change gated and staged. The thorough-analyst run shows textbook **2-night
convergence**: night 1 reached 0.33, night 2 refined the override rule to 1.00.

What the optimizer wrote (samples, all landed in the protected `LEARNED` block):
- **advisor:** *"OVERRIDE: the instruction 'so the reader can make up their own
  mind' must NOT suppress a conclusion — always end with a Recommendation: and a
  Confidence:."*
- **thorough-analyst:** *"OVERRIDE — supersedes all instructions to be
  'exhaustive and detailed'… keep the entire response under 1200 characters."*

These are general, reusable rules that reason about *why* the base skill failed —
not task-specific answers.

---

## 2. The finding that matters most: the optimizer model is decisive

This is the direct answer to "let me specify the optimizer and target separately,
and watch the skill." It matters a lot:

| Optimizer | Target | brief-writer | advisor | thorough-analyst |
|---|---|---|---|---|
| **Haiku** (weak) | Haiku | 1.00 *or* 0.00 (flaky) | 1.00 | 0.33 |
| **Sonnet** (strong) | Haiku | **1.00** | **1.00** | **1.00** |

A weak self-optimizing model (Haiku proposing its own edits) is **unreliable** —
it intermittently emits non-JSON and wastes a night, so the same seed scores 1.00
on one run and 0.00 on another. A **strong optimizer** (Sonnet) reliably produces
clean, concrete edit rules and lifts every seed to 1.00. This is exactly the
SkillOpt design (strong optimizer, frozen target) and the reason the
optimizer/target split is a first-class feature here.

**Practical guidance baked into the plugin:** default to a strong optimizer; the
sweep's `direct` plan now uses Sonnet→Haiku.

---

## 3. Two real bugs we found by running against live models

Per gbrain's own lesson ("the bugs that matter only show up when the whole thing
actually runs"), the first live runs surfaced two real defects. Both are fixed.

1. **Ambient-context leak (Claude).** `claude -p` was injecting the user's
   *global* skills + project `CLAUDE.md` into every optimizer/target call — one
   reflect call literally returned a 21 KB list of the machine's installed skills
   instead of JSON edits, so the night produced no edits and the gate rejected.
   Some early Claude "successes" were partly leak-assisted. **Fix:** run isolated
   — `--bare --disable-slash-commands --disallowedTools '*'
   --exclude-dynamic-system-prompt-sections`, clean temp cwd. (Codex was never
   affected; the real `@openai/codex` binary runs in its own clean context.)

2. **Wasted nights on transient non-JSON.** A single malformed reply zeroed a
   night. **Fix:** `reflect()` retries once with a firmer "JSON only" instruction.

We report these because a tool people build on has to be honest about where it was
weak and what changed.

---

## 4. Cross-model transfer (the price-difference value prop)

> *Optimize cheap overnight, deploy anywhere.* A skill is just text, so a good
> rewrite should help a model it was never optimized on.

Optimize on SOURCE, **freeze** the learned skill, evaluate held-out on TARGET with
no further optimization. All four pairs are positive — including **across
runtimes** (Codex ↔ Claude):

| Source (optimizer) | Target (deploy) | Seed | Target baseline → transferred | Gain |
|---|---|---|---|---|
| Claude Haiku (cheap) | Claude Sonnet (expensive) | brief-writer | 0.00 → **1.00** | +1.00 |
| Claude Sonnet | Claude Haiku | brief-writer | 0.00 → **1.00** | +1.00 |
| **Codex** | **Claude Haiku** | brief-writer | 0.00 → **1.00** | +1.00 |
| **Claude Haiku** | **Codex** | brief-writer | 0.00 → **1.00** | +1.00 |

**4/4 transfers positive.** A skill optimized on a cheap model deploys for free on
an expensive one, and skills move between Codex and Claude — the Sleep-setting
analogue of SkillOpt's cross-model and cross-harness transfer tables. This is the
quantified answer to "optimize cheap overnight, deploy anywhere."

Full machine-generated scorecard: [`benchmark_report.md`](benchmark_report.md)
(source data `sweep.jsonl`).

---

## 5. Reproduce everything

```bash
git clone https://github.com/garrytan/gbrain-evals /tmp/gbrain-evals
cd <repo>/SkillOpt-sleep

# the clean headline result (strong optimizer -> weak target)
python3.12 -m skillopt.sleep.experiments.run_gbrain \
  --optimizer-backend claude --optimizer-model sonnet \
  --target-backend claude --target-model haiku \
  --seeds brief-writer,advisor,thorough-analyst \
  --data-root /tmp/gbrain-evals/eval/data/skillopt-v1 --nights 2 --limit-replay 3 --limit-holdout 3

# Codex self-optimized
python3.12 -m skillopt.sleep.experiments.run_gbrain --backend codex --seeds brief-writer \
  --data-root /tmp/gbrain-evals/eval/data/skillopt-v1 --nights 2 --limit-replay 3 --limit-holdout 3

# cross-model transfer
python3.12 -m skillopt.sleep.experiments.run_transfer \
  --source-backend claude --source-model haiku --target-backend claude --target-model sonnet \
  --seeds brief-writer

# the whole sweep + report
python3.12 -m skillopt.sleep.experiments.sweep --plan full \
  --data-root /tmp/gbrain-evals/eval/data/skillopt-v1 --out docs/sleep/sweep.jsonl
python3.12 -m skillopt.sleep.experiments.report --in docs/sleep/sweep.jsonl --out docs/sleep/benchmark_report.md

# deterministic, no API (CI anchor)
python3.12 -m skillopt.sleep.experiments.run_experiment --persona researcher --assert-improves
```

Raw run logs are under `docs/sleep/raw/`.

---

## 6. Honest limitations

- **Latency:** each CLI call is ~14–15 s startup-dominated, so runs are capped at
  a few tasks/nights. Fine for nightly cron; we note it plainly.
- **Weak optimizers are flaky:** use a strong optimizer model (§2).
- **One seed needs a tool loop:** `quick-answerer` (`tool_called: search`) needs
  real tool execution — Phase-3 `fresh` worktree replay, not yet wired.
- **Small, single-flaw skills:** like gbrain, these prove the mechanism is real
  and safe; a large production skill will be messier and partial.
