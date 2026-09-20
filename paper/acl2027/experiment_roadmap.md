# ACL 2027 Complete Experimental Roadmap

**Working thesis:** Safe continual skill routing should improve real-task performance per cumulative token by learning per-rule utility online while limiting regressions on previously learned domains.

**Status date:** August 7, 2026

This is the execution-level evidence plan for the ACL 2027 project. It complements `outline.md`: the outline states the paper argument, while this roadmap defines the experiments required to support it. Token-to-target is a shared evaluation axis, not the entire contribution. Greedy, Top-K, and MOAR are comparison policies; the intended method contribution is online credit assignment combined with budgeted routing and cross-domain non-regression.

## 1. Claims and evidence gates

| Intended claim | Minimum evidence |
|---|---|
| Skill routing improves agents | Real downstream accuracy or task success under matched models, prompts, examples, and budgets |
| Learning is token-efficient | All optimization, search, exploration, input, and output tokens counted until a fixed target score |
| The method learns continually | Utilities initialized cold and updated online over a task stream |
| Updates are safe | New-task gains and old-task forgetting reported together |
| The router scales | Nested provenance-controlled 8/32/128/512 libraries with stable rule IDs and hard distractors |
| The method applies to agents | At least one genuine multi-step tool-use environment |
| Results generalize | At least three task families, two model families, and three independent runs per main condition |
| Results reproduce | Frozen configs, run IDs, fingerprints, failures, artifact audits, and compute/token budgets |

A static selector score alone cannot support claims about continual learning, non-regression, or improved LLM agents.

## 2. Unified continual-routing protocol

For every task step:

1. Receive task context, target domain, and current rule library.
2. Retrieve candidate rules.
3. Select a subset under Top-K and prompt-token constraints.
4. Run the target model or deterministic offline simulator.
5. Observe feedback.
6. Assign credit to selected rules.
7. Update utility and uncertainty.
8. Propose optional skill edits.
9. Apply a cross-domain non-regression gate.
10. Record performance, forgetting, latency, routing decisions, and cumulative cost.

All methods must use the same task stream, library, model, prompts, budgets, utility initialization, and evaluation examples.

## 3. Experiment A â€” Real downstream effectiveness

Proxy precision is diagnostic only. Formal experiments must measure:

- **SearchQA:** Exact Match, F1, format validity, tokens, latency, and cost.
- **MMLU-Pro:** classification accuracy, invalid answers, tokens, latency, and cost.
- **Tool-use tasks:** task success, tool and argument correctness, invalid/repeated calls, steps, tokens, latency, and cost.

Controls include the same model, decoding configuration, questions, task order, prompt template, rule library, and budget. Failures and timeouts remain in the denominator and artifact log. Without this evidence, claims must be limited to rule-selection behavior.

## 4. Experiment B â€” Genuine multi-step agent tasks

If the paper claims LLM-agent improvement, include at least one task requiring dependent actions: search-read-answer, tool selection and argument filling, spreadsheet/office manipulation, embodied interaction, or multi-query synthesis. Candidate environments include OfficeQA, SpreadsheetBench, and ALFWorld.

Report task success, wrong-tool calls, parameter errors, redundant calls, average and p95 steps, failures caused by selected rules, recovery behavior, cumulative tokens, and latency.

## 5. Experiment C â€” Rule-library scaling

Build deterministic nested libraries:

```text
8 â†’ 32 â†’ 128 â†’ 512 rules
```

Preserve the same in-domain core while adding rules with stable IDs, provenance, domains, token counts, and duplicate checks. Include:

1. irrelevant cross-task distractors;
2. semantically similar but inapplicable hard negatives;
3. partially overlapping rules;
4. conflicting rules;
5. synonymous duplicates;
6. incorrect or adversarial rules.

Report task performance, candidate recall, selected-rule precision, dynamic prompt tokens, routing latency, index-build time, memory, and update time. If formal experiments stop at 64 rules, the paper must not claim large-scale routing.

## 6. Experiment D â€” Online credit assignment

This is a primary method experiment. Start utilities equal in the main setting and compare:

- frozen utility;
- shared batch reward;
- equal selected-rule reward;
- learned per-rule credit;
- leave-one-out oracle credit at small scale;
- contextual epsilon-greedy;
- contextual UCB;
- Thompson Sampling;
- the proposed uncertainty-aware estimator.

Measure cumulative reward and regret, utility calibration, rank correlation with measured rule contribution, correction time for mistaken utility rankings, exploration overhead, noisy/delayed-feedback stability, and final real-task performance. Frozen Greedy-Utility is a baseline, not evidence of continual learning.

## 7. Experiment E â€” Non-regression and forgetting

Use a continual stream such as:

```text
SearchQA â†’ MMLU-Pro Law â†’ MMLU-Pro Health â†’ OfficeQA â†’ SearchQA re-evaluation
```

Compare unprotected updates, freezing old rules, a hard validation gate, a soft non-regression gate, and the proposed method.

Report new-domain gains, average forgetting, worst-domain drop, old-task performance after each transition, rejected-update rate, harmful updates accepted, beneficial updates rejected, and recovery tokens. Safety and plasticity must be shown together: a gate that rejects every update is safe but not useful.

## 8. Experiment F â€” Strong and fair baselines

### No routing

- Core Only
- Full Library
- Random Top-K

### Retrieval

- TF-IDF
- BM25
- dense retrieval
- cross-encoder/reranker
- MMR

### Budgeted selection

- relevance Top-K
- Greedy-Cold
- Greedy-Utility
- token-aware knapsack
- exact search for small libraries

### Online learning

- epsilon-greedy
- UCB
- Thompson Sampling

### Complex selection

- MOAR
- NSGA-II

Every baseline receives the same budget, library, initialization, tasks, target model, and seeds. Search and exploration costs are never free.

## 9. Experiment G â€” Component ablations

Remove one component at a time:

- relevance;
- learned utility;
- per-rule credit;
- token cost;
- redundancy penalty;
- online update;
- exploration;
- non-regression gate;
- Fast/Slow adaptive switching.

Report accuracy, forgetting, total tokens, tokens-to-target, p95 latency, and failure rate. Components without measurable effects should not be claimed as major contributions.

## 10. Experiment H â€” Utility corruption and adversarial robustness

Stress conditions:

- All-Cold utility;
- noisy utility;
- shuffled utility;
- adversarial utility;
- harmful rules with high initial utility;
- useful rules with low initial utility;
- domain-dependent utility drift;
- duplicate, conflicting, malicious, and factually incorrect rules.

Measure degradation, recovery tasks, recovery tokens, duration of harmful-rule selection, recalibration, regret, and non-regression true/false positive behavior.

## 11. Experiment I â€” Cross-task and cross-model generalization

Minimum formal scope:

- three task families;
- two model families or architectures;
- three independent runs per main condition.

Test whether utility transfers across tasks and models, whether smaller models depend more on routed rules, whether rules are model-specific, and whether the non-regression gate transfers. Report both positive and negative transfer.

## 12. Experiment J â€” Statistical reliability

Required practices:

- at least three independent seeds;
- mean and standard deviation or confidence interval;
- paired comparisons on identical examples;
- paired bootstrap or McNemar-style tests where appropriate;
- effect sizes in addition to p-values;
- explicit failure, timeout, retry, and invalid-output counts;
- validation-based hyperparameter selection;
- one frozen code/config revision per formal sweep.

Copied or resumed outputs must not be counted as independent runs.

## 13. Experiment K â€” Evaluation validity

Prefer objective metrics: Exact Match, F1, accuracy, executable success, environment-state checks, and unit-test or constraint satisfaction.

If LLM-as-a-Judge is necessary, manually annotate a representative subset, use multiple annotators where feasible, report agreement, measure judge-human agreement, test answer-order bias, freeze the judge model/prompt, and retain judge artifacts. Unvalidated judge scores must not be the sole evidence for a main claim.

## 14. Experiment L â€” Efficiency and cost

### Per inference

- selected dynamic-rule tokens;
- total input/output tokens;
- API cost;
- p50/p95 latency.

### Learning

- cumulative tokens before convergence;
- utility-update cost;
- search/exploration overhead;
- tokens required for a target score;
- recovery tokens after corruption or domain shift.

### System

- router CPU/GPU time;
- memory usage;
- index construction and update time;
- failure/retry cost.

Required Pareto curves:

```text
Accuracy â†” Total Tokens
Accuracy â†” Latency
Accuracy â†” Forgetting
```

Primary summary metrics:

- **Tokens-to-Target:** cumulative tokens before first reaching a fixed target score.
- **Score-at-Budget:** best score under a fixed cumulative-token allowance.
- **Budget AUC:** area under the score-versus-token curve.
- **Cumulative Regret:** loss relative to an oracle or best fixed policy.
- **Search Overhead Ratio:** routing and exploration tokens divided by total tokens.
- **Recovery Tokens:** cost required to recover after corruption or domain shift.

## 15. Phased execution plan

### Phase 0 â€” Offline framework, no paid API

Build the unified task-stream/selector interface, credit-assignment simulator, cumulative cost/regret/calibration/forgetting metrics, adversarial conditions, nested 8/32/128/512 libraries, strong constrained/bandit baselines, deterministic mock tests, resumable outputs, run IDs, and fingerprints.

**Decision gate:** do not spend API budget until deterministic curves reproduce and every method is charged for search and exploration.

### Phase 1 â€” Small real-model pilot

Use one model, SearchQA, 100â€“200 examples, three independent seeds, five to seven representative methods, and several cumulative-token budgets.

Objectives: validate proxy-to-real correlation, remove dominated methods, calibrate budgets/thresholds, expose parser/API failures, and verify that online credit changes real outcomes.

**Decision gate:** if proxy metrics do not correlate with real performance, revise the reward model and simulator before scaling.

### Phase 2 â€” Continual non-regression study

Run a multi-domain stream, compare gate variants and controls, measure safety/plasticity, perform utility-corruption recovery, and select the final credit/gate design.

**Decision gate:** new domains must improve without obtaining safety by rejecting nearly all updates.

### Phase 3 â€” Formal ACL experiments

Run at least three task families, one genuine tool-use task, two model families, three independent runs, 128/512-rule conditions where feasible, and only the strongest five to seven methods in expensive sweeps.

Produce the main task table, token-efficiency curves, scale-quality-latency Pareto curves, continual forgetting table, and cross-task/model transfer table.

### Phase 4 â€” Ablation, robustness, statistics, and release

Complete component ablations, corruption/adversarial tests, paired statistics and confidence intervals, judge validation if needed, artifact audits, reproduction scripts, and limitations covering model drift, contamination, cost, and rule provenance.

## 16. Immediate implementation priority

The next milestone is a unified offline continual-routing harness containing:

1. online per-rule credit assignment;
2. cumulative token-to-target accounting;
3. non-regression and forgetting metrics;
4. adversarial utility conditions;
5. strong bandit and constrained-selection baselines;
6. deterministic mock tests and reproducible artifacts.

Greedy, Top-K, and MOAR plug into this harness as policies. After the offline framework is trustworthy, run the small SearchQA API pilot before expensive cross-task/model experiments.

## 17. Submission evidence checklist

- [ ] Real downstream results rather than selector proxies only
- [ ] At least one multi-step tool-use task
- [ ] Nested libraries reaching at least 128 rules, targeting 512
- [ ] All-Cold online utility learning
- [ ] Per-rule credit and contextual-bandit comparisons
- [ ] Non-regression safety-plasticity evaluation
- [ ] Strong retrieval and constrained-selection baselines
- [ ] Complete component ablation
- [ ] Utility-corruption and adversarial robustness
- [ ] Three task families and two model families
- [ ] Three independent runs per main condition
- [ ] Objective metrics or validated judge evaluation
- [ ] Total token, latency, compute, and monetary cost
- [ ] Immutable configs, run IDs, fingerprints, and artifact audit

## Phase 4B development calibration result (2026-08-18)

The explicitly authorized Phase 4B v3 execution completed 100/100 development
calls with zero retries, 202,872 exact tokens, CNY 0.476706 exact stage cost,
valid pacing, and automatic authorization closure. All responses were valid
JSON, but none returned the frozen six-field evidence-grounded contract. Strict
contract validity was therefore 0/100 against the predeclared 0.95 threshold.
The development stop rule fires: Phase 4C must not execute. Descriptive answers
from the contract-invalid responses are non-gating and cannot repair this
failure. Analysis fingerprint:
`75f54900bc79b1a9a49f715219b7bfb20571c91a261e71b2e850f9e92713e885`.

## Phase 4B-R1 prompt/transport repair preflight (2026-08-18)

The zero-network diagnostic establishes a contract-visibility failure rather
than a measured method-effect failure: the original six-field schema and
evidence identifiers were not present in the messages sent by the provider
adapter. The repaired schedule exposes the exact schema and annotated evidence
IDs inside the transmitted messages, verifies the adapter projection, and uses
20 wholly new development tasks across 100 five-condition rows. All prior task,
logical-call, and request-hash overlaps are zero. No execution or Phase 4C
permission exists. Fingerprint:
`a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c`.

## Phase 4B-R2 repaired live-execution preflight (2026-08-18)

The separately versioned zero-network R2 preflight binds the exact R1 repaired
100-row schedule to the Token Plan Beijing `qwen3.7-plus` contract. It
revalidates all canonical request and final transport payload hashes, the
20-by-5 condition balance, the transmitted six-field schema, visible evidence
IDs, and zero prior task, logical-call, and request-hash overlap.

The audit also discovers and freezes an execution limitation: there are 80
unique transmitted payloads, not 100. For every task, the `global_only` and
`contextual_typed` rows are identical after adapter transport projection. Thus
any future execution of this immutable schedule cannot identify a causal
contrast between those labels. The authorization request discloses this fact;
no receipt, open authorization, or external call exists. R2 fingerprint:
`94a2e284a4049db12f5e1f1294fa92d4433547ee9be0dd151e6ba848bbc7da28`.

## Phase 4B-R3 terminal repaired calibration (2026-08-18)

The exact R2 authorization opened a separately versioned R3 run. An external
command timeout left the Python child active until it was explicitly
terminated. The immutable terminal boundary contains 73 request-start entries,
72 complete response rows, one orphan start, and 27 unattempted rows. The
orphan request is conservatively spent and may never be retried.

The completed-response and request-start hash chains validate, pacing is at
least one second, and retries are zero. Known usage is 204,266 tokens and CNY
0.512794; known cumulative cost is CNY 12.328920, excluding unknown orphan
usage. All 72 recorded responses satisfy the exact six-field contract and all
evidence IDs resolve. This is strong partial evidence that the prompt/transport
repair worked, but it is non-gating because the frozen 100-row calibration did
not complete. Phase 4C remains closed. Terminal audit fingerprint:
`f32e141b1ba15637cdb9b99fa360a59996adf613b90d610b7ef206bce14773e1`.

## 17. Phase 0 execution status (updated 2026-08-07)

Completed offline diagnostics:

- Phase 0A: baseline continual-routing grid and token-to-target accounting;
- Phase 0B: contextual state and non-regression gates;
- Phase 0C: contextual transfer, conflict, drift, malicious rules, duplicates, and utility corruption;
- Phase 0D: credit identifiability and leave-one-out cost;
- Phase 0E: global-contextual shrinkage sweep;
- Phase 0F: charged prior-sanity reset guard;
- Phase 0G: low-cost fixed-probe and sequential prior validation with separate development and held-out seeds;
- Phase 0H: helpful-prior retention, informative-probe ablation, and same-policy cold-router comparison;
- Phase 0I: rollout-aware cold-router comparison with cloned online updates and exact update-token accounting;
- Phase 0J: adaptive destructive-reset horizon with per-round trajectories and development cost calibration.
- Phase 0K: frozen 20-seed adaptive-guard reliability evaluation and predeclared-gate decision.
- Phase 0L: global-versus-contextual prior identity and probe-to-stream representativeness diagnosis.

Phase 0G completed 72 development runs and 48 held-out runs. The selected sequential `z=1.0` guard had
0/3 all-cold false resets and 3/3 adversarial detections on both seed splits. It reduced guard cost from
about 13.2k?13.6k tokens in Phase 0F to about 3.4k under adversarial priors and 6.6k under all-cold priors.
Its exact reward per 1k tokens nevertheless remained below Relevance Top-K. A one-probe guard nearly
matched Relevance efficiency on held-out seeds but falsely reset 1/3 all-cold development runs.

The Phase 0G reliability expansion then completed 200/200 runs over seeds 61?80. Both guards detected
20/20 adversarial priors, but the one-probe guard falsely triggered on 2/20 all-cold seeds and the sequential
`z=1.0` guard on 1/20. One-probe mean exact reward per 1k slightly exceeded Relevance Top-K, but paired
bootstrap intervals included zero; sequential validation remained significantly less token-efficient.
All-cold resets are operationally no-ops, so this condition does not measure the cost of discarding useful
learned utility.

Phase 0H then added a genuinely helpful oracle prior, deterministic selection-disagreement ordering, and a
same-policy `cold-router` comparator. The cold-router diagnostic completed 90/90 runs over seeds 81-85 with
zero artifact or token-accounting failures. The unguarded helpful prior improved mean reward from 0.7181 to
0.7553, while the adversarial prior fell to 0.5101. Cold-router comparison detected 5/5 adversarial priors and
removed all-cold comparator asymmetry, but one-probe validation still falsely reset 3/5 helpful priors.
Sequential `z=1.0` reduced this to 1/5 at 5,154 mean oracle guard tokens; seed 83 still lost 0.0540 reward.
Selection-disagreement ordering was a negative result: it worsened one-probe helpful-prior retention and
increased sequential cost.

Phase 0I completed 60/60 rollout-aware development runs with zero audit failures. Cloned learned and cold
states now receive their actual online credit updates during paired validation, including exact charging of
extra credit-assignment tokens. Rollout sequential validation with a 12-sample minimum retained 5/5 helpful
priors, rejected 5/5 adversarial priors, and produced 0/5 all-cold false resets. However, it cost 6,767 tokens
for all-cold, 9,591 for helpful priors, and 6,736 for adversarial priors on average. A 6-sample minimum still
reset seed 83 prematurely, proving that online updates alone do not solve horizon mismatch.

Phase 0J completed 90/90 development runs with zero audit failures. Per-round margin, confidence, recovery
slope, and exact token trajectories are now persisted. The selected harm-margin-0.10/slope-0.10 guard retained
5/5 helpful priors, rejected 5/5 adversarial priors, and produced 0/5 all-cold false resets. Mean guard cost
fell to 3,369 tokens for all-cold, 6,172 for helpful, and 4,022 for adversarial priors: reductions of 49.8%,
35.6%, and 40.3% from the Phase 0I min-12 anchor. The margin-only ablation matched the lowest development
cost, so the slope gate's incremental safety value remains unproven.

Phase 0K completed the frozen 180/180-run reliability grid over seeds 101-120 with zero artifact or exact
token-accounting failures. The selected slope-0.10 guard produced 0/20 all-cold false resets, but falsely
reset 3/20 helpful priors, detected only 19/20 adversarial priors, and used 9,028 mean helpful guard tokens.
It therefore failed the predeclared 0/20 helpful-reset, 20/20 adversarial-detection, and <=8k helpful-cost
gates. The margin-only ablation made the same decisions at lower adversarial cost, so the slope gate has no
observed held-out benefit. The min-12 anchor detected 20/20 adversarial priors but kept the same three helpful
false resets and was materially more expensive.

Phase 0L completed the frozen 80/80-run development diagnostic on seeds 121-140. It established that the
nominal oracle prior was a global mean vector copied into every contextual domain state: global-oracle mean
per-domain Spearman correlation was only 0.481, and its phase-0 stream margin was positive on 10/20 seeds.
An explicit contextual-oracle identity reached 1.0 per-domain correlation, positive stream margins on 20/20
seeds, zero frozen-guard resets, and a +0.1265 mean stream-margin improvement. All-probe coverage also had
higher probe-to-stream correlations than the first-two-round prefix. The labeled Phase 0K postmortem showed
that adversarial seed 109 changed from +0.2187 on the accepted prefix to -0.2260 across all probes and -0.3333
on the phase-0 stream.

The immediate priority is now an **identity-aware non-destructive guard**, not another threshold sweep.
A global-only prior should inform the global state while contextual domain states begin cold; explicit
per-domain priors require an identity-bearing contract. Ambiguous early evidence should abstain or escalate
rather than force destructive reset/accept. Paid API evaluation and formal 128/512 scaling remain disabled,
and any Phase 0M candidate must later pass a new disjoint held-out reliability gate.
## Phase 0M result: typed priors and non-destructive selective deployment

Phase 0M froze and completed 160 development-only runs on seeds 141-160. Correct global-only
initialization raised oracle mean reward from 0.7404 to 0.7870 and removed copied-global helpful
false resets from 4/20 to 0/20. Explicit contextual priors reached 0.8224. The non-destructive
selective candidate accepted 20/20 oracle priors, accepted 0/20 adversarial priors, rejected 16/20
adversarial priors, and abstained on 4/20 without mutating candidate state. Its limitation was exact
validation cost: full oracle confirmation added 9,513 mean tokens over the identity-correct reset
ablation with no reward gain. The artifact and all token/fingerprint identities passed audit
(`0f19ae8eb18a2f07297a909cae672a857f45e92f20dfc54382bde15711b5159b`).

The selected conservative candidate is `global_only_selective_full_confirmation`, frozen only for a
later disjoint held-out reliability test. This is not a downstream or scaling promotion: paid API
and formal 128/512-rule evaluation remain disabled.



## Phase 0N result: frozen identity-aware guard held-out reliability

Phase 0N completed and audited 160/160 held-out synthetic runs on seeds 161-180 with the Phase 0M methods and guard parameters unchanged. The selective candidate exceeded copied-global reset by +0.036734 oracle mean reward (paired 95% t interval [+0.025156, +0.048311]) and used 10.66% more oracle total tokens than global-only reset, below the frozen 15% ceiling. It accepted 18/20 oracle priors, abstained on 2/20, accepted 1/20 adversarial priors, rejected 14/20, abstained on 5/20, and mutated candidate state on 0/40 runs. All file/config/stream/run/aggregate fingerprints and exact run/round token identities passed audit (`72f5973bb697ebd12334ccb0737599154a51a50273e218ac7fe2aeab97914a02`).

The held-out gate formally passed, but adversarial safety has no slack: seed 176 was accepted after full confirmation and then underperformed cold-fallback comparators on the downstream stream. The result therefore strengthens the scoped-prior and non-destructive-abstention claims while preserving probe-to-stream representativeness as the central unresolved risk. Do not tune on seeds 161-180.

The immediate priority is a frozen, budget-capped real-task pilot protocol with no-cost harness and accounting preflight. Paid execution and formal 128/512 scaling remain disabled until that separate protocol is immutable and validated.

## Phase 1A result: budget-capped SearchQA pilot no-cost preflight

Phase 1A froze and completed a deterministic SearchQA pilot preflight around
`qwen3.6-flash`, three pairwise-disjoint 120-item example replicates, and seven
paired methods. The complete mock plan contained 2,448 logical calls, including
48 explicit fallback calls. It persisted 2,576 provider attempts, 128 visible
failed attempts/retries, 7,673,567 input tokens, 18,385 output tokens, and
7,691,952 total tokens. All exact call/token/pico-currency identities passed,
and paid calls remained zero. The simulated accounted cost was 14.58348275335
CNY / 2.08335467905 USD under the frozen conservative snapshot; no charge was
incurred.

Strict parser negative cases, deterministic disjoint manifests, hard-cap
prechecks, resume corruption checks, live-mode refusal, and direct CLI execution
all passed. The first full CLI run usefully exposed and fixed a missing project
root import path. A completed-artifact resume made zero new logical calls and
zero provider invocations while preserving aggregate fingerprint
`dd7e644e34f82b90a3bfcc0569fcaf24225d40d2f3d385e46d2c3c5c54a86db3`.
Mock EM/F1/substring values of 1.0 are plumbing checks only and are not
real-model scientific results.

The immutable artifact is
`artifacts/acl2027_searchqa_phase1a_pilot_preflight_v1`, and the full audit is
reported in
`paper/acl2027/results/phase1a_searchqa_pilot_preflight_v1.md`.

Phase 1B subsequently froze and audited
`searchqa_phase1b_paid_pilot_v1` as a zero-network token-accounting preflight.
Its 2,448 logical calls, 2,579 attempts, 131 retries, 48 fallback calls, and
7,676,501 total tokens satisfy every persisted call-plan, fingerprint, resume,
parser, cap, and accounting identity, with zero paid calls. The related
regression suite passes 80 tests. The provider adapter also disables hidden SDK
retries with `max_retries=0`.

The immutable v1 remains preflight-only. Its runner cannot enter live mode, its
execution loop always selects the deterministic mock provider, and it does not
yet freeze the complete prompts, retrieval/MOAR implementation, executable
guard behavior, runner source fingerprint, or a nonzero monetary cap. The
bounded smoke response also reported 218 completion tokens despite a requested
32-token output limit, requiring fresh verification of reasoning-token,
maximum-token, and billing semantics. Legacy `phase1a` identifiers inside v1
must be corrected only in a new versioned artifact.

The next step is therefore a new immutable Phase 1B live protocol, not a
mutation or rerun of v1. Before any provider call, execution requires explicit
user authorization for the maximum spend. Model availability, endpoint,
region, price, billing currency, and token-limit semantics must then be freshly
verified and frozen with the complete scientific execution contract.
`paid_api_allowed` and `formal_scaling_allowed` remain false. Phase 0N seeds
161-180, especially adversarial seed 176, remain spent held-out evidence and
must not be used to tune thresholds.

On August 9, 2026, the user authorized a maximum Phase 1B spend of CNY 200.
Fresh provider verification confirmed that Token Plan supports Beijing
`qwen3.6-flash` and the v1 OpenAI-compatible endpoint. It also exposed a
decisive compliance blocker: current Alibaba Cloud documentation prohibits
Token Plan Personal and Team keys in automated scripts and non-interactive
batch-call scenarios. The 2,448-call scientific runner therefore cannot use
Token Plan.

The model page also schedules standard `qwen3.6-flash` pay-as-you-go access to
end at 2026-08-10 00:00. The experiment will not bypass its freeze and smoke
gates merely to run before that deadline. A documented migration candidate is
Beijing `qwen3.5-flash`, currently CNY 0.2 per million input tokens and CNY 2
per million output tokens for inputs no larger than 128k. The v1 dry-run totals
would estimate to CNY 1.568 and the existing token hard caps to CNY 13.60, both
below the authorized CNY 200 ceiling.

Changing from `qwen3.6-flash` to `qwen3.5-flash` changes the frozen scientific
protocol and cannot be done implicitly. Phase 1B remains closed until the user
either supplies written provider permission for Token Plan batch
experimentation or explicitly approves a compliant model migration, after
which a new immutable v2 protocol can be frozen.

## Phase 1B result: complete SearchQA Token Plan live pilot v5

On August 9, 2026, the frozen v5 protocol completed all 2,448 SearchQA logical calls with 2,579 provider attempts. It recorded 2,447 successful attempts, 132 failed attempts, 131/131 successful format repairs, one terminal `data_inspection_failed` rejection conservatively charged at the full attempt envelope, zero HTTP 429 attempts, 2,579 unique request IDs, and no reasoning content. Known provider usage was 7,444,769 input plus 70,422 output tokens; total conservative accounted usage was 7,523,639 tokens. The completed summary fingerprint is `e8f28745ef53918b1f22171be9fff77400e41da864a0c8f2a8d88363f35d214e`.

`skillopt_moar_frozen` was strongest (EM 0.788690, F1 0.857837, substring EM 0.907738). The frozen selective candidate tied identity-correct reset on EM but was slightly lower on F1 and substring EM, so the offline selective-guard advantage did not transfer into a clear real-task gain. Phase 1B is complete as mixed/negative evidence. Before Phase 2 or formal scaling, reconcile the offline reward/probe signal with the real SearchQA ranking. Paid API and formal scaling permissions remain disabled.

## Phase 1C result: no-paid proxy-to-real reconciliation

Phase 1C analyzed the immutable 2,352 evaluation calls and 96 guard-probe
calls from Phase 1B v5, paired exactly by `seed:item_id`, together with all 160
immutable Phase 0N summary rows. The selective guard tied identity-correct
reset on EM (delta 0.000000) but was lower on F1 (-0.001984) and substring EM
(-0.002976), while reducing only 3.28 accounted tokens per item on average.
The frozen MOAR method exceeded reset by +0.014881 EM and +0.009708 F1 while
using 119.53 more accounted tokens per item.

The offline selective advantage was +0.004357 mean reward versus the
identity-correct reset comparator (2 wins, 36 ties, 2 losses) and +0.016360
versus copied-global reset (17 wins, 21 ties, 2 losses). This localizes part of
the mismatch to comparator/initialization identity, but does not establish a
repairable guard threshold or probe rule from held-out answers. The selective
non-regression guard is therefore demoted from a primary real-task superiority
claim to a safety/diagnostic component. The primary evidence-backed claim is
budget-aware skill routing, with proxy-to-real calibration as an explicit
analysis problem.

Do not tune on the completed SearchQA held-out answers or spent Phase 0N seeds
161-180. Any guard redesign requires fresh development or fabricated evidence
and a new frozen held-out evaluation. Paid API and formal scaling remain
disabled.

## Phase 2 v10 result: development-acquisition viability diagnostic

The separately authorized development-acquisition stage completed exactly
10/10 `qwen3.7-plus` Token Plan calls, two per frozen skill family. All 10
responses were exact-contract valid and 8/10 were verifier-correct. Exact usage
was 12,469 tokens and CNY 0.025526, with zero retries, zero duplicates, no
`max_tokens`, valid one-second pacing, and automatic authorization closure.

Four families scored 2/2. `entity_bridge` scored 0/2, which increases the risk
of failing the later target of 8 verified formal-history supports within the
frozen 32-attempt cap. The development diagnostic is not itself a frozen gate,
so it does not automatically cancel the Phase 2 design. Its responses are
development-only and cannot become formal-history supports. No formal-history,
probe, held-out, or formal-scaling call ran, and none is authorized. The next
permissible step is a separately versioned zero-network formal-history
activation and risk review.

## Phase 2 completion: v31 combined failure-analysis result

Phase 2 completed the frozen 400-task, four-condition grid by combining 1,072
preserved v27 rows, 308 reusable rows from complete v29 task grids, and 220
completed v31 recovery rows. Terminal and orphan rows remain excluded
provenance; no spent request was retried.

Strict contextual typed prior scored 308/400 versus 301/400 for global-only, a
+0.0175 margin with 14 wins, 7 losses, and 379 ties. Alias-tolerant scoring was
349/400 versus 344/400, a +0.0125 margin with 11 wins, 6 losses, and 383 ties.
Only three of five alias family margins were nonnegative, and the mechanism
stratum contained 9 tasks rather than the required 20. Neither the positive nor
negative rule fired, so the frozen gate is `inconclusive`.

v31 completed 220/220 calls with zero retries, 534,548 exact tokens, CNY
1.084408 exact stage cost, and valid pacing and identities. The cumulative
v27/v29/v31 known cost lower bound is CNY 7.218738 because earlier terminal
attempts have unknown usage. Combined fingerprint:
`a203fc9bf435b9bc8d1079e118b1aa34e54a1b647944596ad0aee351a4b958bb`.

Phase 2 is complete as bounded inconclusive real-task evidence. It does not
establish reliable typed-prior superiority. All provider and formal-scaling
permissions are closed; a new experiment requires a new design and permission.

## Phase 3A result: zero-network real-task mechanism audit

Phase 3A audited the completed 400-task Phase 2 grid without rescoring or
re-gating it. All four raw responses were identical on 294/400 tasks, all
normalized answers were identical on 340/400, and alias-tolerant outcomes were
equal across all four conditions on 368/400. Contextual typed and global-only
raw responses differed on only 53 tasks and their normalized answers differed
on only 33.

The frozen exclusive taxonomy contains 294 no-observable-uptake tasks, 74
response-change-without-outcome-change tasks, 11 typed benefits, 6 typed harms,
and 15 other condition-sensitive tasks. The nine-task global-degradation
stratum remains small; typed recovered three tasks and copied-global recovered
none. These results preserve the Phase 2 inconclusive gate and reject another
random same-distribution scale-up as an efficient next experiment.

The next admissible stage is a separately versioned zero-network Phase 3B
activation preflight. Its design target is 60 new tasks balanced across five
families and five conditions, including a shuffled-typed negative control, with
structured applicability, selected-skill-ID, intermediate-operation, and final
answer observations. The resulting 300-call proposal is not materialized or
authorized. Phase 3A fingerprint:
`0b2c420671b02b4210c3903d5549c5ec137699ec501c028a949da4ebb6212e3c`.

## Phase 3B result: zero-network activation preflight

Phase 3B materialized the mechanism bridge without making any provider call.
It deterministically selected 60 entirely new tasks, 12 per frozen skill
family, and froze 300 unique requests across cold, copied-global, global-only,
contextual-typed, and shuffled-typed conditions. The shuffled control always
uses a typed bundle from a different family. All selected task IDs, logical
call IDs, and request hashes have zero overlap with the scanned Phase 2 spent
and proposed identity universe.

Every future response must expose exactly four fields: declared skill
applicability, selected skill ID, a short intermediate operation label, and the
final answer. Private gold remains outside canonical requests. The analysis
plan freezes paired contextual-versus-shuffled uptake, strict and
alias-tolerant answer scoring, family-level reporting, and positive, negative,
and inconclusive gates before execution. It also requires stopping without
scale-up when contextual uptake is below 0.15 or its advantage over shuffled
typed is below 0.05.

The 300-call schedule is not authorized and no authorization artifact exists.
Any execution requires a new explicit authorization bound to the exact Phase
3B fingerprint:
`fe1bb5316f57e4aa4dba14e19a173a44c60575263bd54018b8b33e6d256de7b8`.

## Phase 3B completion: v5 recovered activation result

The explicitly authorized v3 run completed 126 responses before a DNS terminal
attempt. The immutable v4 recovery excluded the incomplete task grid, retained
125 rows from 25 complete v3 grids, and froze 175 disjoint requests for 34
untouched tasks plus one same-family replacement. v5 completed all 175 requests
with zero retries, yielding a complete 60-task, 300-row analysis grid.

All 300 responses satisfied the four-field activation contract. Contextual
typed uptake was 60/60, while shuffled-typed uptake was 31/60, for a paired
difference of +0.4833 and 29/0 contextual-only/shuffled-only uses. Three of five
families had positive uptake differences: fact retrieval +1.0000, relation
inference +0.7500, and entity bridge +0.6667. Attribute comparison and bridge
attribute comparison both showed universal uptake under contextual and shuffled
bundles, so those families do not identify family-specific selection.

Alias-tolerant contextual accuracy was 53/60 versus 50/60 for shuffled, with
3/0 net wins, but 53/60 versus 54/60 for cold. Strict contextual accuracy was
49/60 versus 46/60 for shuffled and tied cold at 49/60. The frozen positive gate
passed and the stop rule did not fire. This establishes strong, family-sensitive
mechanism uptake under the frozen presentation; it does not establish a broad
accuracy gain over cold.

v5 used 439,441 exact tokens and CNY 0.940886 exact stage cost. The combined
known v3+v5 stage cost is CNY 1.557926. All authorizations are closed; later
stages and formal scaling remain separately gated. Analysis fingerprint:
`d228d3b907091a8001d3f3379bd1ad1ded2af1cf30dfe0c148226a6be9cc435f`.

## Phase 3C result: uptake-to-outcome mediation audit

Phase 3C reanalyzed the immutable Phase 3B 60-task, 300-row grid without any
new model call. The uptake strata were 29 contextual-only tasks and 31 tasks
where both contextual and shuffled bundles were adopted; neither-adopt and
shuffled-only were empty.

Within contextual-only tasks, the intermediate operation changed on 26/29
(0.8966), but the normalized final answer changed on only 1/29 (0.0345).
Alias-tolerant contextual accuracy produced zero net wins over shuffled and
zero net wins over cold; strict comparisons were also tied. The frozen positive
mediation gate therefore did not pass.

The 31/60 both-adopt rate triggered the prespecified specificity warning. Those
tasks contain all 24 attribute-comparison and bridge-attribute-comparison
examples, confirming that the remaining mechanism gap is not mere recognition:
the model must learn when to abstain from an irrelevant historical skill and
must translate a selected skill into an answer-relevant computation.

The gate is `inconclusive`, so immediate cross-domain scaling is not supported.
The next admissible stage is a zero-network Phase 3D specificity/abstention
preflight with a frozen mediation gate; any provider execution remains separately
authorized. No network, provider, model, paid, or formal-scaling call occurred.
Aggregate fingerprint:
`0e1769ea906c18907f7161aea5fd93b30add92738b6cce26be32091dfb1b30fd`.

## Phase 3D result: specificity and abstention preflight

Phase 3D converts the Phase 3C specificity warning into a frozen, zero-network
real-task design. It selects 40 entirely new tasks, 20 each from attribute
comparison and bridge attribute comparison, the two families implicated by
universal or near-universal irrelevant-bundle uptake.

Each task has six conditions: cold, global-only, contextual-only,
irrelevant-only, contextual-first dual candidates, and irrelevant-first dual
candidates. The dual conditions contain the same correct and irrelevant skill
bundles in reversed order. The response contract requires one applicability
assessment per candidate, an explicit selected skill ID or `none`, a short
intermediate operation, and the final answer.

The frozen positive gate is deliberately conjunctive. It requires contextual
selection, irrelevant-only rejection, correct dual selection under both orders,
a bounded order effect, operation and normalized-answer changes, alias net wins
over the irrelevant control, and non-regression versus cold. Specificity alone
does not authorize cross-domain scaling if answer mediation remains absent.

The schedule contains 240 unique requests with zero task, logical-call, or
request-hash overlap against scanned Phase 2/3A/3B/3C identities. It is a
proposal only; no authorization artifact exists and no network, provider, model,
paid, or formal-scaling call occurred. Aggregate fingerprint:
`59143bd2c63bf73c4f747121d547216a2665c7bd722fb7c672b0e12e9db2e5b0`.

## Phase 3D execution readiness: live preflight v2

The separately versioned v2 preflight revalidates and binds all 240 canonical
Phase 3D requests without modifying the frozen schedule. Every stored request
hash matches its canonical body, all logical-call and request identities remain
unique, and the 40-by-6 task-condition grid remains balanced.

The future execution boundary is now exact: Alibaba Cloud Token Plan Beijing
endpoint, `qwen3.7-plus`, temperature 0, thinking disabled, zero retries, no
`max_tokens`, JSON-object responses, one request per second, CNY 3.00 stage
ceiling, and CNY 15.00 cumulative ceiling. Request-start and response ledgers,
hash chains, exact usage accounting, first-failure terminal stop, exact-prefix
resume, and automatic authorization closure are mandatory.

This is readiness evidence only. No authorization receipt or open authorization
exists, and all network, provider, paid, later-stage, cross-domain, and formal-
scaling permissions remain closed. Execution requires the exact statement in
`authorization_request.json`. Preflight fingerprint:
`1b57aabe12711ef646674dc39dcc01990c8e0088c667c30fe0818d47c26f4970`.

## Phase 3D live result: strict contract failure and bounded diagnostic

The explicitly authorized v3 execution completed all 240 frozen calls with zero
retries, valid one-second pacing, unique request and provider identities, and
valid hash chains. It used 681,040 input and 26,209 output tokens (707,249
total) at CNY 1.571752 exact stage cost; the known cumulative lower bound is
CNY 8.790490. Authorization closed automatically.

The frozen strict result is **negative**: every response used a candidate-ID-
keyed `skill_assessments` mapping rather than the specified ordered array, so
0/240 responses satisfied the response contract. This is a contract failure,
not evidence that the model ignored the tasks.

A separately versioned, non-gating v3.1 diagnostic reconstructs presentation
order from those mappings solely to describe the spent responses. It finds
contextual-single and dual correct selection rates of 1.0000, zero dual order
effect, and irrelevant-only rejection of 0.6750, below the prespecified 0.75
threshold. Contextual-versus-irrelevant answer net wins are zero and contextual
has two net losses versus cold. The diagnostic cannot alter the strict negative
gate or authorize cross-domain scaling. Strict fingerprint:
`501f57df97267d3dae84fa953e0652102e5d003572d9e40c58d8a50010e22b29`.

## Phase 3E result: negative-control validity audit

Phase 3E is a zero-network audit of the spent Phase 3D ledger. It leaves the
strict negative gate unchanged, but checks whether each alleged irrelevant
single-candidate control was actually incapable of solving the target task.

The attribute-comparison bridge-attribute control was valid: it was applicable
and selected on 0/20 tasks. The bridge-attribute entity-bridge control was not
valid: it was applicable and selected on 13/20 tasks because film-to-director
bridging is a required first operation before comparing that director's
attribute. Those 13 responses cannot be used as evidence of indiscriminate
skill adoption or weak abstention.

Any Phase 3F redesign must treat candidate-ID-keyed assessments as the native
response contract (or pre-register deterministic normalization) and use a
bridge-family control incapable of providing the required bridge operation. It
must also use wholly new task identities and freeze an answer-sensitivity and
mediation gate before any separately authorized provider execution. No calls
were made. Fingerprint:
`ca9b53061590b7d11f45a355a4e19b177806e8366707a70ceb4e8005c5eb26e7`.

## Phase 3F result: repaired selector contract, unresolved answer mediation

The explicitly authorized Phase 3F v2 execution completed all 240 frozen calls
with zero retries, valid one-second pacing, unique logical/request/provider
identities, and valid request-start and response hash chains. It used 691,012
input and 20,228 output tokens (711,240 total) at CNY 1.543848 exact stage
cost; the known cumulative lower bound is CNY 10.334338. Authorization closed
automatically.

Under the frozen native candidate-ID mapping contract, 221/240 rows were
contract-valid and the prespecified gate is **inconclusive**: contextual
selection was 40/40, irrelevant rejection 25/40, dual correct selection 76/80,
and contextual-versus-irrelevant normalized-answer changes 16/40. The
descriptive boolean-mapping diagnostic admits 238/240 rows and shows repaired
selector specificity (irrelevant rejection 40/40; dual correct selection
78/80), but answer changes fall to 2/40, below the frozen 0.10 mediation
threshold. It cannot alter the strict decision.

Thus the evidence now separates two claims: response-shape and
operation-incompatible-control defects are largely repaired, but candidate
selection still does not reliably mediate into answer-relevant behavior. No
cross-domain or formal scaling is licensed. Strict fingerprint:
`d797e795ba5d6318cbeb01ce8ff7187949a134679a621a673855b216e3a3d0cc`.
Descriptive diagnostic fingerprint:
`96e6678979361ed7b840bc0b1e80ac4ddbf1b19ebbb49ede377a3379b224d0b4`.

## Phase 3G result: answer-grounding attribution

The zero-network Phase 3G audit reuses only the immutable Phase 3F boolean-
mapping diagnostic. Contextual versus operation-incompatible context changed
the declared operation on 19/20 attribute-comparison tasks and 10/20 bridge-
attribute tasks, but changed normalized final answers on only 1/20 in each
family. The remaining limitation is therefore answer grounding rather than a
selector-only failure. This audit made no external call and did not re-gate
Phase 3F.

## Phase 3H result: counterfactual answer-sensitivity preflight

Phase 3H v1 produced a zero-call design artifact with fingerprint
`9888dac8cef340a6fee5b09252ad19911d7febae5a4b7cf9dacb2b2df6dc906b`,
but its first regression suite contained a false-positive substring assertion.
It remains immutable, unaccepted provenance.

V2 excludes every v1 identity and freezes a scientifically valid replacement,
but its completion manifest used provider-call semantics (`completed_calls=0`)
instead of aggregate design-row semantics and omitted `rows`. Preserve v2 as
unaccepted zero-call provenance with fingerprint
`41a5e6f82c5503c09bf380f0489bcc5fef9af8343f4f46ab790c03ee7f956e64`.

The completion-schema-corrected v3 excludes every v1/v2 identity and freezes 40
wholly new 2WikiMultiHopQA tasks, 20 per comparison family. Each task preregisters two
distinct source-verifiable answers and evidence traces: the dataset answer
under the question's comparison direction and the other compared entity under
the inverse procedure. The five-condition schedule contains 200 unique proposed
requests across cold, contextual, forced incompatible-control, and reversed
dual orders. All prior task, logical-call, and request-hash overlaps are zero.

The primary gate is paired target-to-counterfactual answer grounding after an
observable operation change; selector uptake alone cannot pass the gate. V2
made zero network, provider, model, paid, later-stage, cross-domain, or formal-
scaling calls. Its manifest records `completed_calls=rows=200` design rows and
`provider_calls_executed=0`. Cache-free regressions passed 12/12. Accepted
fingerprint:
`61d55a4c3134c0ccf349aa400d3fd2333376b7e7775c3730a7a1016fc942eafb`.

The separately versioned v4 closed live-execution preflight now binds that
unchanged 200-row schedule to the Token Plan Beijing endpoint and
`qwen3.7-plus`, temperature 0, disabled thinking, zero retries, absent
`max_tokens`, JSON-object responses, one-second pacing, CNY 3.00 stage and CNY
15.00 cumulative ceilings, exact-prefix resume, request/response hash-chain
ledgers, first-failure terminal stop, and automatic closure. Its aggregate
fingerprint is
`9355217fec78e792e421cc12d807ad9846e3f50f84724d6856c0f3bc19aa5e23`.
The schedule audit preserves 40 tasks, 200 unique logical IDs and request
hashes, and 40 rows per condition; every external-call counter remains zero.

The proposal remains unauthorized. No receipt or open authorization exists. A
separately versioned v5 execution may be created only after the user sends
verbatim the exact statement in
`artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_live_preflight_v4/authorization_request.json`.
That authorization is limited to the frozen payload egress, route, model,
attempt count, pacing, retry rule, response format, and cost ceilings; other
models, later Phase 3, cross-domain scaling, and formal scaling remain closed.

## Phase 3H v5 execution

The explicitly authorized v5 execution completed all 200 frozen requests with
zero retries, valid one-second request-start pacing, 444,929 exact tokens, and
CNY 1.005082 exact stage cost. The authorization closed automatically; known
cumulative cost is CNY 11.339420. The frozen answer-grounding analysis admitted
40 primary-population task pairs: contextual target-answer rate was 0.825,
incompatible-control counterfactual-answer rate was 0.475, and paired
target-to-counterfactual grounding was 0.425. Neither frozen decision gate
fires, so the result is inconclusive. Cross-domain and formal scaling remain
closed, and none of the 200 spent requests may be retried or resumed.

## Phase 4B-R4 zero-network recovery preflight (2026-08-18)

R4 preserves 72 complete R3 responses as provenance, excludes all 73 spent R3
logical IDs and request hashes, and freezes 28 new canonical identities. One
row replaces orphan source sequence 73 and 27 rows cover source sequences
74-100. The orphan replacement has a new logical ID and request hash but
deliberately repeats the same provider-visible payload.

The combined plan restores the 100-row, 20-task balanced grid while retaining
80 unique payloads and 20 identical `global_only`/`contextual_typed` pairs. No
external call or authorization was created. Unknown orphan usage prevents R4
from freezing future cost ceilings. A new live preflight, explicit cost
treatment, and fresh exact authorization are required before provider
execution. Fingerprint:
`fc668155d0e1d787fe45bf381f5958d8f9d5d78759be3c0bab3951580254f066`.

## Phase 4B-R5 closed recovery live-execution preflight (2026-08-18)

R5 binds the immutable 28-row R4 recovery plan to the exact qwen3.7-plus
route, pacing, response, accounting, and terminal-stop contract. Unknown orphan
usage is reserved at CNY 0.011136, the maximum observed completed-response
local cost. The proposed stage ceiling is CNY 0.30 and the cumulative ceiling
is CNY 15.00, producing a projected known upper bound of CNY 12.640056.

No authorization or external call was created. Fingerprint:
`4b220ba56d8cf0990ecf86df791f79b8218db427c81a117b6c78a775d58f5a0d`.

## Phase 4B-R6 recovery execution and analysis (2026-08-18)

R6 completed the explicitly authorized 28-call recovery with zero retries,
valid pacing, 81,331 tokens, CNY 0.209612 stage cost, and automatic closure.
The R3+R6 combined population restores all 100 development rows: 100/100 are
strict contract-valid and evidence-ID resolving, and contextual selection is
1.0. The development calibration contract gate passes.

The 20 `global_only`/`contextual_typed` pairs remain transport-identical, so no
causal contrast between those labels is available. Phase 4C is not authorized.
Analysis fingerprint:
`80cc655e1dc70795b783ae671f55e9df064c552467db3a42295e795f46016048`.

## Phase 4C-D1 zero-network design admissibility diagnostic (2026-08-18)

The inherited Phase 4A held-out schedule is not admissible for Phase 4C. The
400-row audit finds zero transmitted rows with the exact six-field contract,
zero with copyable evidence IDs, and 80 identical
`global_only`/`contextual_typed` transport pairs. No authorization or external
call was created. A separately versioned repair design is required before any
Phase 4C live preflight. Fingerprint:
`57e2588f8183e4d8682f20dcf9d587fb37fe303142be1c340b616fbef68405c7`.

## Phase 4C-R1 repaired zero-network held-out design (2026-08-18)

R1 repairs the inherited Phase 4A held-out schedule without any external call.
It freezes 80 tasks and 400 rows with the exact six-field contract and evidence
IDs visible in every transmitted message. `global_only` and `contextual_typed`
now differ by substantive prior scope, yielding 400 unique transport payloads.
All spent Phase 4B logical/request identities are excluded. The design is not
authorized for live execution. Fingerprint:
`5c776023249499a5022fe901cae9f0684c22e30991fa9349a71e9af92b14bda3`.

## Current research-line reset (2026-08-22)

µ±Ç°Ö÷ÏßÎª `scope-aware-admission-answer-level-grounding`£¬È¨Íþ¼Æ»®¼û `paper/acl2027/ACTIVE_RESEARCH_PLAN.md`¡£

Ô­Ö÷Ïß `typed-scoped-prior-continual-routing` ÏÖ±ê¼ÇÎª `LEGACY / FROZEN / READ-ONLY`¡£¾É artifact¡¢ledger¡¢closure¡¢analysis ºÍ fingerprint Ö»ÔÊÐíÖ»¶ÁÖ¤¾Ý×ÛºÏÓëÊ§°ÜÕï¶Ï£¬²»µÃÓÃÓÚµ÷²Î¡¢ºòÑ¡¹¹Ôì¡¢held-out Ñ¡Ôñ»òÐÂ provider schedule¡£ºóÐøÊµÑé±ØÐë°ó¶¨µ±Ç°Ö÷Ïß±êÊ¶¡¢ÐÂ task/logical/request/transport identities ºÍÐÂµÄ zero-network preflight¡£

µ±Ç°Ö÷Ïß·Ö±ðÆÀ¹À candidate identity/scope¡¢admission¡¢operation/intermediate result¡¢evidence resolution¡¢final answer ºÍ counterfactual-answer avoidance£»selector uptake µ¥¶À²»¾ß±¸ gating ×Ê¸ñ¡£

## Phase 6 scope-aware admission zero-network preflight (2026-08-23)

Phase 6 freezes a new 40-task, 240-row 2WikiMultiHopQA schedule on the active
`scope-aware-admission-answer-level-grounding` line. It balances cold,
always-use typed, admission typed, shuffled typed, incompatible control, and
evidence-abstain conditions at 40 rows each. Every schedule identity is new:
task, logical-call, request, transport-payload, and provider-response identity
overlap with historical artifacts is zero.

The transmitted response contract has exactly seven top-level fields and uses a
candidate-ID keyed assessment object. Evidence IDs resolve only through the
canonical request's structured evidence map; empty, duplicate, unknown, and
cross-candidate IDs are rejected. Private target/counterfactual answers and
private exact admission expectations are not sent in the request.

The frozen design fingerprint is
`aecbd3c11dffd1f6860d663d3fe86fa144da4e8be4048aadf323ccd5b8e26ca6`.
The separately closed live preflight fingerprint is
`dfe7cbf6c9e4a8ad5da6298e9fe41a9b4b745cf404eb08b3e9c0f3443721fb3d`.
It only creates an authorization request, not a receipt; provider, paid,
model, cross-domain, and formal-scaling calls remain zero. Any live execution
requires the exact authorization statement in the Phase 6 artifact and is
otherwise forbidden.
