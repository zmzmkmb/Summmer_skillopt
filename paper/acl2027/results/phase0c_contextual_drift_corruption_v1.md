# Phase 0C: Contextual Utility, Drift, and Corruption Recovery (v1)

## Scope

This phase is **synthetic offline instrumentation only**. It validates routing, credit assignment,
non-regression gating, drift/corruption recovery, and full token accounting. It does **not** establish
real downstream LLM accuracy.

## Configuration

- Artifact: `artifacts/acl2027_continual_phase0c_v1`
- Config: `configs/acl2027/offline_continual_phase0c_v1.json`
- Grid: 3 seeds ? 2 utility initialisations ? 2 corruption settings ? 8 methods = **96/96 runs**
- Rules: 48 (specialist, shared-transfer, cross-domain conflict, malicious, duplicate)
- Domains: SearchQA, Law, Health
- Stream: 6 blocks ? 25 tasks = 150 tasks/run
- Drift: phase 1 begins at block 3
- Selection: top-k=3, dynamic-rule budget=170 tokens
- Aggregate fingerprint: `ef2b4c309759476892f52de8ef99bfc19dfd1130845fdb315fbb519afaad63da`

Artifact audit passed:

- 96 run files present
- 96/96 file hashes match the manifest
- 96/96 runs satisfy
  `total_tokens = inference_tokens + credit_update_tokens + probe_tokens + gate_validation_tokens`
- Test suite: 25 passed

## Main results

### 1. Context alone did not beat the global estimator under shared credit

Across all 12 paired seed/condition/corruption comparisons:

| Comparison | Mean reward delta | Wins | Mean token delta | Harmful-selection delta |
|---|---:|---:|---:|---:|
| Contextual Greedy Shared ? Global Greedy Shared | **?0.0118** | 3/12 | ?7 | +0.0093 |

Breakdown of the reward delta:

| Initial utility | Corruption | Contextual ? Global |
|---|---|---:|
| All-cold | None | ?0.0007 |
| All-cold | Shuffled midstream | ?0.0108 |
| Adversarial | None | ?0.0181 |
| Adversarial | Shuffled midstream | ?0.0176 |

Therefore, Phase 0B's failure to show a contextual advantage was not solved merely by adding
context-dependent ground truth. The shared bundle reward remains too noisy to identify which selected
rule helped or hurt.

### 2. Per-rule credit produced a consistent improvement

Replacing shared credit with synthetic oracle per-rule credit for the contextual estimator gave:

| Comparison | Mean reward delta | Wins | Mean token delta | Harmful-selection delta |
|---|---:|---:|---:|---:|
| Contextual Oracle Credit ? Contextual Shared | **+0.0553** | **12/12** | +1,316 | **?0.0973** |

Representative aggregate conditions:

| Condition | Shared reward | Oracle-credit reward | Shared harmful rate | Oracle-credit harmful rate |
|---|---:|---:|---:|---:|
| All-cold, no corruption | 0.7423 | **0.7981** | 0.3110 | **0.1892** |
| All-cold, shuffled | 0.7362 | **0.7697** | 0.3134 | **0.2297** |
| Adversarial, no corruption | 0.5180 | **0.5999** | 0.4205 | **0.3056** |
| Adversarial, shuffled | 0.5763 | **0.6263** | 0.3685 | **0.2997** |

This is the strongest Phase 0C result: **credit assignment, not the selector formula, is the current
bottleneck**. It also identifies a concrete research target: obtain useful per-rule credit without the
unacceptable cumulative cost of repeated leave-one-out model calls.

### 3. Relevance Top-K remains a strong and robust baseline

Relevance Top-K achieved mean reward **0.7435** at **77,293 tokens** in every utility/corruption
condition because it does not consume learned utilities. Global Greedy Shared only slightly matched it
under all-cold initialisation, and failed badly under adversarial initialisation:

| Method / condition | Mean reward | Mean total tokens |
|---|---:|---:|
| Relevance Top-K | **0.7435** | 77,293 |
| Global Greedy Shared, all-cold/no corruption | 0.7430 | **75,383** |
| Contextual Greedy Shared, all-cold/no corruption | 0.7423 | 75,660 |
| Global Greedy Shared, adversarial/no corruption | 0.5361 | 75,077 |
| Contextual Greedy Shared, adversarial/no corruption | 0.5180 | 74,433 |
| Oracle upper bound | **0.9831** | 75,414 |

The large gap from 0.7435 to the 0.9831 oracle upper bound confirms substantial room for better
routing, but current online learning does not reliably close it.

### 4. UCB exploration helped adversarial starts but hurt all-cold starts

Relative to Contextual Greedy Shared, Contextual UCB Shared had a mean reward delta of **+0.0126**
across all 12 comparisons, but only won 6/12 and added about **1,794 tokens**. It was useful under
adversarial initialisation and generally harmful under all-cold initialisation. This supports an
adaptive exploration schedule rather than always-on UCB.

### 5. Current non-regression gates are not cost-effective

| Gate | Mean token overhead vs ungated contextual | Mean reward delta | Mean forgetting delta | Mean acceptance |
|---|---:|---:|---:|---:|
| Hard non-regression | **+44.4%** | ?0.0072 | ?0.0076 | 72.2% |
| Balanced | **+44.0%** | ?0.0166 | +0.0130 | 48.6% |

The hard gate slightly reduced forgetting, but its validation cost is too high and it did not improve
mean reward. The balanced gate was worse on both reward and average forgetting in this setup. Gate
work should pause until the underlying utility updates are more reliable; otherwise the gate spends
extra tokens validating noisy states.

### 6. Recovery evidence is promising only with clean per-rule credit

For all-cold initialisation, Contextual Oracle Credit recovered after drift in all 3 seeds:

- no corruption: mean **7,267 tokens**
- shuffled midstream: mean **9,476 tokens**

Shared contextual credit was slower:

- no corruption: mean **22,589 tokens**
- shuffled midstream: 2/3 successes, mean **29,131 tokens** among successes

Under adversarial initialisation, Oracle Credit recovered in 2/3 seeds without corruption and 3/3
with shuffled corruption. The apparent improvement after shuffling is not evidence that corruption is
beneficial: shuffling an adversarially reversed prior can partially randomise away the bad ordering.

## Important design limitation discovered

In v1, shuffled corruption is applied at block 3, exactly when drift phase 1 begins. Therefore
`corruption_recovery_tokens` and `post_drift_recovery_tokens` share the same starting point and cannot
cleanly separate recovery from estimator corruption versus environmental drift. This does not affect
the routing reward comparisons, but it limits causal interpretation of the two recovery metrics.

A second v1 limitation is that the corruption permutation was seeded with the method name, so paired
methods did not receive exactly the same shuffled estimator state. No-corruption conclusions remain
valid, but shuffled-condition method deltas should be treated as exploratory. The runner is corrected
for the next phase.

The next diagnostic must move corruption to a later block and compare global versus contextual
estimators under the same clean per-rule credit.

## Decision

**Do not proceed to 128/512 rules or paid API experiments yet.** Scaling the current shared-credit
learner would mainly produce a larger and more expensive version of an already identified failure.

The next experiment should be a focused credit-identifiability study:

1. Global Shared vs Contextual Shared.
2. Global Oracle Per-Rule vs Contextual Oracle Per-Rule.
3. Global Leave-One-Out vs Contextual Leave-One-Out, charging all counterfactual tokens.
4. Move shuffled corruption from block 3 to block 4 so drift and corruption recovery are separated.
5. Add an adaptive exploration method that turns exploration on only when calibration/rank
   correlation degrades.

Proceed to 128/512 scaling only if contextual estimation beats global estimation under clean per-rule
credit, and if an affordable credit approximation preserves most of that gain.
