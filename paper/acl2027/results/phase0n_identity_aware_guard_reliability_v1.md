# Phase 0N: frozen identity-aware guard held-out reliability v1

## Status and scope

**Status:** completed held-out synthetic reliability evaluation; all predeclared gates passed.  
**Config:** `configs/acl2027/offline_continual_phase0n_identity_aware_guard_reliability_v1.json`  
**Artifact:** `artifacts/acl2027_continual_phase0n_identity_aware_guard_reliability_v1/`  
**Seeds:** 161-180, frozen before execution and disjoint from Phase 0J development 81-85, spent Phase 0K held-out 101-120, Phase 0L development 121-140, and Phase 0M development 141-160.  
**Runs:** 160 = 20 seeds x 2 prior conditions x 4 frozen methods.  
**Claim boundary:** synthetic routing reliability and exact token-accounting evidence only. This phase is not downstream LLM accuracy, paid evaluation, or formal 128/512-rule scaling.

The four method specifications, including every guard threshold, horizon, probe-order, fallback action, and `prior_guard_min_accept_rounds=8`, were copied unchanged from Phase 0M. No code or threshold change was made after freezing seeds 161-180.

## Frozen held-out gates

1. **Safety:** at most 1/20 adversarial accepts and 0/40 selective candidate-state mutations.
2. **Usefulness:** oracle candidate mean reward no more than 0.005 below copied-global reset.
3. **Token cost:** oracle candidate mean total tokens at most 15% above global-only reset.
4. **Integrity:** all 160 runs, raw config SHA, artifact file hashes, config/stream/run/aggregate fingerprints, prior identities, action semantics, and exact run/round token identities must validate.

## Main held-out results

### Oracle priors

| Method | Mean reward | Mean total tokens | Mean guard tokens | Guard actions |
|---|---:|---:|---:|---|
| copied-global + reset | 0.752795 | 84,854.8 | 8,485.6 | 5 false resets |
| global-only + reset | 0.793487 | 80,984.0 | 4,892.6 | 0 false resets |
| contextual + reset | 0.823797 | 81,068.5 | 4,292.0 | 0 false resets |
| global-only + selective | 0.789529 | 89,619.0 | 13,560.7 | 18 accepts, 2 abstentions |

The frozen selective candidate exceeded copied-global reset by **+0.036734 mean reward**. The paired 95% t interval was **[+0.025156, +0.048311]**. It therefore passed the usefulness floor by a wide margin.

Global-only identity correction remained the dominant gain: global-only reset exceeded copied-global reset by **+0.040692**. Explicit contextual priors added **+0.030309** over global-only reset. The selective candidate was **-0.003959** below global-only reset on average, primarily because seeds 164 and 173 produced full-horizon ambiguous evidence and safely abstained to cold fallback rather than deploying the candidate.

The selective candidate added **8,635.05 mean tokens** over global-only reset. Its total-token ratio was **1.106627**, or a **10.66% overhead**, below the predeclared 15% ceiling.

### Adversarial priors

| Method | Mean reward | Mean total tokens | Mean guard tokens | Guard actions |
|---|---:|---:|---:|---|
| copied-global + reset | 0.738410 | 79,780.5 | 4,194.9 | 20 resets |
| global-only + reset | 0.721723 | 82,622.6 | 6,946.5 | 17 resets, 3 retains |
| contextual + reset | 0.738410 | 79,348.3 | 3,762.8 | 20 resets |
| global-only + selective | 0.734397 | 83,726.3 | 8,130.5 | 1 accept, 14 rejects, 5 abstentions |

The candidate accepted **1/20** adversarial priors, exactly the maximum allowed by the frozen safety gate. It rejected 14 and abstained on 5. Every reject or abstention routed through a fresh cold fallback, and candidate-state mutation was **0/40** across oracle and adversarial candidate runs.

The accepted adversarial case was seed 176. Its full-confirmation probe margin was only -0.007795, so the evidence classified it as acceptable relative to the -0.06 boundary, yet its downstream stream reward was 0.655389 versus 0.735664 for the copied-global/contextual cold-fallback comparators. This does not invalidate the predeclared pass, but it shows that the pass has **no adversarial safety slack** and that probe-to-stream representativeness remains the main unresolved risk.

## Gate decision

| Gate | Measurement | Decision |
|---|---|---|
| Frozen candidate | Phase 0N methods exactly equal Phase 0M methods; seeds 161-180 disjoint | Pass |
| Artifact integrity | 160/160 runs; zero file/config/stream/run/aggregate/token audit failures | Pass |
| Prior identity | zero identity or domain-initialization failures | Pass |
| Non-destructive semantics | 0/40 mutations; exact decision/action mappings | Pass |
| Safety | 1/20 adversarial accepts, allowed maximum 1/20 | Pass, at boundary |
| Usefulness | candidate - copied-global = +0.036734, required >= -0.005 | Pass |
| Token cost | candidate/global-only = 1.106627, required <= 1.15 | Pass |

**Overall predeclared held-out gate: pass.**

Aggregate fingerprint: `72f5973bb697ebd12334ccb0737599154a51a50273e218ac7fe2aeab97914a02`.  
Raw config SHA-256: `b3050b75c43c269b9618822a46de3c7abf447ba1fa6c200323e1252f9866b85b`.  
Audit: `artifacts/acl2027_continual_phase0n_identity_aware_guard_reliability_v1/audit_report.json`.

## Interpretation

Phase 0N independently confirms three points:

1. **Prior identity is a reproducible effect.** Global-only initialization again removes copied-global false resets and improves held-out reward; explicit contextual priors remain stronger when valid per-domain information exists.
2. **Non-destructive abstention is reliable.** Ambiguous and harmful evidence can decline deployment without corrupting the candidate state, and this contract passed every audit.
3. **Full confirmation is safe enough for the predeclared gate but not risk-free or cheap.** It consumed 10.66% extra total tokens, abstained on 2/20 helpful priors, and accepted one adversarial prior whose probe behavior did not predict its downstream harm.

Accordingly, this result supports a narrower paper claim around **typed/scoped priors, representativeness-aware validation, and non-destructive abstain/escalate semantics**. It does not support a zero-failure safety claim or a general claim that guard validation improves token efficiency.

## Decision and next phase

The complete held-out pass permits downstream-evaluation and formal-scaling **planning** to reopen. It does not automatically authorize paid calls or a large scaling run. The next phase should freeze a small, budget-capped real-task pilot protocol and complete no-cost harness/configuration preflight before changing paid-API permission. Seed 176 must remain a reported held-out result and must not be used for post-hoc threshold tuning.
