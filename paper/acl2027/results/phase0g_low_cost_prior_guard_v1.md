# Phase 0G ? Low-Cost Prior-Sanity Guard

**Status:** completed offline development calibration and held-out evaluation  
**Date:** August 7, 2026  
**Scope:** synthetic continual-routing evidence only; this phase does not establish downstream LLM accuracy.

## 1. Research question

Phase 0F showed that a charged prior-sanity guard can detect adversarial initial utility and recover the
all-cold performance of a learned router. Its full validation pass, however, added roughly 13.2k?13.6k
tokens per run and made guarded routing less token-efficient than Relevance Top-K.

Phase 0G asks whether the guard can retain that robustness with substantially fewer validation tokens by:

1. limiting probes per domain;
2. stopping sequentially once paired evidence is sufficient;
3. separating exact unamortized accounting from a clearly labelled baseline-sharing amortized view; and
4. selecting the sequential rule on development seeds before evaluating untouched held-out seeds.

## 2. Implementation and accounting

The continual-routing harness now supports:

- `prior_guard_max_probes_per_domain`;
- `prior_guard_sequential`;
- `prior_guard_confidence_z`;
- `prior_guard_min_samples`;
- `prior_guard_relevance_cost_share`.

For every paired guard probe, the learned router and Relevance Top-K are evaluated on the same event. The
sequential statistic is the confidence interval of:

```text
learned probe reward - relevance probe reward
```

After each complete cross-domain round, probing stops when either:

- the upper confidence bound is below `-tolerance` (`confident-harmful`); or
- the lower confidence bound is at least `-tolerance` (`confident-acceptable`).

Otherwise the guard continues to the configured maximum number of probes.

The exact token identity remains:

```text
total_tokens =
    inference_tokens
  + credit_update_tokens
  + probe_tokens
  + gate_validation_tokens
  + guard_validation_tokens
```

`total_tokens`, `tokens_to_target`, and `reward_per_1k_tokens` always include the full candidate-router and
Relevance validation cost. Baseline sharing is reported only through the separate
`guard_amortized_validation_tokens`, `amortized_total_tokens`, `amortized_tokens_to_target`, and
`amortized_reward_per_1k_tokens` fields. Amortized values therefore do not replace the exact primary
accounting.

## 3. Experimental separation

### Development calibration

- Config: `configs/acl2027/offline_continual_phase0g_dev_v1.json`
- Artifact: `artifacts/acl2027_continual_phase0g_dev_v1`
- Seeds: 31, 32, 33
- Grid: 3 seeds ? 2 prior conditions ? 12 methods = 72 runs
- Aggregate fingerprint: `474d9672397db61085e4608e8eeba1cd1ebad630e1604835c1014bd5c5cdfffc`

The development grid compared fixed 1/2/4/8-probe guards and sequential guards with confidence multipliers
`z=1.0` and `z=1.96`, alongside unguarded routers and baselines.

### Held-out evaluation

- Config: `configs/acl2027/offline_continual_phase0g_v1.json`
- Artifact: `artifacts/acl2027_continual_phase0g_v1`
- Seeds: 51, 52, 53
- Grid: 3 seeds ? 2 prior conditions ? 8 methods = 48 runs
- Aggregate fingerprint: `1f4ed16cf5a9abc90977977fdf1372b3e3428c83e1c878945bbbf1f177e65282`

The held-out method set was frozen after development calibration. The primary learned-router comparison used
shared credit because Phase 0F established that the guard can repair adversarial initialization without
requiring expensive oracle per-rule credit.

## 4. Development calibration results

| Guard variant | All-cold false resets | Adversarial detections | Mean all-cold guard tokens | Mean adversarial guard tokens | Mean rounds: all-cold / adversarial |
|---|---:|---:|---:|---:|---:|
| Fixed 1 probe/domain | 1/3 | 3/3 | 1,698 | 1,710 | 1.00 / 1.00 |
| Fixed 2 probes/domain | 1/3 | 3/3 | 3,418 | 3,418 | 2.00 / 2.00 |
| Fixed 4 probes/domain | 0/3 | 3/3 | 6,739 | 6,709 | 4.00 / 4.00 |
| Fixed 8 probes/domain | 0/3 | 3/3 | 13,600 | 13,594 | 8.00 / 8.00 |
| Sequential `z=1.0` | **0/3** | **3/3** | **5,581** | **3,418** | **3.33 / 2.00** |
| Sequential `z=1.96` | 0/3 | 3/3 | 6,710 | 5,130 | 4.00 / 3.00 |

The one-probe guard was cheapest but falsely reset one acceptable all-cold initialization. The selected
sequential `z=1.0` rule had no development false reset or adversarial miss and stopped earlier than
`z=1.96`. The Phase 0F tolerance of 0.06 was retained rather than retuned on held-out results.

## 5. Held-out aggregate results

All values are means over three seeds. `Target` is the number of runs reaching the sustained rolling reward
target of 0.72.

| Condition | Method | Reward | Total tokens | Guard tokens | Reward / 1k | Amortized reward / 1k | Trigger rate | Mean rounds | Target |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All-cold | Relevance Top-K | 0.7070 | 76,016 | 0 | **1.3964** | 1.3964 | ? | ? | 3/3 |
| All-cold | Fixed 0.5 shared, unguarded | 0.7085 | 74,811 | 0 | 1.4215 | 1.4215 | ? | ? | 3/3 |
| All-cold | Adaptive s4 shared, unguarded | 0.7079 | 74,750 | 0 | 1.4217 | 1.4217 | ? | ? | 3/3 |
| All-cold | Fixed guard, 1 probe/domain | 0.7085 | 76,540 | 1,730 | 1.3894 | 1.4033 | 0/3 | 1.00 | 3/3 |
| All-cold | Fixed guard, 4 probes/domain | 0.7085 | 81,656 | 6,845 | 1.3025 | 1.3524 | 0/3 | 4.00 | 3/3 |
| All-cold | Fixed sequential guard, `z=1.0` | 0.7085 | 81,451 | 6,641 | 1.3091 | 1.3555 | 0/3 | 4.00 | 3/3 |
| All-cold | Adaptive sequential guard, `z=1.0` | 0.7079 | 81,391 | 6,641 | 1.3082 | 1.3551 | 0/3 | 4.00 | 3/3 |
| All-cold | Oracle upper bound | 0.9857 | 74,440 | 0 | 1.9867 | 1.9867 | ? | ? | 3/3 |
| Adversarial | Relevance Top-K | 0.7070 | 76,016 | 0 | **1.3964** | 1.3964 | ? | ? | 3/3 |
| Adversarial | Fixed 0.5 shared, unguarded | 0.4903 | 73,934 | 0 | 0.9946 | 0.9946 | ? | ? | 0/3 |
| Adversarial | Adaptive s4 shared, unguarded | 0.5080 | 74,180 | 0 | 1.0279 | 1.0279 | ? | ? | 0/3 |
| Adversarial | Fixed guard, 1 probe/domain | 0.7085 | 76,489 | 1,678 | 1.3904 | 1.4043 | 3/3 | 1.00 | 3/3 |
| Adversarial | Fixed guard, 4 probes/domain | 0.7085 | 81,522 | 6,711 | 1.3046 | 1.3547 | 3/3 | 4.00 | 3/3 |
| Adversarial | Fixed sequential guard, `z=1.0` | 0.7085 | 78,208 | 3,398 | 1.3597 | 1.3869 | 3/3 | 2.00 | 3/3 |
| Adversarial | Adaptive sequential guard, `z=1.0` | 0.7079 | 78,148 | 3,398 | 1.3599 | 1.3871 | 3/3 | 2.00 | 3/3 |
| Adversarial | Oracle upper bound | 0.9857 | 74,440 | 0 | 1.9867 | 1.9867 | ? | ? | 3/3 |

## 6. Findings

### 6.1 Sequential validation preserved held-out robustness

The selected `z=1.0` sequential guards triggered in all 3/3 adversarial held-out runs and in 0/3 all-cold
held-out runs. They also reproduced the corresponding all-cold learned-router reward after resetting an
adversarial prior. Unguarded shared-credit methods still failed to reach the target in all adversarial runs,
whereas every guarded run reached it.

### 6.2 Sequential stopping substantially reduced Phase 0F guard cost

Relative to the roughly 13.2k?13.6k-token full guard used in Phase 0F:

- adversarial sequential validation used about 3.4k tokens, a reduction of roughly 74%;
- all-cold sequential validation used about 6.6k tokens, a reduction of roughly 51%;
- one-probe validation used about 1.7k tokens, a reduction of roughly 87%.

The sequential rule stopped after two rounds for every held-out adversarial seed, but required four rounds
for every held-out all-cold seed. This asymmetry is desirable for rapidly rejecting harmful priors, although
acceptable priors still carry a meaningful validation cost.

### 6.3 Exact-cost sequential routing remains below Relevance Top-K efficiency

For the fixed shared-credit router, exact reward per 1k tokens was:

- adversarial sequential guard: 1.3597 versus Relevance Top-K at 1.3964;
- all-cold sequential guard: 1.3091 versus Relevance Top-K at 1.3964.

With baseline-cost sharing shown only as a secondary accounting view, adversarial efficiency rose to 1.3869,
nearly matching Relevance Top-K, but all-cold efficiency remained lower at 1.3555. Therefore Phase 0G does
not yet justify the claim that the safe learned router dominates Relevance Top-K in cumulative-token
cost-effectiveness.

### 6.4 One-probe validation is promising but under-validated

On the held-out seeds, the one-probe guard achieved:

- 0/3 all-cold false resets;
- 3/3 adversarial detections;
- exact reward per 1k of 1.3894?1.3904, close to Relevance Top-K at 1.3964.

However, it falsely reset 1/3 all-cold development runs. The held-out result therefore cannot be interpreted
as proof of reliability. Selecting it as the paper's safe method after observing only three held-out seeds
would overfit the reliability decision.

### 6.5 This phase remains an offline simulator result

Phase 0G validates deterministic accounting, prior-failure diagnosis, and a lower-cost guard design. It does
not establish that the synthetic reward model predicts real SearchQA, MMLU-Pro, or tool-use outcomes. Paid
model experiments remain gated on a stable offline method and should use objective task outcomes.

## 7. Decision and next experiment

**Do not begin 128/512-rule scaling or paid API experiments yet.** The sequential guard is the safer method
across both development and held-out seeds, but only the riskier one-probe variant nearly matches Relevance
Top-K under exact accounting.

The next experiment is a larger-seed reliability diagnostic using new seeds and only five methods:

1. Relevance Top-K;
2. unguarded fixed 0.5 shared credit;
3. fixed one-probe guard;
4. fixed sequential `z=1.0` guard;
5. oracle upper bound.

With seeds 61?80 and both all-cold and adversarial conditions, the grid contains 200 inexpensive synthetic
runs. Primary outputs are the all-cold false-reset rate, adversarial miss rate, reward mean and standard
deviation, exact reward per 1k tokens, guard-token distribution, target success, and sequential-round
distribution.

The project may proceed to 128/512 scaling only if the expanded reliability evidence shows an acceptably low
one-probe error rate or identifies a sequential/stratified probe strategy that approaches Relevance Top-K's
exact token efficiency without sacrificing prior safety.
