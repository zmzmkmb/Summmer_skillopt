# TG8 Manual Run: Terminal Audit

## Status and Scope

The single plan-authorized independent run completed 360/360 rows with exit
code 0 at **2026-09-17 08:08:45.965176 Asia/Shanghai**. Start time was
2026-09-16 23:21:26.711900 in the same timezone. All outputs are preserved in
`artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1`.
There were 45 recorded successes (12.5% pooled across four conditions) and
16,311 acknowledged actions. This pooled rate is not the method comparison.

The automatic six-hour cutoff was cancelled by explicit user amendment,
without restarting the experiment. The unchanged original config/receipt
and separate amendment must be interpreted together. The guardian recorded
service termination at 08:08:46 and released its SYSTEM awake request.
At the 09:34 read-only check, `powercfg /requests` listed no active requests.

No new episode, environment step, retry, replay, network, provider, model,
API or paid request was performed during this audit. Prior incomplete
attempts, including the 103-row v7 prefix, are preserved separately and
are not pooled with this run.

## Integrity Audit

Full offline selector/trace/hash/event audit **passed at 10:15:02
Asia/Shanghai on September 17**: all 360 rows and 16,311 transitions.
The audit script is `scripts/audit_acl2027_tg8_manual_terminal_v1.py`.
It checks all scheduled identities, aggregate-versus-row equality, input
fields, complete histories, admissibility, trace and ledger fingerprints,
frozen selector recomputation, recorded metrics, events and binding hashes.
It does not instantiate the environment or reevaluate success labels.

The initial uncached offline audit was stopped after 150 verified rows
because repeated static SkillIndex scans were costly; it published no
terminal audit artifact. A tested exact-command cache now memoizes only
that pure lookup and returns fresh lists. Every transition's ranking,
ledger and decision are still recomputed by the unchanged frozen validator.
This is an audit implementation optimization, not an experimental retry,
resume or selector-code change.

The audit artifact is written to the new independent directory
`artifacts/acl2027_tracegraph_tg8_durable_v2/audit_20260917_manual_v1`.
Publication refuses overwrite. The original run is read-only.
Audit SHA-256:
`054a73c13e9984e3dfe5c07e6d76c2929454105bfee47e381f923448d4785d71`.
Original result SHA-256:
`1a8f4c860822524e8290057b4783ff467ec8d0e4ba3a7e784af924f8d2dff954`.

## Descriptive Results

| Condition | Successes | Rate | Two-cycle episodes by step 50 | Actions |
| --- | ---: | ---: | ---: | ---: |
| Lexical greedy | 0/90 | 0.00% | 90/90 | 4,500 |
| Lexical anti-cycle | 0/90 | 0.00% | 81/90 | 4,500 |
| Observable subgoal greedy | 3/90 | 3.33% | 87/90 | 4,368 |
| Observable subgoal anti-cycle | 42/90 | 46.67% | 45/90 | 2,943 |

All recorded successes occurred by step 36, hence also by the primary
step-50 landmark. The combined condition has a descriptive improvement
of 46.67 percentage points over lexical greedy and 43.33 percentage points
over subgoal greedy. These are descriptive contrasts, not significance
claims or proof of a general mechanism.

The combined condition succeeded on 6/10 simple-placement task identities,
8/10 cleaning-and-placement identities, and 0/10 two-object-placement
identities. Subgoal greedy succeeded on one cleaning-and-placement identity.
All conditions failed every two-object-placement task. This family-level
failure remains an important boundary, not an exclusion criterion.

## Horizon and Replication Caveats

1. **Effective horizon:** all 315 failed rows stopped at exactly 50 steps
   with `stop_reason=environment_done`. No row reached step 51. The frozen
   outer loop permits 75 steps, but the current vendor YAML contains
   50-step episode limits (`skillopt/envs/alfworld/vendor/config_tw.yaml`,
   lines 88 and 121), and the builder loads that YAML without a step-cap
   override. This supports an environment-horizon explanation. The YAML's
   launch-time hash was not bound in the receipt, so the exact launch-time
   configuration is not independently proven by its present contents.
   The primary 50-step outcomes remain observed; stored
   `completion_by_step_75` values are not evidence from an extended
   75-step evaluation. Keep this deviation visible.
2. **Independent units:** there are 30 task identities, four conditions
   and three replicates. All 120 task-condition groups have identical
   recorded observation/action/outcome sequences across replicates.
   The 42 combined-condition successes represent 14 task identities.
   Do not treat the repeated rows as independent tasks.
3. **Inference:** the preregistered paired task-cluster bootstrap has now
   been computed with 10,000 resamples, preserving all three replicates and
   four conditions within each task. Completion representation, controller
   and interaction effects are +25.00 [+15.00, +35.00], +21.67
   [+13.33, +30.00] and +43.33 [+26.67, +60.00] percentage points.
   These are marginal 95% intervals without multiplicity correction and
   support pilot signals, not confirmatory proof. All six primary
   endpoint/contrast results, the post-execution computational seed and
   exact percentile rule are in the separate analysis artifact.
4. **Audit ceiling:** deterministic selector recomputation uses the same
   frozen validator as execution, not a separately implemented oracle.
   Success labels are recorded environment outcomes, not independently
   replayed. Private-network evidence does not establish independently
   measured zero network traffic.

## Next Allowed Work

Terminal verification and primary task-cluster analysis are complete.
Examine failure trajectories without tuning on them or modifying the
frozen selector. Do not fix the horizon and silently repeat this run.
Any changed executable experiment requires separate review, frozen bindings
and fresh exact authorization. Existing authorization is consumed.

## Analysis and Full Report

Analysis:
`artifacts/acl2027_tracegraph_tg8_durable_v2/analysis_20260917_manual_v1/analysis.json`
with SHA-256
`da3a08f94a0a0198b0fc3ec67e0b26903d4186366c5ed7486009aae6da8f55a9`.

Chinese TG6-TG8 research report:
`paper/acl2027/reports/TRACEGRAPH_TG6_TG8_RESEARCH_REPORT_20260917_ZH.md`.
It preserves the effective-horizon, identical-replicate, task-family failure,
prior-task-exposure, and outcome-dependent cycle-observation caveats.
