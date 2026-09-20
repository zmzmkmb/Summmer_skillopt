# Phase 0H: Helpful Priors, Informative Probes, and Cold-Router Reference (Development v1)

Date: 2026-08-07

## Scope

This phase is a synthetic, fully offline development diagnostic. It does **not** establish downstream LLM or agent accuracy. It asks whether a charged prior-sanity guard can simultaneously:

1. retain a beneficial non-cold utility prior;
2. reject an adversarial prior;
3. avoid false resets from an all-cold state;
4. remain token-efficient.

The evaluation uses exact token accounting:

```text
total_tokens = inference_tokens + credit_update_tokens + probe_tokens
             + gate_validation_tokens + guard_validation_tokens
```

## Artifacts

Original informative-probe development grid:

- config: `configs/acl2027/offline_continual_phase0h_dev_v1.json`
- artifact: `artifacts/acl2027_continual_phase0h_dev_v1`
- grid: 5 seeds (81-85) x 3 priors x 7 methods = 105/105 runs
- aggregate fingerprint: `414b5a6225bcd4eef4d81fa9074903dd176c351856bf0b3e8c18bf83d7fa3bf9`

Cold-router reference diagnostic:

- config: `configs/acl2027/offline_continual_phase0h_cold_reference_dev_v1.json`
- artifact: `artifacts/acl2027_continual_phase0h_cold_reference_dev_v1`
- grid: 5 seeds (81-85) x 3 priors x 6 methods = 90/90 runs
- aggregate fingerprint: `048bbcaa7488f2cb579085330bb4aacc28736daa91820a1b3e8c8fd703928028`

Audit of the cold-router artifact:

- missing runs: 0
- file-hash failures: 0
- schema/config failures: 0
- exact token-identity failures: 0
- paired reference-accounting failures: 0

Relevant regression suite after implementation: **44 passed**.

## Implementation

`MethodSpec` now supports:

```python
prior_guard_probe_order: str = "stream"
prior_guard_reference: str = "relevance"
```

Valid reference comparators are:

- `relevance`: learned router versus Relevance Top-K;
- `cold-router`: current learned prior versus the same policy, estimator, context settings, top-k, and budget initialized at utility 0.5.

Both sides use paired probe events, and both sides' full tokens are charged. The artifact records reference scores, reference tokens, selected rule IDs, probe plans, stop reasons, actions, and reset magnitude.

## Result 1: the helpful prior is real

The unguarded fixed contextual router produced:

| Prior condition | Mean reward |
|---|---:|
| All-cold | 0.7181 |
| Oracle/helpful | 0.7553 |
| Adversarial | 0.5101 |

Thus the oracle prior improves mean reward by 0.0372 over all-cold, while the adversarial prior causes a severe collapse. A valid guard must preserve the former and reject the latter.

## Result 2: cold-router comparison fixes the all-cold informative false trigger, but not helpful-prior retention

| Cold-router guard | All-cold triggers | Oracle false resets | Adversarial detections | Mean guard tokens: all-cold / oracle / adversarial |
|---|---:|---:|---:|---:|
| One probe, stream order | 0/5 | 3/5 | 5/5 | 1,662 / 1,685 / 1,661 |
| Sequential z=1.0, stream order | 0/5 | 1/5 | 5/5 | 3,365 / 5,154 / 3,357 |
| One probe, disagreement order | 0/5 | 4/5 | 5/5 | 1,662 / 1,738 / 1,721 |
| Sequential z=1.0, disagreement order | 0/5 | 1/5 | 5/5 | 3,365 / 7,933 / 3,460 |

Compared with the earlier Relevance-reference informative one-probe guard, cold-router comparison removes the 2/5 all-cold false triggers. This is expected: an all-cold learned state and the same router initialized cold are paired-equivalent.

However, it does **not** solve the central helpful-prior problem. Stream-order one-probe still resets 3/5 helpful priors. Sequential validation improves this to 1/5, but seed 83 is still incorrectly reset after six rounds and 10,427 guard tokens.

## Result 3: false resets have material opportunity cost

For stream-order one-probe, the three helpful-prior false resets lose the following mean-reward opportunity relative to the unguarded helpful router:

```text
seed 81: -0.0427
seed 83: -0.0540
seed 84: -0.0457
mean:    -0.0475
```

For sequential stream order, the remaining seed-83 false reset loses 0.0540 mean reward.

This confirms that all-cold false-trigger counting was insufficient: resetting cold to cold is a no-op, while resetting a useful learned state destroys real value.

## Result 4: selection-disagreement ordering is a negative result

Selection-disagreement ordering does not provide a safe low-cost fix:

- one-probe oracle false resets worsen from 3/5 to 4/5;
- sequential oracle false resets remain 1/5;
- sequential oracle guard cost rises from 5,154 to 7,933 tokens on average;
- adversarial detection remains 5/5, so the extra cost does not buy a better harmful-prior decision.

It should remain a documented diagnostic/ablation, not be promoted as the proposed method.

## Interpretation

The cold-router reference is conceptually better than using Relevance Top-K as the reset comparator, but the present guard is still **myopic**. It evaluates frozen, one-step route outcomes on probes. It does not let either copied state perform online credit updates during a short trajectory.

That mismatch matters because the paper's objective is cumulative token-to-convergence efficiency. A prior can have noisy or locally negative immediate probe reward yet improve the subsequent learning trajectory. Seed 83 is direct evidence: the oracle prior improves full-stream reward from the all-cold level, but the frozen-probe guard concludes that it is harmful.

Therefore the current result does not support the claim that the prior guard is safe. It supports a narrower claim:

> Comparing against the same router initialized cold removes comparator-induced all-cold asymmetry, but frozen point probes remain an unreliable proxy for the value of a learned prior over an online learning trajectory.

## Decision and next phase

Do not promote one-probe, selection-disagreement, or the current frozen sequential guard. Keep Relevance Top-K as a global experimental baseline, and keep cold-router as the counterfactual reference.

Proceed to **Phase 0I: rollout-aware cold-router validation**:

1. clone the learned and cold states;
2. run both through the same short, stratified held-out/replay trajectory;
3. apply each method's actual credit updates to its cloned state;
4. compare cumulative reward, cumulative tokens, and reward-per-token/AUC rather than only frozen immediate reward;
5. use sequential retain-by-default stopping and charge both trajectories exactly;
6. test whether seed 83 is retained while all 5 adversarial priors are still rejected.

Paid API evaluation and formal 128/512 scaling remain deferred until this gate is passed.
