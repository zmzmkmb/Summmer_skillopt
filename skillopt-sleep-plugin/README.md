# SkillOpt-Sleep (Claude Code plugin)

> Give your local Claude agent a **sleep cycle**. Every night it reviews your
> past sessions offline, replays your recurring tasks on your own API budget,
> and consolidates what it learns into **validated** memory (`CLAUDE.md`) and
> skills (`SKILL.md`). Your agent gets better the more you use it — no
> model-weight training.

SkillOpt-Sleep is the **deployment-time** companion to
[SkillOpt](https://github.com/microsoft/SkillOpt). SkillOpt trains a skill
offline on a benchmark; SkillOpt-Sleep applies the same discipline to *your own
daily usage*: bounded text edits, accepted only through a held-out validation
gate, with rejected edits kept as negative feedback.

It synthesizes three ideas:

| Idea | Contribution |
|---|---|
| **SkillOpt** | skill/memory = trainable text; bounded add/delete/replace edits; **held-out gate** keeps only changes that help. |
| **Claude Dreams** | offline consolidation over past sessions; input never mutated; output **reviewed then adopted**. |
| **Agent sleep** | periodic offline replay turns short-term episodes into long-term skill. |

## What it does (one "night")

```
harvest ~/.claude transcripts → mine recurring tasks → replay offline
   → consolidate (reflect → bounded edit → GATE) → stage proposal → (you) adopt
```

Nothing live is modified until **you** run `/sleep adopt` (the Dreams "review,
then adopt or discard" contract). Every adopt backs up the prior file first.

## Quick start

```bash
# from inside any project you use with Claude Code:
/sleep dry-run     # safe preview: what it would learn, no changes staged
/sleep run         # full cycle: stages a reviewed proposal (still no live edits)
/sleep status      # see history + the latest staged proposal
/sleep adopt       # apply the staged proposal to CLAUDE.md / SKILL.md (with backup)
```

Or call the engine directly (Python ≥ 3.10):

```bash
python -m skillopt.sleep run --project "$(pwd)" --scope invoked --backend mock
python -m skillopt.sleep run --project "$(pwd)" --backend anthropic   # real lift, uses your budget
```

Default backend is **`mock`** — deterministic, no API spend — so you can try the
plumbing for free. Switch to `--backend anthropic` for genuine improvement.

## Does it actually improve? (deterministic proof)

```bash
python -m skillopt.sleep.experiments.run_experiment --persona researcher --assert-improves
python -m skillopt.sleep.experiments.run_experiment --persona programmer  --assert-improves
```

Each prints the held-out score rising from baseline toward 1.0 as the gate
accepts the general rules your tasks need, and confirms the gate **rejects** an
injected harmful edit. Recorded output: [`docs/sleep/experiment_results.md`](../docs/sleep/experiment_results.md).

## Schedule it nightly

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/install-cron.sh" "$(pwd)"   # prints a crontab line; installs nothing
```

## Safety

- **Read-only** harvest of `~/.claude`. `mock` replay has no side effects.
- Proposals are **staged**, never auto-applied (unless you opt in with `--auto-adopt`).
- Every adopt writes a backup under the staging dir's `backup/`.
- Per-night **token/task budget caps**; secrets redacted from prompts.
- `fresh` replay (Phase 3) runs only in throwaway git worktrees.

## Status

Phase 1 (engine + deterministic experiment + plugin surface) is complete.
Phase 3 adds the real-API miner/judge and `fresh` worktree replay. See
[`docs/superpowers/specs/2026-06-07-skillopt-sleep-claude-code-plugin-design.md`](../docs/superpowers/specs/2026-06-07-skillopt-sleep-claude-code-plugin-design.md).
