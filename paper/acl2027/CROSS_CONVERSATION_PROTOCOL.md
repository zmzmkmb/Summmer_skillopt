# ACL 2027 Cross-Conversation Experiment Protocol

This file makes the experiment program resumable across Codex conversations. The repository, rather than chat history, is the source of truth.

## Terminal Handoff: 2026-09-17

The manual-plan run `independent_20260916_manual_v1` is COMPLETED, not running.
It ended at 08:08:45.965176 Asia/Shanghai with exit code 0, 360 saved rows,
45 successes and 16,311 acknowledged actions. The guardian observed terminal
state at 08:08:46 and released its SYSTEM awake request. Authorization is
consumed and closed. Do not relaunch, resume, retry, overwrite, or create a
heartbeat. The September 16 running instructions below are historical.

Offline terminal selector/trace/hash/event validation passed for all
360 rows and 16,311 steps at 10:15:02 Asia/Shanghai using
`scripts/audit_acl2027_tg8_manual_terminal_v1.py`. Output is separate from
the original run, under
`artifacts/acl2027_tracegraph_tg8_durable_v2/audit_20260917_manual_v1`.
The original config retains its six-hour value; the explicit cancellation
amendment explains the longer elapsed time and is not a new execution.

Descriptive successes per 90 rows: lexical greedy 0, lexical anti-cycle 0,
observable subgoal greedy 3, observable subgoal anti-cycle 42. All 315
failures ended at step 50 with `environment_done`; no row reached step 51.
Thus the primary 50-step endpoint is observed but the intended extended
75-step sensitivity is unavailable. Do not silently fix the environment
or rerun under the consumed authorization.

All 120 task-condition groups have identical recorded observation/action/
outcome sequences across their three replicates. The sample contains 30
task identities, not 360 independent tasks. The preregistered 10,000-resample
paired task-cluster analysis is complete. All six marginal 95% intervals
exclude zero in the observed direction, supporting development-pilot
signals only, without multiplicity correction or confirmatory claims.
Analysis: `artifacts/acl2027_tracegraph_tg8_durable_v2/analysis_20260917_manual_v1/analysis.json`.
Report: `paper/acl2027/reports/TRACEGRAPH_TG6_TG8_RESEARCH_REPORT_20260917_ZH.md`.
Audit SHA: `054a73c13e9984e3dfe5c07e6d76c2929454105bfee47e381f923448d4785d71`.
Analysis SHA: `da3a08f94a0a0198b0fc3ec67e0b26903d4186366c5ed7486009aae6da8f55a9`.
Next work is read-only failure diagnosis and separately versioned follow-up
design, not execution. Report prior exposure of the same tasks in partial
runs and success-dependent observation length for cycle incidence.
Preserve prior partial runs separately; do not
pool them. All network/provider/model/API/paid and original data prohibitions
remain closed. Isolation evidence is not independently measured traffic.

## Manual Handoff: 2026-09-16

DEADLINE CANCELLED, 23:57 CST verification: the user requested removing
automatic time stopping. The existing service now has RuntimeMaxSec=infinity
via a runtime drop-in; Linux PID380 and the original 23:21:26 start remain,
NRestarts=0, PrivateNetwork=yes. New Windows awake guardian PID27152 acquired
its SYSTEM request before old timed supervisor PID18772 was terminated.
WSL keeper PID29516 remains. The old 05:21 deadlines are no longer active.
No experimental process was restarted and frozen config/receipt/code stay
unchanged; the user-authorized amendment explains the effective control change.
See `current_phase.manual_execution` and
`artifacts/acl2027_tg8_manual_control_20260916/deadline_cancellation_applied.json`.
At verification 61 rows/12 successes were readable, with no exit or final
scientific audit. Preserve the replacement guardian and do not relaunch.
The 360-row/75-step/zero-retry/first-invariant/input/network/data rules remain.

Current powercfg AC and DC lid actions were both index 0 (Do nothing).
No power/lid setting was changed in this turn and no physical lid-close test
was performed. Earlier lid-open advice and the six-hour controls below are
historical; current configuration alone is not proof that firmware, heat or
power loss can never interrupt execution.

RUNNING UPDATE, 23:23 CST: the authorization is consumed. Exactly one formal
service, `tg8-v2-f0cdf278bffd858564cf`, started at 23:21:26 CST and is running
with Linux PID380, PrivateNetwork=yes, Restart=no and a six-hour limit.
New run: `artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1`.
Windows relay/supervisor/WSL keeper PIDs: 27988 / 18772 / 29516.
The real SYSTEM awake request was verified; no DISPLAY request is held.
Nominal service deadline: 2026-09-17 05:21:26 CST; host readout 05:21:27,
with 30-second service shutdown grace. Do not change the limit.
Six saved rows (216 steps, two successes) passed basic prefix/input/history/
admissibility/cap audit at 23:23:55. No final result or conclusion exists.
See `current_phase.manual_execution`, the startup evidence JSON and
`results/tracegraph_tg8_manual_start_20260916.md`. Read only; never invoke
any confirmation/relay/launcher again. No Codex heartbeat was created.
The older `durable_execution` field describes the terminal v7 run, NOT this
currently running manual-plan experiment.

AUTHORIZATION UPDATE, 23:01 CST: the user explicitly authorized Codex to
start the exact manual plan below. Provenance:
`configs/acl2027/tracegraph_tg8_manual_chat_authorization_20260916.json`.
The operator may relay that authorization once to the unchanged local prompt.
Its generated receipt uses the helper's label `explicit_local_terminal_confirmation`;
the separate provenance file records that the real source was the user's
chat message, not an authorization independently invented by the assistant.
Before submission inspect the control directory
`artifacts/acl2027_tg8_manual_control_20260916` and all new receipt/output
paths. Never submit again if a claim, process or run output exists.
The earlier unconfirmed preparation description below is historical.

TRANSPORT NOTE: initial host PID 22072 exited before authorization because
Read-Host did not receive the redirected input. No receipt, authorized
config, experimental output or episode was created. Its logs/claim remain.
A prompt-synchronized relay passed an offline transport smoke with native
WSL preflight, without loading an environment. It may deliver the existing
user authorization to the unchanged script once. See the control directory's
`preauthorization_transport_failure.json`; do not count this host failure as
a started experiment or use it to justify repeating any actual row.

The user requested a self-run entrypoint without Codex monitoring.
`scripts/start_acl2027_tg8_manual_v1.ps1` and the closed plan
`configs/acl2027/tracegraph_tg8_manual_plan_20260916.json` are prepared.
Plan digest: `bb68465f38a85105042dc086426415f1b6b2465c67997569d5bc412399c072ba`.
Only the user's exact local terminal confirmation creates the new authorized
config/receipt and launches the new independent output directory
`artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1`.
No new episode or authorization was created during preparation.
See `TG8_MANUAL_START_20260916.md` for the command, scope, tests and limits.

IMPORTANT: after this handoff, inspect `current_phase.manual_execution_candidate`
and its config/receipt/output paths before any action: the user may have
launched independently. Static preparation status must not trigger a duplicate
launch. Do not install a Codex heartbeat. The old v7 attempt remains terminal.

Windows standby at 2026-09-15 23:43:46 and lid wake at 2026-09-16 11:50:15
provide evidence of a host-power contribution. The terminal Python stack
waits on a local worker queue, not an Internet read. Exact causation remains
unconfirmed. New protection requests system wakefulness while allowing the
screen to turn off; it does not prevent explicit sleep, lid sleep or power
loss. The user must leave AC connected, the lid open and terminal open.

## V7 Authorization: 2026-09-15

TERMINAL UPDATE (2026-09-16): the v7 service stopped at 11:50:14 CST,
exit 130, systemd result timeout. This is later than the amended 07:00
wall-clock deadline; the discrepancy cause remains unknown. Saved evidence
contains 103 schedule-prefix rows, 4416 steps and 19 successes, with no
result.json; ordinal 103 was started but not saved. Basic prefix/cap/input/
history/admissibility checks passed, not a complete factorial audit.
Execution is closed and heartbeat tg8-v7 is deleted after terminal checks.
Preserve the partial outputs; do not restart, retry or resume.
The following launch/deadline details are historical provenance.

The user explicitly accepted the complete durable-v2 authorization request.
New receipt: `configs/acl2027/tracegraph_tg8_durable_v2_authorization_receipt_v7_20260915.json`.
New config: `configs/acl2027/tracegraph_tg8_durable_v2_authorized_20260915.json`.
Both Windows and WSL validation passed. The closed candidate remains unchanged.
The authorized output is
`artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260915_v1`.
The systemd unit is `tg8-v2-ecaa88078a140638bacf`. Consult the structured
`current_phase.durable_execution` record before any action. Once submitted,
monitor only: no duplicate launch, automatic retry, or resumed rows.

Submitted once at 2026-09-15 22:26:11 CST. Service started at 22:26:16 CST,
Windows PID 27656, Linux main PID 390. The original time limit requested stop at
2026-09-16 04:26:16 CST. On September 15 the user extended the existing run
to 2026-09-16 07:00:00 CST, with the unchanged 30 seconds of grace.
The effective limit is 30824 seconds from the original service start.
A unit-specific runtime drop-in and daemon-reload applied the change without
restart; PID/start time remained unchanged and NRestarts=0.
The original config and receipt hashes remain frozen. See
`results/tracegraph_tg8_deadline_extension_20260915.md` for the amendment
hash, failed direct method and successful fallback verification.
At 22:28:47 CST, five rows were durably saved; their prefix/order, caps,
runtime fields and admissibility were audited. Two successes and 166 steps
are interim saved-row counts, not a final factorial result.
Heartbeat automation `tg8-v7` performs read-only checks every ten minutes,
remaining quiet on routine progress. Delete it after terminal audit.
The authorization is consumed: do not invoke the launcher again.

## Durable Candidate: 2026-09-15

V2 now provides no-clobber per-row evidence, durable events, exit records,
permanent receipt claims, a Linux active lock, and a hidden Windows WSL
client waiting on a no-restart PrivateNetwork systemd service. The frozen
v1 row executor and selector remain unchanged. Fault-injection tests use
synthetic rows only. A ten-second isolated service smoke exited 0.
No formal episodes were run and the candidate config remains closed.
See `results/tracegraph_tg8_durable_v2_offline_validation_20260915.md`.
The proposed 21600-second wall-time stop is a new infrastructure safeguard
requiring explicit authorization, as are the new runner/launcher/config
bindings. Do not reuse a prior receipt or resume a partially saved run.

## Recovery Checkpoint: 2026-09-13

Latest recovery after the v6 monitoring interruption:
session 5684 is unavailable; WSL has no TG8 runner and the output directory
is absent. Previous WSL boot `7e0c6a897326406091fac864fcc7fc42` records
`poweroff.target` and `Shutting down` at 2026-09-13 02:19:42 CST.
The shutdown initiator and runner exit code are unknown. Completed rows,
successes and scientific invariant status cannot be recovered from the
available evidence. The frozen runner hash is unchanged and its source
writes results only after the loop; there are no durable per-row checkpoints.
No replacement run was launched. The v6 authorization is not reusable.
Before another formal run, address durable supervision, log/exit capture,
and per-row evidence persistence offline. Do not modify the frozen runner;
any replacement requires separate versioning and explicit authorization.

Subsequent fresh user authorization: v6 receipt and separate v6 runner config
passed frozen binding validation. A new independent execution was launched
as session 5684, output suffix `result_authorized_wsl_20260913_independent_2.json`.
This is historical launch provenance, not a currently live session.

The v5 receipt authorized a new independent TG8 v4 execution. At recovery,
session 63914 returned `Unknown process id`; WSL `ps` and `pgrep` found no
TG8 runner. The expected result directory
`artifacts/acl2027_tracegraph_tg8_observable_subgoal_runner_v1` does not exist.
Completed rows, successes, invariant status, exit code, and termination cause
are unknown. Do not treat missing output as zero successes or evidence of a
scientific failure. No replacement execution was launched during recovery.
The authorized runner and config were not changed during this recovery.
Preserve prior missing attempts as provenance; do not automatically retry.
Any new independent execution requires explicit authorization and a new path.

## Start of every new conversation

If the user says `继续`, `继续实验`, `继续 ACL 2027 实验`, or otherwise asks to resume the ACL 2027 work:

1. Read `paper/acl2027/experiment_state.json`.
2. Run:

   ```powershell
   python scripts/acl2027_experiment_handoff.py validate
   python scripts/acl2027_experiment_handoff.py status
   ```

3. If `graphify-out/graph.json` exists and an architecture question is needed, query Graphify rather than rebuilding it.
4. Work only on `current_phase.next_actions`, unless evidence forces a documented change.
5. Do not repeat completed runs whose manifest and aggregate fingerprint validate.

A compact recovery prompt can be generated with:

```powershell
python scripts/acl2027_experiment_handoff.py handoff
```

## Source-of-truth hierarchy

1. `experiment_state.json`: current phase, gates, permissions, and immediate next actions.
2. Immutable config plus artifact `run_manifest.json`: what was actually executed.
3. Phase report in `paper/acl2027/results/`: interpreted result and decision.
4. `experiment_roadmap.md`: complete ACL evidence path.
5. Chat history: explanatory only; never the sole record of a result.

If these disagree, stop the conflicting run, validate artifacts, and repair the state/report before continuing.

## Phase lifecycle

Each phase must move through:

```text
planned -> in_progress -> completed
                    \-> blocked
```

Before execution:

- give the phase a unique ID and immutable config path;
- state the development/held-out split;
- state the decision gate before seeing results;
- record the allowed write scope;
- keep paid API permission explicit.

After execution:

- preserve the config and run directory;
- audit expected run count, file hashes, config hashes, schema, and exact token identities;
- write a phase report including negative results;
- update `experiment_state.json` and append a checkpoint;
- update the roadmap only after the artifact passes audit;
- run the relevant regression suite.

## Artifact rules

- Never overwrite a completed artifact directory.
- A changed config requires a new versioned config and artifact directory.
- Development seeds cannot be relabeled as held-out seeds.
- Timing fields are non-deterministic and must not enter scientific fingerprints.
- Both sides of any counterfactual guard must be charged in exact token accounting.
- Failed, missing, resumed, or excluded runs remain visible in provenance.

## End-of-conversation checkpoint

Before ending a material experiment conversation, update:

- `updated_at`;
- `last_completed_phase` when appropriate;
- `current_phase.status`;
- `current_phase.next_actions`;
- `verification.last_result`;
- `checkpoints` with what changed and the exact next action.

Then run:

```powershell
python scripts/acl2027_experiment_handoff.py validate
```

The final user response should state: completed phase, key measured result, artifact/report paths, test/audit status, next phase, and whether the user must prepare anything.

## Current ACL 2027 experiment handoff (2026-08-16)

This section records the current experiment stage for the next conversation. The structured fields in `experiment_state.json` remain authoritative if this snapshot becomes stale.

### Completed boundary

- Phase 1 is closed and immutable.
- Phase 2 v13 passed formal-history candidate coverage with verified supports `28/32/28/17/16`.
- Phase 2 v20 passed the frozen probe eligibility gate; this is eligibility evidence only.
- Phase 2 v23 completed the 320-row held-out grid and was inconclusive: contextual typed prior `60/80` versus global-only `59/80`, paired margin `+0.0125`, `2/1/77` wins/losses/ties.
- Phase 2 v25 completed the independent 320-call replication and closed: contextual typed prior `59/80` versus global-only `57/80`, paired margin `+0.0250`, `4/2/74` wins/losses/ties. The frozen replication gate is negative. Audit fingerprint: `35a683a78dd6057b8e3e5122373de024706eba033e3742c04eaf081fdba0c779`.

### Next experiment stage

The next admissible stage is **Phase 2 v26 post-v25 failure-analysis design-only preflight**. It must remain zero-network and separately versioned. Its purpose is to inspect the already completed v23/v25 paired outcomes, especially the v25 four wins, two losses, and 74 ties, and freeze a falsifiable follow-up hypothesis before requesting more paid calls.

The v26 design must, before any provider authorization:

1. bind the immutable v23 and v25 audits, manifests, schedules, ledgers, and fingerprints;
2. report task-family and error-type breakdowns without changing the v23/v25 gates;
3. distinguish lack of prior effect from verifier, coverage, prompt-length, and task-capability explanations;
4. define a new independent task split, exact conditions, exact request count, analysis rule, and positive/negative/inconclusive decision gate;
5. prove zero overlap with all spent logical IDs, request hashes, provider response IDs, and previously used evaluation tasks;
6. run cache-free zero-network integrity/regression tests and record an aggregate fingerprint;
7. create no open authorization and make zero network, provider, model, paid, or formal-scaling calls.

After v26 is accepted, provider execution still requires a new explicit authorization stating the exact model, attempts, temperature, retries, `max_tokens` policy, response format, stage CNY ceiling, cumulative CNY ceiling, and forbidden later stages. Do not infer that authorization from a request to continue. Do not retry or resume v25, and do not execute calibration, development acquisition, formal history, probe, held-out, another model, a later stage, or formal scaling without separately scoped permission.

## Current ACL 2027 experiment handoff after Phase 3A (2026-08-16)

This section supersedes the older Phase 2 next-stage snapshot above. The
structured state remains authoritative.

- Phase 2 is complete and remains inconclusive.
- Phase 3A completed a zero-network audit of all 400 Phase 2 task grids.
- All four raw responses were identical on 294 tasks; alias-tolerant outcomes
  were equal on 368 tasks.
- The exclusive taxonomy is 294 no-observable-uptake, 74 response changes
  without outcome changes, 11 typed benefits, 6 typed harms, and 15 other
  heterogeneous tasks.
- Random same-distribution scale-up is rejected. Aggregate fingerprint:
  `0b2c420671b02b4210c3903d5549c5ec137699ec501c028a949da4ebb6212e3c`.

The next admissible work is a separately versioned **zero-network Phase 3B
activation preflight**. It may materialize 60 new tasks across five conditions
and freeze structured applicability/skill-ID/intermediate-operation/final-answer
measurements. The 300-call target is a proposal only. Do not create an open
authorization or make provider/model/paid calls without a later explicit user
authorization bound to the completed Phase 3B preflight.

## Current ACL 2027 experiment handoff after Phase 3B (2026-08-16)

This section supersedes the Phase 3A handoff above. The structured state remains
authoritative.

- Phase 2 remains complete and inconclusive.
- Phase 3A remains immutable and rejects random same-distribution scale-up.
- Phase 3B completed a zero-network activation preflight with 60 entirely new
  tasks, 12 per family, and five conditions per task.
- The frozen schedule contains 300 unique logical calls. Phase 2 task,
  logical-call, and request-hash overlap is zero.
- The response contract freezes exactly four observations: declared skill
  applicability, selected skill ID, intermediate operation, and final answer.
- The shuffled-typed negative control always sources its bundle from a
  different family.
- The frozen stop rule forbids scale-up if contextual uptake is below 0.15 or
  contextual-minus-shuffled uptake is below 0.05.
- Aggregate fingerprint:
  `fe1bb5316f57e4aa4dba14e19a173a44c60575263bd54018b8b33e6d256de7b8`.

The schedule is **not authorized**. No open authorization or authorization
receipt exists. Do not make any provider, model, paid, or formal-scaling call
from a generic continuation request. A future execution requires fresh
explicit permission bound to exactly 300 qwen3.7-plus attempts, temperature 0,
thinking disabled, zero retries, no `max_tokens`, JSON-object responses, an
explicit pacing rule, stage and cumulative CNY ceilings, and forbidden later
stages.

## Current ACL 2027 handoff after Phase 3B recovered execution (2026-08-17)

This section supersedes the earlier Phase 3B preflight snapshot. The structured
state remains authoritative.

- v3 terminally stopped at attempt 127 after 126 completed calls; no retry was
  made and its authorization is closed.
- v4 preserved 125 rows from 25 complete v3 task grids, excluded the incomplete
  task, and froze 175 disjoint recovery requests including one same-family
  replacement.
- v5 completed 175/175 calls with zero retries, 439,441 exact tokens, and CNY
  0.940886 exact stage cost. Its authorization is closed.
- The combined grid has 60 tasks, 300 rows, and 300/300 contract-valid responses.
- Contextual typed uptake is 60/60 versus shuffled typed 31/60, paired difference
  +0.4833. Alias-tolerant contextual accuracy is 53/60 versus shuffled 50/60 and
  cold 54/60.
- The frozen decision gate is positive, the stop rule did not fire, and the
  analysis fingerprint is
  `d228d3b907091a8001d3f3379bd1ad1ded2af1cf30dfe0c148226a6be9cc435f`.

Interpret this as positive mechanism-uptake evidence, not a general final-answer
accuracy improvement over cold. All provider and paid permissions are closed.
A next phase may be designed because the gate passed, but any additional calls,
new model, later stage, or formal scaling require a new zero-network preflight
and explicit authorization.

## Current ACL 2027 handoff after Phase 3C (2026-08-17)

This section supersedes the Phase 3B handoff above. The structured state remains
authoritative.

- Phase 3C completed a zero-network mediation audit over the immutable 60-task,
  300-row Phase 3B grid.
- The uptake strata are 29 contextual-only and 31 both-adopt tasks, with no
  neither-adopt or shuffled-only tasks.
- Contextual-only uptake changed the intermediate operation on 26/29 tasks but
  changed the normalized answer on only 1/29.
- Contextual-only alias-tolerant net wins are 0 versus shuffled and 0 versus
  cold; the frozen mediation gate is `inconclusive`.
- The 31/60 both-adopt rate fires the specificity warning. Both comparison
  families show universal contextual and shuffled uptake.
- Aggregate fingerprint:
  `0e1769ea906c18907f7161aea5fd93b30add92738b6cce26be32091dfb1b30fd`.

Preserve Phase 3C unchanged. The next admissible work is only a separately
versioned zero-network Phase 3D preflight that repairs abstention and bundle
specificity and freezes an outcome-mediation gate before cross-domain scaling.
All provider, model, paid, later-stage, and formal-scaling permissions remain
closed; generic continuation does not authorize any external call.

## Current ACL 2027 handoff after Phase 3D (2026-08-17)

This section supersedes the Phase 3C handoff above. The structured state remains
authoritative.

- Phase 3D completed a zero-network specificity and abstention preflight bound
  to the Phase 3C inconclusive gate and specificity warning.
- It selected 40 entirely new tasks, 20 each from attribute comparison and
  bridge attribute comparison.
- The frozen schedule has 240 requests over cold, global-only,
  contextual-only, irrelevant-only, contextual-first dual candidates, and
  irrelevant-first dual candidates.
- Dual conditions reverse the same two candidates, and each response must
  assess every candidate, select one ID or `none`, expose a short operation,
  and return the final answer.
- The positive gate jointly requires specificity, irrelevant rejection, order
  stability, operation and answer mediation, accuracy wins over the irrelevant
  control, and non-regression versus cold.
- Prior task, logical-call, and request-hash overlap is zero. Aggregate
  fingerprint:
  `59143bd2c63bf73c4f747121d547216a2665c7bd722fb7c672b0e12e9db2e5b0`.

The 240-call schedule is not authorized. A future execution requires fresh
explicit permission bound to the exact fingerprint, sending the frozen payloads
to the named provider, model and route, temperature, thinking, retries,
`max_tokens` policy, JSON response format, pacing, stage and cumulative cost
ceilings, and forbidden later stages. Cross-domain and formal scaling remain
closed.

## Current ACL 2027 handoff after Phase 3D live preflight v2 (2026-08-17)

This section supersedes the earlier Phase 3D design-only handoff. The structured
state remains authoritative.

- The v2 zero-network live preflight binds all 240 unchanged Phase 3D canonical
  requests and revalidates their hashes, uniqueness, and balanced 40-by-6 grid.
- The frozen route is the Alibaba Cloud Token Plan Beijing endpoint using
  `qwen3.7-plus`, temperature 0, thinking disabled, zero retries, absent
  `max_tokens`, JSON-object responses, and one-second pacing.
- The stage cost ceiling is CNY 3.00 and cumulative ceiling is CNY 15.00, against
  a known cumulative lower bound of CNY 7.218738.
- Exact usage accounting, request-start and response hash-chain ledgers,
  first-failure terminal stop, exact-prefix resume, and automatic authorization
  closure are mandatory.
- No authorization receipt or open authorization exists. All call counters are
  zero. Preflight fingerprint:
  `1b57aabe12711ef646674dc39dcc01990c8e0088c667c30fe0818d47c26f4970`.

Do not execute from a generic continuation request. A separately versioned v3
live execution may be created and launched only after the user sends the exact
authorization statement in
`artifacts/acl2027_phase3d_specificity_abstention_live_preflight_v2/authorization_request.json`.
Other models, later Phase 3 stages, cross-domain scaling, and formal scaling
remain forbidden.

## Current ACL 2027 handoff after Phase 3D v3 execution (2026-08-17)

This section supersedes the v2 preflight handoff. The structured state remains
authoritative.

- The authorized Phase 3D v3 execution completed 240/240 calls with zero
  retries, exact usage, valid pacing and hash chains, CNY 1.571752 exact stage
  cost, and closed authorization.
- The frozen strict response contract failed on 240/240 responses because the
  provider used candidate-ID-keyed assessment mappings instead of ordered arrays.
  The frozen gate is therefore `negative`.
- The separate non-gating v3.1 diagnostic reconstructs the order only to
  describe the spent responses: contextual-single and dual selection are 1.0,
  irrelevant rejection is 0.675, contextual answer net wins over irrelevant are
  zero, and the contextual condition has two net losses versus cold.
- Strict fingerprint:
  `501f57df97267d3dae84fa953e0652102e5d003572d9e40c58d8a50010e22b29`.

Preserve all v3 artifacts and do not retry any of the 240 requests. Cross-domain
and formal scaling remain closed. Any later work must be a separately versioned,
zero-network redesign of the response contract, irrelevant rejection, and
answer mediation; any new provider calls require fresh explicit authorization.

## Current ACL 2027 handoff after Phase 3E (2026-08-17)

This section supersedes the Phase 3D v3 handoff above. The structured state
remains authoritative.

- Phase 3E completed a zero-network audit of Phase 3D's irrelevant controls.
- Attribute-comparison's bridge-attribute control was valid: applicable 0/20
  and selected 0/20.
- Bridge-attribute-comparison's entity-bridge control was invalid: applicable
  and selected 13/20, because it supplies the required film-to-director bridge.
- Phase 3D's strict contract failure and negative frozen gate remain unchanged,
  but the bridge-family 13/20 non-rejections are confounded and cannot support
  a claim of indiscriminate adoption.
- Aggregate fingerprint:
  `ca9b53061590b7d11f45a355a4e19b177806e8366707a70ceb4e8005c5eb26e7`.

Preserve Phase 3E unchanged. The only next admissible work is a separately
versioned zero-network Phase 3F redesign. It must use the candidate-ID-keyed
assessment mapping as the native contract or pre-register deterministic
normalization, replace the invalid bridge-family control with an
operation-incompatible control, prove wholly new identity non-overlap, and
freeze answer-sensitivity/mediation gates. All provider, model, paid,
cross-domain, and formal-scaling permissions remain closed; any provider call
requires fresh explicit authorization.

## Current ACL 2027 handoff after Phase 3F v2 execution (2026-08-17)

This section supersedes the Phase 3E handoff above. The structured state remains
authoritative.

- The explicitly authorized Phase 3F v2 execution completed 240/240 calls with
  zero retries, valid one-second pacing and hash chains, 711,240 exact tokens,
  and CNY 1.543848 exact stage cost. Authorization closed automatically.
- Strict analysis is inconclusive: 221/240 contract-valid rows, contextual
  selection 1.0, irrelevant rejection 0.625, dual correct selection 0.95, and
  answer-change rate 0.40.
- The non-gating boolean-mapping diagnostic has 238/240 contract-valid rows and
  repairs selector specificity (irrelevant rejection 1.0; dual correct 0.975),
  but its answer-change rate is 0.05, below the frozen 0.10 mediation threshold.
- Strict fingerprint:
  `d797e795ba5d6318cbeb01ce8ff7187949a134679a621a673855b216e3a3d0cc`.
  Diagnostic fingerprint:
  `96e6678979361ed7b840bc0b1e80ac4ddbf1b19ebbb49ede377a3379b224d0b4`.

Preserve all Phase 3F artifacts and do not retry any request. Selector
specificity is improved, but answer mediation remains inadequate. Cross-domain
and formal scaling remain closed. The only admissible future experiment is a
separately versioned zero-network design; any provider execution needs new,
explicit payload-egress and cost authorization.

## Current ACL 2027 handoff after Phase 4B v3 (2026-08-18)

This section supersedes all earlier next-stage snapshots. The structured state
remains authoritative.

- The Phase 4B v2 local-runner record closed before provider invocation. Its
  orphan request-start row is preserved, with an additive correction recording
  zero actual provider, network, model, paid, token, or cost usage.
- The separately versioned v3 authorization completed 100/100
  `qwen3.7-plus` development calls with zero retries, valid one-second pacing,
  202,872 exact tokens, CNY 0.476706 stage cost, and automatic closure.
- All 100 responses were JSON-parseable, but 0/100 satisfied the frozen
  six-field evidence-grounded contract. The required rate was 0.95.
- The Phase 4B development stop rule fires. Phase 4C, replication,
  cross-domain testing, other models, and formal scaling are not authorized.
- Strict analysis fingerprint:
  `75f54900bc79b1a9a49f715219b7bfb20571c91a261e71b2e850f9e92713e885`.

Preserve all Phase 4A/4B artifacts and never retry a spent v3 request. The only
admissible experimental continuation is a separately versioned zero-network
prompt/transport contract-repair diagnostic and preflight. Any later provider
execution requires fresh explicit authorization.

## Current ACL 2027 handoff after Phase 4B-R1 (2026-08-18)

This section supersedes the Phase 4B-v3 next-stage snapshot. The structured
state remains authoritative.

- The zero-network diagnostic confirms a prompt/transport visibility failure:
  all 100 original system messages omitted the six exact contract keys because
  the contract metadata lived outside `messages`; evidence IDs were also not
  visible to the model.
- The repaired prompt embeds the exact six-field schema in both system and user
  messages and annotates every context sentence with a copyable evidence ID.
- The final adapter transport projection is audited for all 100 rows.
- The proposal contains 20 wholly new development tasks, 10 per family, and
  100 balanced five-condition rows with zero prior task, logical-call, or
  request-hash overlap.
- No authorization, network, provider, model, paid, Phase 4C, cross-domain, or
  formal-scaling call occurred. Fingerprint:
  `a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c`.

Preserve Phase 4B-R1 unchanged. Its 100-row repaired proposal is not authorized.
A future execution requires a separately versioned live preflight and fresh
explicit authorization. Phase 4C remains closed until a repaired development
calibration completes and passes every frozen calibration gate.

## Current ACL 2027 handoff after Phase 4B-R2 (2026-08-18)

This section supersedes the Phase 4B-R1 next-stage snapshot. The structured
state remains authoritative.

- The closed zero-network R2 preflight binds the exact R1 repair fingerprint
  `a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c` and
  unchanged 100-row schedule.
- It revalidates all 100 canonical request hashes and all final adapter
  transport hashes, 20-by-5 balance, the transmitted six-field contract,
  explicit evidence IDs, and zero prior task/logical-call/request-hash overlap.
- R2 identifies 80 unique transmitted payloads: each task's `global_only` and
  `contextual_typed` rows are transport-identical, for 20 duplicate pairs.
  Those labels cannot support a causal comparison in this immutable schedule.
- The route is frozen to Token Plan Beijing `qwen3.7-plus`, temperature 0,
  thinking disabled, zero retries, no `max_tokens`, JSON-object responses,
  one-second pacing, CNY 2.00 stage and CNY 15.00 cumulative ceilings,
  first-failure stop, exact-prefix resume, hash-chain ledgers, and automatic
  closure.
- No receipt or open authorization exists; network/provider/model/paid/Phase
  4C/replication/cross-domain/formal-scaling calls remain zero. Fingerprint:
  `94a2e284a4049db12f5e1f1294fa92d4433547ee9be0dd151e6ba848bbc7da28`.

Preserve R1 and R2 unchanged. Do not create a receipt or execute any call from
a generic continuation request. A future execution requires the exact R2
authorization statement, including the 80-payload/20-equivalent-pair
disclosure. Phase 4C and all scaling remain closed.

## Current ACL 2027 handoff after Phase 4B-R3 (2026-08-18)

This section supersedes the R2 next-stage snapshot. The structured state is
authoritative.

- The exact R2 authorization opened R3 for at most 100 repaired development
  requests. The run terminally closed with 73 request starts, 72 complete
  responses, one orphan start, and 27 unattempted rows.
- An external command timeout left the child runner active after the shell
  returned. It was explicitly terminated. Six starts and six responses were
  written after the original closure snapshot but before process termination;
  authorization was not reopened.
- Request 73 has no response record and is conservatively spent. Never retry or
  resume it or any earlier spent request.
- The first 72 response rows and all 73 request starts have valid hash chains,
  valid one-second pacing, and zero retries. Known usage is 204,266 tokens and
  CNY 0.512794; known cumulative cost is CNY 12.328920. Orphan usage is unknown.
- All 72 recorded responses are JSON-parseable, strict six-field
  contract-valid, and evidence-ID resolving. This is partial non-gating repair
  evidence only; the frozen 100-row calibration gate was not reached.
- Authorization is closed. Phase 4C, replication, other models, cross-domain
  testing, and formal scaling remain forbidden. Terminal audit fingerprint:
  `f32e141b1ba15637cdb9b99fa360a59996adf613b90d610b7ef206bce14773e1`.

The next admissible experiment is a separately versioned zero-network recovery
preflight. It must exclude all 73 spent identities, preserve the 72 completed
rows as provenance, replace the orphan row under a new identity, and freeze the
remaining coverage. Any recovery provider execution requires fresh exact user
authorization.

## Current ACL 2027 handoff after Phase 4B-R4 (2026-08-18)

This section supersedes the R3 next-stage snapshot. The structured state is
authoritative.

- The closed zero-network R4 preflight preserves all 72 complete R3 responses
  as provenance and excludes all 73 spent R3 logical IDs and request hashes.
- It freezes 28 new canonical identities: one replacement for orphan source
  sequence 73 and 27 rows for unattempted source sequences 74-100.
- All model-visible payloads are unchanged. The orphan replacement deliberately
  repeats spent transport hash
  `c835e7e855d1121c09e03d21544e46884dedb0903275347dfc54a7f7c1f73cda`
  under a new logical ID and request hash; this is disclosed recovery, not a
  retry of the spent canonical identity.
- The combined plan restores 100 rows, 20 tasks, and 20 rows per condition. It
  retains 80 unique payloads and 20 identical
  `global_only`/`contextual_typed` pairs, so that contrast is non-identifiable.
- No external call or authorization exists. Unknown orphan usage leaves future
  cost ceilings unresolved. Fingerprint:
  `fc668155d0e1d787fe45bf381f5958d8f9d5d78759be3c0bab3951580254f066`.

Preserve R1-R4 unchanged. Provider execution requires a separately versioned
zero-network live preflight, explicit cost treatment, and fresh exact user
authorization. Phase 4C and all scaling remain closed.

## Current ACL 2027 handoff after Phase 4B-R5 (2026-08-18)

This section supersedes the R4 snapshot. The closed zero-network R5 preflight
binds the immutable 28-row R4 recovery plan to Token Plan Beijing
`qwen3.7-plus`, temperature 0, thinking disabled, zero retries, absent
`max_tokens`, JSON-object responses, one-second pacing, first-failure stop,
exact-prefix resume, and hash-chain ledgers.

Unknown orphan usage is handled with a CNY 0.011136 conservative reserve, a
CNY 0.30 recovery-stage ceiling, and a CNY 15.00 cumulative ceiling. The
projected known upper bound is CNY 12.640056. No receipt, open authorization,
or external call exists. Fingerprint:
`4b220ba56d8cf0990ecf86df791f79b8218db427c81a117b6c78a775d58f5a0d`.

Preserve R1-R5 unchanged. Provider execution requires the exact R5
authorization statement and must retain the orphan transport-repeat and
`global_only`/`contextual_typed` non-identifiability disclosures.

## Current ACL 2027 handoff after Phase 4B-R6 (2026-08-18)

The explicitly authorized recovery completed 28/28 calls with zero retries,
valid pacing, and automatic closure. R6 used 81,331 tokens and CNY 0.209612;
the known cumulative lower bound is CNY 12.538532 and the conservative total
with orphan reserve is CNY 12.549668.

Combined with the 72 complete R3 rows, all 100 calibration rows are present,
strict contract-valid, and evidence-ID resolving. Contextual selection is 1.0,
so the Phase 4B development contract gate passes. This is not a causal typed-
prior result: the 20 `global_only`/`contextual_typed` pairs remain transport-
identical. Authorization is closed and Phase 4C remains unauthorized. Analysis
fingerprint:
`80cc655e1dc70795b783ae671f55e9df064c552467db3a42295e795f46016048`.

## Current ACL 2027 handoff after Phase 4C-D1 (2026-08-18)

The zero-network Phase 4C-D1 diagnostic audits the inherited Phase 4A held-out
schedule before any new authorization. Across 400 rows and 80 tasks, zero rows
expose the exact six-field contract in transmitted messages and zero rows
expose copyable evidence IDs. All 80 `global_only`/`contextual_typed` task
pairs are transport-identical.

The inherited held-out schedule is therefore blocked from Phase 4C execution.
A separately versioned repair design must embed the contract, annotate evidence
IDs, make the two conditions substantively distinct, prove zero spent-identity
overlap, and obtain a fresh live preflight plus exact authorization. No Phase
4C authorization or external call exists. Diagnostic fingerprint:
`57e2588f8183e4d8682f20dcf9d587fb37fe303142be1c340b616fbef68405c7`.

## Current ACL 2027 handoff after Phase 4C-R1 (2026-08-18)

The closed zero-network repaired design freezes 80 held-out tasks and 400 new
rows. Every row embeds the exact six-field response contract and annotated
evidence IDs in transmitted messages. The design has 400 unique transport
payloads, 80 rows per condition, and zero logical/request overlap with spent
Phase 4B identities.

This is technical design readiness only. No Phase 4C receipt, live preflight,
provider call, or paid authorization exists. A separate live preflight and
fresh exact authorization must bind this fingerprint:
`5c776023249499a5022fe901cae9f0684c22e30991fa9349a71e9af92b14bda3`.

## Current ACL 2027 handoff after Phase 5 admission/grounding preflight (2026-08-20)

The zero-network Phase 5 design preflight was created at 2026-08-20 17:25:22 and recorded in structured state at 2026-08-20 23:58:00+08:00. It freezes 40 new counterfactually identifiable tasks and 240 rows across cold, always_use_typed, evidence-grounded admission_typed, shuffled_typed, incompatible_control, and evidence_abstain conditions. The seven-field response contract exposes the admission decision, selected candidate, evidence IDs, intermediate result, and final answer while keeping private target/counterfactual gold out of requests. All 240 logical IDs, request hashes, and transport payload hashes are unique with zero prior identity overlap. Aggregate fingerprint: c61009e80f5f662c5b62c87239aff4a9fce86c759a98c6250f1a4e941b11a7de.

This is design-readiness only. No network, provider, model, or paid call was made, and no live authorization is open. Any execution requires a separately versioned zero-network live preflight, corrected cumulative-cost accounting, and fresh exact user authorization. Preserve the Phase 5 artifacts unchanged.
## Active research-line isolation (2026-08-22)

Authoritative active line: `scope-aware-admission-answer-level-grounding`.

Former line `typed-scoped-prior-continual-routing` is permanently `LEGACY / FROZEN / READ-ONLY`. Do not modify, overwrite, retry, resume, tune on, or construct new provider schedules from its artifacts. Legacy files may be read only for provenance, historical evidence synthesis, and failure diagnosis.

Every subsequent experiment must declare `experiment_line`, use the active line identifier, and prove fresh task/logical/request/transport identities. Runners must refuse legacy-line execution. Primary active-line endpoints are admission correctness, operation correctness, evidence resolution, final-answer correctness, and counterfactual-answer avoidance; selector uptake alone is non-gating.

## Current TraceGraph TG0 handoff (2026-08-27)

This section supersedes earlier active-line instructions. The structured state
and `paper/acl2027/TRACEGRAPH_RESEARCH_PLAN.md` are authoritative.

- Active line: `tracegraph-observable-state-skill-composition`.
- Current stage: `TG0-tracegraph-research-plan-v1`, completed plan persistence.
- TraceGraph is ALFWorld-first. A future SkillBank may use only ALFWorld
  training-split expert trajectories; runtime inputs are only observation,
  historical actions, and admissible actions; composition uses a constrained
  SkillGraph with frozen `qwen3.7-plus`.
- TG0 creates no provider request, model/API call, authorization receipt,
  SkillBank, schedule, or WebShop asset.
- Phase 0-6 is `FROZEN / READ-ONLY`: it is allowed only as motivation or
  appendix diagnostics and is forbidden as TraceGraph data, SkillBank input,
  tuning, prompt example, threshold source, evaluation substrate, or provider
  schedule source. Do not execute or repurpose Phase 6.
- WebShop remains blocked until a separately preregistered ALFWorld mechanism
  gate has been executed and passed. The first target is auditable mechanism,
  not an assumed accuracy gain.

Before any future TraceGraph work, read the state and this protocol, run
`python scripts/acl2027_experiment_handoff.py validate`, and verify the plan
through Graphify. Any later stage must declare the TraceGraph research-line ID,
data split and source identities, allowed runtime inputs, and a zero-Phase-0-6
contamination audit.
## Current TraceGraph TG1 handoff (2026-08-27)

TG1 is the active zero-network ALFWorld SkillBank preflight. Its authoritative
configuration is `configs/acl2027/tracegraph_tg1_alfworld_skillbank_preflight_v1.json`.
It may validate only the contract: training path, provenance schema, runtime
exclusions, and Phase 0-6 isolation. `$ALFWORLD_DATA` is not set at this
checkpoint, so TG1 must not read trajectories, construct a SkillBank, launch
ALFWorld, call a model/provider/API, or create a receipt.

Future construction requires a separately versioned protocol and a local source
root limited to `$ALFWORLD_DATA/json_2.1.1/train`; `valid_seen` and
`valid_unseen` are prohibited. WebShop remains blocked.
## Current TraceGraph TG1 construction-protocol handoff (2026-08-28)

The official ALFWorld `json_2.1.1/train` source audit is complete for 3,553
paired `game.tw-pddl`/`traj_data.json` records; 2,821 trajectories without an
adjacent game file remain excluded. The provenance manifest is immutable for
this checkpoint. A separately versioned construction protocol is now frozen at
`paper/acl2027/TRACEGRAPH_TG1_SKILLBANK_CONSTRUCTION_PROTOCOL_V1.md` with
configuration `configs/acl2027/tracegraph_tg1_skillbank_construction_v1.json`.
Its preflight passes, but `construction_enabled=false`: no SkillBank records,
ALFWorld episodes, provider/model/API calls, receipts, WebShop assets, or
Phase 0-6 reuse are authorized. Any future construction requires a new enabled
zero-network preflight bound to the source-manifest fingerprint and a complete
deterministic-output audit.
## Current TraceGraph TG1 deterministic SkillBank build handoff (2026-08-28)

The enabled zero-network construction preflight passed against manifest file
SHA-256 `f0027b4ab28a80371d4e3a43f9208e956c99ecc691efaae8f0741805ee17fdec`.
The local deterministic builder produced `23,746` unique skills from `3,553`
paired ALFWorld `json_2.1.1/train` records; output SHA-256 is
`15059dd2cc5b99fc69d0bae79109ec20c8d000ec9d550ce237d06ee9ffd6a331`. The
artifact is `artifacts/acl2027_tracegraph_tg1_skillbank_construction_v2/skillbank.jsonl`.
Raw trajectories, images, planner/PDDL state, human descriptions, evaluation
data, and Phase 0-6 material are excluded. Freeze this artifact. The next
admissible work is a separately versioned TG2 observable-state representation
and constrained SkillGraph preflight; no provider/model/API call or held-out
episode is authorized.
## Current TraceGraph TG3 runtime mechanism handoff (2026-08-28)

TG3 is a zero-network fixture audit bound to the immutable TG1 SkillBank and TG2
observable SkillGraph configuration. All four preregistered checks passed:
eligible-edge compliance, inadmissible-skill rejection, complete trace fields,
and hidden-state rejection. The audit artifact is
`artifacts/acl2027_tracegraph_tg3_runtime_mechanism_preflight_v1/mechanism_audit.json`
with SHA-256 `bdec60b9666298d06b06f4239fe536eeaa1b66bcec43463df59fdd8e4ae404c3`.
This is mechanism evidence only. Do not run held-out ALFWorld episodes or make
provider/model/API calls until a separately versioned held-out mechanism
protocol and its zero-network preflight pass.
## Current TraceGraph TG4 held-out mechanism handoff (2026-08-28)

TG4 froze a zero-network held-out ALFWorld schedule containing 40 task
identities: 20 from `valid_seen` and 20 from `valid_unseen`. The schedule is
`artifacts/acl2027_tracegraph_tg4_heldout_mechanism_preflight_v1/heldout_schedule.json`
with SHA-256 `9e3acdad7a106fb20374d9885fc8da9f29ffba329c17c11134f193962887bb87`.
Held-out trajectories are evaluation-only and cannot enter the TG1 SkillBank.
No episode, provider/model/API call, receipt, Phase 6 action, WebShop asset, or
Phase 0-6 reuse is authorized. Before running any held-out episode, create a
separately versioned local runtime-runner preflight with exact trace and stop
rules bound to TG1-TG4 fingerprints.
## Current TraceGraph TG5 runtime-runner handoff (2026-08-28)

TG5 froze the local runtime-runner contract for the 40-task TG4 schedule. The
runner accepts only observation, historical_actions, and admissible_actions,
requires the complete TG3 trace fields, allows one trace row per task, and
stops on the first hard invariant violation. Its 40-task dry-run passed 40/40;
the artifact is
`artifacts/acl2027_tracegraph_tg5_runtime_runner_preflight_v1/dryrun.json`
with SHA-256 `5fe798315f491cd157b16efa1aa33aee293c21add60dab8fe40379079312856e`.
No real episode, provider/model/API call, receipt, Phase 6 action, WebShop
asset, or Phase 0-6 reuse is authorized. Real held-out execution requires
explicit authorization for an exact local scope and a new execution preflight.
## Current TraceGraph TG6 local execution handoff (2026-08-28)

TG6 freezes, but does not authorize, a possible local execution of exactly 40
held-out ALFWorld episodes from the TG4 schedule. The scope allows zero retries
and stops on the first hard invariant violation. It binds the TG5 runner dry-run
and keeps runtime inputs limited to observation, historical_actions, and
admissible_actions. Configuration:
`configs/acl2027/tracegraph_tg6_local_execution_preflight_v1.json` (SHA-256
`f9ec6efe63d044adf1614f3ca7d67c7b434963c94cdea44ac093498c4ab77c7c`).
`execution_authorized=false`; no episode, provider/model/API call, receipt,
Phase 6 action, WebShop asset, or Phase 0-6 reuse is authorized. Any execution
requires explicit authorization bound to this exact scope and fingerprint.
## TG6 held-out readiness audit (2026-08-28)

The frozen TG4 schedule remains 40 held-out identities, but local ALFWorld
assets currently make only 22/40 executable because 18 tasks lack an adjacent
`game.tw-pddl`. The readiness artifact is
`artifacts/acl2027_tracegraph_tg6_local_readiness_audit_v1/readiness.json`
(SHA-256 `0dd01c696bfddc577e8ccbec93ba3fb3bf2f11d7bc5cd379678a6d1a163094e6`).
Do not silently narrow or run a partial schedule. Obtain complete game-file
coverage or create a separately justified, versioned schedule revision before
any execution authorization. No episode or model/provider/API call occurred.
## TG6 held-out readiness resolved (2026-08-28)

The official `json_2.1.1_pddl.zip` archive was verified and extracted. Using
the official ALFWorld domain and grammar files, `game.tw-pddl` was materialized
for all 40 frozen TG4 held-out tasks without running solvability episodes. The
readiness audit is now `40/40` and ready=true in
`artifacts/acl2027_tracegraph_tg6_local_readiness_audit_v2/readiness.json`
(SHA-256 `4db572cdd7dbba3091cfc37f3554a3425e360e64f8ceebfdd9faffc526e3bd99`).
TG6 execution remains unauthorized: do not start episodes or create receipts
until explicit authorization binds the exact TG6 config fingerprint, 40 local
episodes, zero retries, and stop-on-first-hard-violation.

## Current TraceGraph TG6 local execution terminal handoff (2026-08-31)

The user supplied exact authorization for the frozen TG6 local scope: 40
held-out ALFWorld episodes, zero retries, stop on the first hard invariant
violation, and runtime inputs limited to `observation`, `historical_actions`,
and `admissible_actions`. The runner configuration is
`configs/acl2027/tracegraph_tg6_local_execution_runner_v1.json` (SHA-256
`2d60a6557affc9d67dc2fd7d7f6fb9cf3b6e3ba239461b2d427b99df4f8bf67e`) and is
bound to the authorized preflight fingerprint
`f9ec6efe63d044adf1614f3ca7d67c7b434963c94cdea44ac093498c4ab77c7c`.

Execution stopped immediately at the first hard invariant violation. Two tasks
started; the first ran 50 steps and ended `environment_done` without success,
while the second failed at step 0 during ALFWorld/TextWorld reset with
`KeyError: 'val1'` while parsing `game.tw-pddl`. The result is a local
environment-integrity blocker, not a TraceGraph capability conclusion. The
terminal artifact is
`artifacts/acl2027_tracegraph_tg6_local_execution_runner_v1/` with result,
manifest, and report files. Its result SHA-256 is
`440a6e6ede149724015dceb7948bf72a81fd8128ba6d8d42f9aa01097467b87f`.

Observed counts are 2 episodes started, 1 completed, 0 successes, 0 retries,
and zero network/provider/model/paid-API calls. Do not retry or resume either
started task, modify the terminal artifact, execute Phase 6, build WebShop
assets, or reuse any Phase 0-6 artifact. Any repaired execution must use a
separately versioned preflight and fresh exact authorization.

## Current TraceGraph TG6 PDDL-integrity diagnosis handoff (2026-08-31)

A read-only audit of all 40 frozen TG4 `game.tw-pddl` files is complete. The
audit artifact is
`artifacts/acl2027_tracegraph_tg6_pddl_integrity_audit_v1/audit.json` (SHA-256
`a4a85ec9ffadbb76b0622cd102cf536e6a31def0233941b7a4f777d0e6b804cd`). It found
8/40 tasks where the target is marked `pickupable` but has no `inReceptacle`
fact. The vendored ALFRED `PickupObject` operator requires that fact, so these
tasks are structurally unsatisfiable under the current TextWorld PDDL domain.
For the second scheduled task, Fast Downward consequently returns its
unsolvable placeholder state containing `dummy(val1)`, which surfaces as the
observed `KeyError: 'val1'` in TextWorld's state reconstruction.

This diagnosis does not modify the official dataset, the frozen TG4 schedule,
or the terminal TG6 artifact. It is not a model-capability result. Do not
retry/resume the terminal run, silently drop the eight tasks, or inject facts
into the frozen source. Any repair must be separately justified (for example,
a versioned domain/adapter repair or a newly preregistered schedule), audited
without provider/model/API calls, and then bound to fresh exact authorization.


## Current TraceGraph TG6 derived PDDL repair handoff (2026-08-31)

A separately versioned zero-network adapter was built for the frozen TG6 schedule. It writes only under `artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/derived/` and leaves every official `game.tw-pddl`, the TG4 schedule, and the terminal TG6 artifact unchanged. Exactly 8/40 tasks were repaired by adding `TraceGraphFloorReceptacle - receptacle`, `TraceGraphFloorType - rtype`, a matching `receptacleType`, `receptacleAtLocation` at the existing target `objectAtLocation`, and the missing `inReceptacle` fact. Tasks with any already-valid target instance were copied byte-for-byte.

Fast Downward `pddl2sas` parsing passed for all 40 derived problems. The preflight ran zero episodes and made zero network/provider/model/API calls. Its artifacts are `repair_manifest.json` (source/derived hashes), `preflight.json`, `repair_completion_manifest.json`, and `preflight_report.md`. This is an environment-compatibility result, not a TraceGraph capability result. Do not retry/resume the old TG6 run, do not execute repaired episodes without a separately versioned runner config and fresh exact authorization, and do not execute Phase 6, build WebShop assets, or reuse Phase 0-6 data.
## Current TraceGraph TG6 repaired local-execution preflight handoff (2026-09-02)

The separately versioned closed preflight is
`configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v1.json`
with SHA-256
`a4855cc665e2404b905df979949980da01305255761f9a7612bcd8b23c1b5feb`.
Its validator and the repaired runner guard passed 15 cache-free regression
tests, including handoff validation. The scope remains exactly 40 derived
held-out tasks, zero retries, stop on the first hard invariant violation, and
runtime inputs limited to `observation`, `historical_actions`, and
`admissible_actions`.

This is still a closed preflight: execution_authorized=false, the
authorized runner configuration does not exist, and zero episodes,
provider/model/API calls, receipts, Phase 6 actions, WebShop assets, or
Phase 0-6 reuse are permitted. Do not create the authorized config or run the
repaired runner without a fresh exact user authorization bound to this
preflight fingerprint and scope.
## Current TraceGraph TG6 repaired local-execution attempt (2026-09-02)

The exact authorized repaired runner configuration was present at configs/acl2027/tracegraph_tg6_repaired_local_execution_runner_v1.json (SHA-256 D5EEDD7A934C1A1F005388002769D170C76441759F76A59D120FEA19209618C8), bound to the repaired preflight fingerprint a4855cc665e2404b905df979949980da01305255761f9a7612bcd8b23c1b5feb and the frozen 40-task derived manifest.
The runner was invoked once with zero retries; it stopped before episode 0 because Windows Python could not load the Linux NumPy binary, and the path-appended fallback exposed Linux-only Jericho/Fast Downward binaries. The existing WSL path was also unavailable with Wsl/Service/E_ACCESSDENIED.

No result.json was written, no episode started, and no network/provider/model/API call occurred. This is an environment dependency blocker, not a TraceGraph capability result. Do not retry this authorization or resume the old terminal TG6 run. After a functioning local runtime is restored, any later execution must use a new versioned runner attempt and fresh exact authorization.

## Current TraceGraph TG6 repair-v2 and closed execution-preflight handoff (2026-09-05)

The separately versioned repair-v2 formalization is complete. Its derived tree
covers the same 40 frozen TG4 held-out task identities and repairs 10
goal-required pickupable or toggleable objects that lacked `inReceptacle`
support. The formal repair preflight is
`artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/preflight.json` with
SHA-256 `b38728824423e934df397c84e3566b85d99b5155215df9048d7533f3dc0e7686`.

Existing repair-v2 zero-step TextWorld reset evidence passed 40/40 tasks with
zero actions, episodes, network calls, provider/model/API calls, and paid
calls. It was promoted by exact source hash to
`artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/zero_step_evidence.json`.
The repair manifest SHA-256 is
`921344f3658215d8aaa4ef7deea5afa978d41a1ecf6aa6503d57040740c389fd`.

The closed repaired-local-execution preflight is
`configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v2.json`
with SHA-256
`9eb082c1e775c2355629c88abd7f8099dc97260dfca923418a2afae6cddc1df2`.
It binds repair-v2, the frozen TG4 schedule, the TG5 runner dry-run, the
train-only TG1 SkillBank, and the promoted zero-step evidence. The scope is
exactly 40 derived held-out tasks, zero retries, stop on the first hard
invariant violation, and runtime inputs limited to `observation`,
`historical_actions`, and `admissible_actions`.

This preflight remains closed: `execution_authorized=false`. Generic
continuation does not authorize episode execution. The next admissible action
is to use a functioning Linux ALFWorld/TextWorld/Fast Downward runtime and
obtain fresh exact user authorization bound to this v2 preflight before
creating an authorized runner attempt. Do not retry the old TG6 runs, use
Windows Python with the Linux environment, execute Phase 6, build WebShop
assets, or reuse Phase 0-6 material.

## Current TraceGraph TG6 trajectory-failure diagnostic runner handoff (2026-09-05)

The frozen v2 trajectory-failure design now has a separately versioned
implementation note and closed local runner:

- implementation note:
  `paper/acl2027/TRACEGRAPH_TG6_TRAJECTORY_FAILURE_ANALYSIS_IMPLEMENTATION_NOTE_V1.md`
  (SHA-256
  `fa2b80786534cd2f24ff57c003c6bf4f9937c41895664ce6c4462fd3200d6fed`);
- runner config:
  `configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_runner_v1.json`
  (SHA-256
  `bc16c19c53fa2c5d8fdc04fbffa369dca1e2df5ca091f9a5e5632c8b0dd22281`);
- runner:
  `scripts/run_acl2027_tracegraph_tg6_trajectory_failure_analysis_runner_v1.py`.

The runner defines the three frozen conditions
`baseline_first_eligible`, `history_aware_anti_cycle`, and
`observable_progress_aware`, and records a separate observable snapshot
fingerprint that excludes the growing `historical_actions` list. This avoids
under-counting repeated states in the TG6 v4 cycle diagnosis.

The zero-step readiness audit passed all 24 fresh development tasks:
`24/24`, zero actions, zero episodes, and zero network/provider/model/API/paid
calls. Its artifact is
`artifacts/acl2027_tracegraph_tg6_trajectory_failure_analysis_runner_v1/readiness.json`
with SHA-256
`05ba723c5242bbe4014a235741041870529da12cfc19e7e906a964724a6bdfa6`.
The cache-free related suite passed `33/33`.

Episode execution remains closed. A fresh exact authorization must bind the
v2 preflight fingerprint
`b82976f1c5be80bd00d67f4e0397f8a72f4eb56282536864ca649a8f9fe74d07`, the
runner config fingerprint above, exactly 72 development episodes, at most 50
steps per episode, zero retries, first-hard-invariant stop, and the exact
runtime input boundary
`observation`, `historical_actions`, `admissible_actions`. Do not execute
from a generic continuation request, and do not use provider/model/API,
Phase 0-6, Phase 6, WebShop, other models, or other datasets.

## Current TraceGraph TG6 mechanism-audit handoff (2026-09-07)

The authorized 72-episode trajectory diagnostic is complete and immutable:
72/72 episodes finished, with 0/72 successes, 0 hard invariant violations,
100% trace validity, 100% terminal-action admissibility, and zero network,
provider, model, API, or paid calls. Its primary direct-cycle gate is negative:
the two-cycle episode rate is 9/9 under all three conditions.

A zero-network post-hoc audit then analyzed 3,600 immutable transitions. The
audit found 138 exact cross-task allowed-input collision groups, of which 134
contain different post-hoc task targets. It also found that cycle-trigger
states still had eligible actions outside the detected pair, while skill/edge
switches frequently occurred on repeated observable snapshots. The audit
does not claim raw-input information-theoretic impossibility because the
initial observation contains the task sentence; the supported claim is a
failure to maintain target-directed progress under the current observable
selector and trajectory controller.

The audit config is
`configs/acl2027/tracegraph_tg6_trajectory_failure_mechanism_audit_v1.json`
with SHA-256
`fe4217b94f3c4a85d1ec6b3cf2150050ec5b1ef42e5b33253bc36528e06de440`.
Its artifact is
`artifacts/acl2027_tracegraph_tg6_trajectory_failure_mechanism_audit_v1/audit.json`
with SHA-256
`ef3d2b3c5720dfa6003940e069f5fce634e5bebc478b148829fed2ed099c02b3`.
The report is
`paper/acl2027/results/tracegraph_tg6_trajectory_failure_mechanism_audit_v1.md`.

The next admissible work is paper argument revision and, only if justified,
a separately versioned zero-network ablation design. Do not rerun completed
episodes, open provider/model/API authorization, execute Phase 6, build
WebShop, use other models or datasets, or reuse Phase 0-6 artifacts.

## Current TraceGraph TG7 progress-memory runner handoff (2026-09-07)

TG7 freezes a new zero-network progress-memory ablation over 24 fresh ALFWorld
task identities and 72 paired condition rows. The preflight aggregate
fingerprint is 48470f6d571cf4a40547304ea475a536ab9855b40efaf644839b40e7fcdfc0d2.
The three conditions are aseline_first_eligible, 	ask_anchor_aware, and
progress_memory; runtime inputs remain exactly observation,
historical_actions, and dmissible_actions.

The separately versioned runner is
configs/acl2027/tracegraph_tg7_progress_memory_runner_v1.json with SHA-256
e6e96b8eb14017aa379e8187c3e7e141086536bd75ee92774b635dc79f115e79.
Episode execution remains closed. The reset-only readiness attempt was blocked
before environment construction because the current Windows Python interpreter
cannot import lfworld (ModuleNotFoundError). All 24 tasks were marked

ot_attempted_dependency_block; actions, episodes, network, provider, model,
API, and paid calls were all zero.

This is an environment dependency result, not a TG7 capability result. Restore
a functioning local ALFWorld/TextWorld runtime and rerun only reset-only
readiness. Require 24/24 task resets before creating a separately versioned
authorized config and requesting fresh exact authorization for exactly 72 rows.
Do not reuse TG6 artifacts, open provider/model/API permissions, execute
Phase 6, build WebShop assets, or use Phase 0-6 material.
## Current TraceGraph TG7 WSL readiness handoff (2026-09-08)

WSL access was restored and the local Ubuntu runtime was verified with Python
3.12.3, ALFWorld, TextWorld, Gymnasium, NumPy, and the local Fast Downward
binary. TG7 reset-only readiness then passed all 24 fresh tasks with zero
actions, zero episodes, and zero network/provider/model/API/paid calls.

The evidence artifact is
rtifacts/acl2027_tracegraph_tg7_progress_memory_runner_v1/readiness_wsl_20260908.json
with SHA-256
5ed392361360e0c3152e43a73f42da87be74b545a2521b1491fbb9c6089f3fc.
The earlier Windows dependency-block artifact remains preserved and must not be
interpreted as a TG7 capability result.

Episode execution is still closed. Before any 72-row run, create a separately
versioned Linux/WSL authorized runner config and obtain fresh exact user
authorization bound to the TG7 preflight fingerprint
48470f6d571cf4a40547304ea475a536ab9855b40efaf644839b40e7fcdfc0d2,
the new config hash, this readiness evidence hash, exactly 72 paired rows,
at most 50 steps per episode, zero retries, first-hard-invariant stop, and the
runtime boundary observation, historical_actions, and
dmissible_actions. Do not infer authorization from 鈥渃ontinue鈥?

## Closed TG7 WSL runner candidate (2026-09-08)

The candidate config is
configs/acl2027/tracegraph_tg7_progress_memory_runner_v2_ubuntu_wsl.json
with SHA-256
f78a67030b00a85b594da064f9c0fa6cedc1e2685438bd0ab674496b0aea737.
It remains execution_authorized=false; no episode has started. Any run must
be authorized exactly against this config hash, the TG7 preflight fingerprint,
the WSL readiness evidence hash, and the fixed 72-row scope.

## Current TraceGraph TG7 execution result (2026-09-09)

The exact user-authorized Ubuntu WSL run completed the frozen TG7 schedule:
72/72 rows and 3,600 transitions, with 24 rows per condition, 50 steps per
row, zero retries, zero hard-invariant violations, and zero network/provider/
model/API/paid calls. Runtime input isolation, trace validity, terminal-action
admissibility, progress-ledger validity, and progress-ledger provenance all
passed at 100%.

Result artifact:
`artifacts/acl2027_tracegraph_tg7_progress_memory_runner_v1/result_authorized_wsl_20260909.json`
(SHA-256
`34ea3456f7d361761b9c6eff369c466a799a1c2427da18f703060c27546ed4ff`).
Bindings: preflight aggregate
`48470f6d571cf4a40547304ea475a536ab9855b40efaf644839b40e7fcdfc0d2`, WSL
readiness
`b5ed392361360e0c3152e43a73f42da87be74b545a2521b1491fbb9c6089f3fc`,
authorization receipt
`c91e196d07ef65da6fe3206efe976c3922f8f9440d82ffc2e921fc59bedd39e6`, and
authorized config
`3189e528902bd23c9fcd73f084a4c07d8cd8b7a649b39923201ef128c9c8dcc7`.

All three conditions obtained 0/24 successes. Baseline two-cycle rate was
24/24; task-anchor-aware was 24/24; progress-memory was 22/24, only an 8.33%
relative reduction versus the preregistered 50% threshold. Anchor-aware
post-hoc target-surface hit rate was 75.63% versus 9.38% for baseline, but
completion remained zero. The progress-supported and anchor-only gates
therefore fail. The representation-limited gate is supported because the
augmented conditions preserve the contract without improving completion and
179 cross-task allowed-input collision groups remain, including 24 with
conflicting goal tuples.

TG7 is complete and immutable. Do not rerun or retry this result, open any
provider/model/API permission, execute Phase 6, use Phase 0-6 artifacts, or
silently change the schedule. The next admissible work is paper-argument
revision and, only if justified, a separately versioned zero-network design
that changes the observable progress representation or controller.

## TG8 preflight review and execution gate (2026-09-09)

The TG8 v1 zero-network preflight is structurally valid but **not execution
ready**. Independent review found that its 2x2 decision gate confounds the
representation and controller factors, each family-by-split cell has only four
identities and one seed, task selection is lexicographic with repeated template
clusters, and the observable-subgoal/false-progress rules are not yet an
executable selector contract. Metric denominators, collision taxonomy, and
partial-run invalidation rules also require preregistration.

Review report:
`paper/acl2027/results/tracegraph_tg8_preflight_review_v1.md`.

Therefore do **not** run TG8 zero-step readiness or any episode from v1. The
next admissible work is a separately versioned TG8 v2 zero-network redesign:
freeze the three factorial contrasts, deterministic subgoal/state-delta rules,
cluster-aware task sampling, metric formulas and confidence procedure, ledger
adversarial tests, and reproducibility/budget contracts. Execution remains
closed until that v2 preflight passes and a fresh exact user authorization is
provided.

## TG8 v4 design and selector audit (2026-09-10)

TG8 v1-v3 remain immutable zero-network design/review artifacts and are not
execution inputs. TG8 v4 corrected the remaining design issues: 30 globally
unique task templates, 360 explicit rows (`30 x 3 replicates x 4 conditions`),
balanced condition positions (22/23 per condition-position cell), 75-step
maximum with step 50 as the primary landmark, and zero-execution accounting
(`completed_calls=0`, `episodes_run=0`, `actions_taken=0`). Its aggregate
fingerprint is
`098bee6f10b47fb8dbe656785c3732a949448047f72bb0454bb48545299ceffe`.

The selector implementation was revised after review to use a realistic
observable event-state machine: search-source, pickup, search-destination,
clean where applicable, and put events. Its synthetic zero-network audit
passed 5/5 cases, including realistic search/pickup sequencing, false
progress on unchanged snapshots, wrong-object rejection, tamper/hidden-field
rejection, and representation/controller separation. Audit SHA-256:
`885d4346e8a15de7add97a74e8902ea89b83cc2f5224cbe72997b76fd8856714`.

At this v4 design checkpoint, TG8 readiness was still **closed**. The next
admissible action was to build and review a separately versioned zero-step
readiness runner bound to the v4 preflight and selector audit. No episode,
provider/model/API, network, paid, Phase 0-6, Phase 6, WebShop, other-model,
or other-dataset execution was authorized.

## TG8 selector v3 and WSL readiness (2026-09-10)

Selector v3 is now frozen at SHA-256
`6aae3a8539594bdb65bdeab92f9d82c2de9ac0e287f036af1e83157751636622`, with
config SHA-256
`36407699541289ea42a69362f1a6a3c2582648b1e1b7680781ed6725ee066582`. Its
tamper-resistant validator recomputes candidate eligibility, ranking, ledger
transitions, and edge fields from the frozen train-only SkillIndex. The
zero-network selector audit v3 passed 5/5 cases; its audit SHA-256 is
`28bcdc8a917bccd11572a7de0e7f1929529613b8b6d43e516f67b1c869247488`.

The separately bound WSL reset-only readiness then passed all 30 TG8 task
resets and 120 selector probes. The immutable readiness artifact is
`artifacts/acl2027_tracegraph_tg8_observable_subgoal_readiness_v1/readiness_wsl_20260910.json`
with SHA-256
`85627fd938abce62e254a68957893f81b1389cc0a7e6519976d338a15ed3904b`.
It records zero actions, zero episodes, zero network/provider/model/API/paid
calls, `execution_authorized=false`, and `readiness_only=true`.

Formal TG8 execution remains **closed**. Any later 360-row run requires fresh
exact user authorization bound to the v4 aggregate fingerprint
`098bee6f10b47fb8dbe656785c3732a949448047f72bb0454bb48545299ceffe`, the
selector/config hashes above, the readiness hash above, 360 rows, at most 75
steps per episode, zero retries, stop on the first hard invariant violation,
and runtime inputs limited to `observation`, `historical_actions`, and
`admissible_actions`.
