# Phase 0D: Credit Identifiability and Total-Token Cost (v1)

## Scope and audit

This phase is synthetic offline instrumentation, not downstream LLM accuracy.

- Artifact: `artifacts/acl2027_continual_phase0d_v1`
- Config: `configs/acl2027/offline_continual_phase0d_v1.json`
- Grid: 3 seeds ? 2 initialisations ? 2 corruption settings ? 8 methods = **96/96 runs**
- Corruption moved to block 4; drift begins at block 3
- The same corruption permutation is now used across paired methods
- Tests: **26 passed**
- Manifest/file-hash audit: **96/96 passed**
- Total-token identity audit: **96/96 passed**
- Aggregate fingerprint: `75b3fc53f274336ceb3b2a12152d1a1092754cc8ac5ebcf5ca41962598b3375a`

## Question 1: Does contextual estimation beat global estimation when credit is clean?

Not universally.

| Credit | Mean Contextual ? Global reward | Contextual wins | Mean token delta | Harmful-selection delta |
|---|---:|---:|---:|---:|
| Shared | ?0.0067 | 4/12 | ?176 | +0.0079 |
| Oracle per-rule | ?0.0010 | 8/12 | ?367 | +0.0058 |
| Leave-one-out | ?0.0010 | 8/12 | ?163 | +0.0058 |

The aggregate mean hides a strong interaction with utility initialisation:

| Initial utility | Corruption | Contextual Oracle Credit ? Global Oracle Credit |
|---|---|---:|
| All-cold | None | **+0.0105** |
| All-cold | Shuffled after drift | **+0.0153** |
| Adversarial | None | **?0.0178** |
| Adversarial | Shuffled after drift | **?0.0122** |

Interpretation:

- With a neutral cold start, contextual estimates learn useful domain-specific distinctions.
- With an adversarial prior, splitting evidence across domains slows correction. Global pooling gets more
  updates per rule and can erase the bad prior faster.
- A fixed context weight therefore cannot be the final method. The estimator needs confidence-aware
  shrinkage between global and local evidence.

## Question 2: Is leave-one-out credit worth its cumulative token cost?

No.

Oracle per-rule credit and leave-one-out use the same marginal-credit target in the synthetic harness.
They produced identical rewards and selections in **12/12 paired conditions** for both estimators.

| Estimator | LOO / Oracle-credit total-token ratio | Mean extra tokens/run | Reward difference |
|---|---:|---:|---:|
| Global | **2.365?** | +105,250 | 0.0000 |
| Contextual | **2.374?** | +105,454 | 0.0000 |

Thus, clean per-rule credit is valuable, but obtaining it through a full counterfactual model rerun per
selected rule is not token-efficient. Future work must approximate marginal credit from cheaper signals,
for example a learned critic, sparse probes, delayed batched attribution, or occasional counterfactual
calibration rather than per-task leave-one-out.

## Question 3: Can drift and corruption recovery now be separated?

Yes. Drift starts at block 3 and corruption at block 4.

Under all-cold + oracle per-rule credit:

- Contextual drift recovery: 3/3 successes, mean **7,267 tokens**.
- Global drift recovery: 3/3 successes, mean **12,409 tokens**.
- Contextual post-corruption recovery: 3/3 successes, mean **15,554 tokens**.
- Global post-corruption recovery: 1/3 successes; the successful run required 8,604 tokens.

Under adversarial + oracle per-rule credit:

- Contextual drift recovery: 3/3, mean **22,915 tokens**.
- Global drift recovery: 3/3, mean **31,572 tokens**.
- Contextual post-corruption recovery: 3/3, mean **17,670 tokens**.
- Global post-corruption recovery: 3/3, mean **17,857 tokens**.

Contextual state therefore often adapts faster after a change once it has useful evidence, even though
its early adversarial-prior reward can be worse. This reinforces the case for time-varying shrinkage:
strong global sharing early, stronger local weighting after domain evidence accumulates.

## ACL-path decision

Do **not** start 128/512 scaling or paid API experiments yet.

The next offline experiment should test the estimator itself:

1. Sweep fixed context weights: 0.0, 0.25, 0.5, 0.75, 1.0.
2. Add confidence-adaptive context weight based on local versus global effective sample size.
3. Compare under both all-cold and adversarial initialisation.
4. Use oracle per-rule credit first to isolate estimator quality; then repeat the best variants with
   shared credit to measure robustness to noisy attribution.
5. Preserve total-token accounting and report recovery after drift and corruption separately.

Proceed to larger libraries only if an adaptive estimator improves both cold-start and adversarial
conditions without requiring leave-one-out cost.
