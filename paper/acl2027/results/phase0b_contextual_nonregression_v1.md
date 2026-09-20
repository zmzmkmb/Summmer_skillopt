# Phase 0B ? Contextual Utility and Non-Regression Gates (v1)

**Run date:** August 6, 2026  
**Scope:** deterministic synthetic/offline instrumentation only; these rewards are not downstream LLM accuracy.  
**Config:** `configs/acl2027/offline_continual_phase0b_v1.json`  
**Artifacts:** `artifacts/acl2027_continual_phase0b_v1/`  
**Grid:** 3 seeds ? 2 utility conditions ? 9 methods = **54/54 completed runs**  
**Aggregate fingerprint:** `a43b26f385c9819d8ed1f18b55bb002e81890bb04398c6b11d28ab6d98498041`

## What was added

- Contextual utility state with global and per-domain posterior statistics.
- Context-aware Greedy, UCB, and Thompson selection.
- Snapshot/rollback at domain-block boundaries.
- Hard non-regression and balanced safety/plasticity gates.
- Explicit gate validation-token accounting.
- Gate acceptance, rejection, safety violation, plasticity, and worst-regression metrics.
- Backward-compatible Phase 0A aggregation.
- Tests for contextual isolation, cloning, gate decisions, token accounting, and deterministic fingerprints.

## Main results

### All-Cold initialization

| Method | Mean reward | Mean total tokens | Reward / 1K tokens | Avg. forgetting | Gate acceptance |
|---|---:|---:|---:|---:|---:|
| Relevance Top-K | 0.3975 | 56,872 | 0.8384 | 0.0000 | ? |
| Global Greedy shared | 0.3959 | 56,634 | 0.8387 | 0.0106 | ? |
| Contextual Greedy shared | 0.3959 | 56,630 | 0.8388 | 0.0106 | ? |
| Contextual UCB shared | 0.3666 | 57,439 | 0.7658 | 0.0169 | ? |
| Contextual Thompson shared | 0.3647 | 56,543 | 0.7736 | 0.0252 | ? |
| Contextual Greedy LOO | 0.3975 | 143,713 | 0.3321 | 0.0000 | ? |
| Contextual Greedy + hard gate | 0.3959 | 77,995 | 0.6090 | 0.0000 | 91.7% |
| Contextual Greedy + balanced gate | 0.3951 | 78,028 | 0.6076 | 0.0000 | 50.0% |
| Oracle upper bound | 0.8292 | 49,240 | 2.0205 | 0.0000 | ? |

### Adversarial initialization

| Method | Mean reward | Mean total tokens | Reward / 1K tokens | Avg. forgetting | Gate acceptance |
|---|---:|---:|---:|---:|---:|
| Relevance Top-K | 0.3975 | 56,872 | 0.8384 | 0.0000 | ? |
| Global Greedy shared | 0.3846 | 56,731 | 0.8134 | 0.0051 | ? |
| Contextual Greedy shared | 0.3843 | 56,755 | 0.8124 | 0.0050 | ? |
| Contextual UCB shared | 0.3409 | 57,416 | 0.7125 | 0.0151 | ? |
| Contextual Thompson shared | 0.3746 | 56,724 | 0.7927 | 0.0418 | ? |
| Contextual Greedy LOO | 0.3910 | 143,863 | 0.3261 | 0.0099 | ? |
| Contextual Greedy + hard gate | 0.3843 | 78,136 | 0.5901 | 0.00002 | 91.7% |
| Contextual Greedy + balanced gate | 0.3833 | 78,172 | 0.5883 | 0.000002 | 75.0% |
| Oracle upper bound | 0.8292 | 49,240 | 2.0205 | 0.0000 | ? |

## Findings

1. **The current contextual estimator is effectively redundant in this simulator.** Contextual Greedy and global Greedy are nearly identical. Each synthetic rule has one fixed home domain and one global true utility, while relevance already removes most cross-domain rules. The stream therefore contains little context-dependent utility for a contextual learner to discover.

2. **Shared credit still does not beat Relevance Top-K.** Under All-Cold, contextual Greedy is 0.0017 reward below Relevance Top-K. Under adversarial utility it is 0.0132 below.

3. **Leave-one-out remains economically unattractive.** It reaches approximately Relevance Top-K reward under All-Cold, but uses **2.53?** the total tokens and drops reward-per-1K-token from 0.8384 to 0.3321.

4. **The gates are operational rather than degenerate.** The hard gate accepts 91.7% of blocks, while the balanced gate accepts 50.0% under All-Cold and 75.0% under adversarial initialization. Safety is therefore not obtained by rejecting every update.

5. **The gates remove measured forgetting, but at high validation cost.** Hard-gate forgetting falls from 0.0106 to 0.0000 in All-Cold and from 0.0050 to approximately 0.00002 under adversarial initialization. However, validation adds about 21.4K tokens per run, raising total cost by roughly 37.7% over ungated contextual Greedy and reducing reward-per-1K-token to about 0.59?0.61.

6. **Only the oracle reaches the configured 0.72 token-to-target threshold.** All non-oracle methods record zero successful seeds. This confirms substantial selector headroom, but also means the current target is useful primarily as a separation diagnostic.

## Decision

**Do not start paid API experiments yet.** Phase 0B validates the gate mechanics and honest cost accounting, but it does not validate contextual learning as a method contribution.

The next experiment should revise the offline stream so that rule utility is genuinely context-dependent. The minimum next simulator must include:

- shared rules whose utility differs by domain;
- positive transfer rules;
- negative-transfer/conflicting rules;
- domain drift that changes rule utility over time;
- duplicate and malicious distractors;
- recovery metrics after utility corruption.

After that revision, rerun global versus contextual estimators and gate variants. Only if contextual learning improves reward or token-to-target while the gate preserves non-trivial acceptance should the project advance to the 128/512 scale sweep and then small paid-model validation.

## Verification

```text
20 passed in 3.65s
54/54 Phase 0B runs completed
```
