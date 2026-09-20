# Phase 0L: Prior Identity and Probe Representativeness Diagnostic (v1)

**Status:** completed; predeclared development diagnostic gate passed  
**Date:** August 7, 2026  
**Scope:** synthetic offline diagnosis only; seeds 101-120 are labeled spent-held-out post-hoc evidence, seeds 121-140 are fresh development evidence, and no paid model/API calls, formal 128/512 scaling, or downstream LLM accuracy claims are included.

## 1. Question

Why did the frozen Phase 0K guard falsely reset the nominally helpful oracle prior on seeds 101, 108, and 113, while accepting the adversarial prior on seed 109? Specifically, are these failures explained by an insufficient reset horizon alone, or by a mismatch in prior identity and probe representativeness?

## 2. Frozen protocol and integrity constraints

- Phase 0K post-hoc source: `artifacts/acl2027_continual_phase0k_adaptive_rollout_reliability_v1`
- Phase 0L config: `configs/acl2027/offline_continual_phase0l_probe_representativeness_dev_v1.json`
- Phase 0L artifact: `artifacts/acl2027_continual_phase0l_probe_representativeness_dev_v1`
- Development seeds: 121-140
- Disjointness: seeds 121-140 are disjoint from Phase 0J seeds 81-85 and spent Phase 0K seeds 101-120
- Grid: 20 seeds x 4 prior-identity conditions = 80/80 runs
- Conditions: global oracle, contextual oracle, global adversarial, and contextual adversarial
- Measurements: frozen Phase 0K guard-only rollout; static first-two-round probes; all phase-0 probes; first three main-stream blocks; per-domain prior correlations and selection harms
- Prohibition: no threshold calibration, run exclusion, or renewed held-out claim from seeds 101-120

The unique config, metrics, advancement gate, and fresh development split were written before any seed-121-140 execution.

## 3. Mechanistic finding: the prior called `oracle` was global, not contextual

The contextual synthetic stream defines each rule's `true_utility` as the mean of its domain-specific utilities. `initialise_utilities(..., condition="oracle")` returns that global mean vector. `ContextualUtilityState.from_prior` then copies the same vector into every domain state. The adversarial condition reverses the global ranking, not each domain ranking.

Consequently:

1. global oracle is perfect for global mean utility but only moderately correlated with each domain's utility;
2. copying it into every domain state double-counts a global identity as if it were contextual evidence;
3. global adversarial is not guaranteed to be adversarial on every small domain probe sample;
4. Phase 0K's ?helpful oracle? label was too strong for a contextual router.

Phase 0L adds an explicit diagnostic contextual identity: the global state receives global truth while each domain state receives that domain's truth. Its adversarial counterpart reverses each domain ranking separately. This is diagnostic evidence, not a promoted production prior format.

## 4. Labeled Phase 0K post-hoc diagnosis

Across seeds 101-120, global oracle had perfect global Spearman correlation (`1.000`) but only `0.499` mean per-domain Spearman correlation; the mean minimum-domain correlation was `0.415`. Its mean static margin versus the all-cold router was `-0.0350` on all phase-0 probes and `-0.0198` on the phase-0 main stream. The actual sequential guard margin and phase-0 stream margin had only `0.111` Pearson correlation, `0.187` Spearman correlation, and 10/20 sign agreement.

Replacing the copied global identity with explicit contextual oracle identity changed the mean static margin to `+0.1191` on probes and `+0.1120` on the phase-0 stream. Every development conclusion below was then tested again on fresh seeds 121-140.

| Failure | Actual guard margin | All phase-0 probe margin | Phase-0 stream margin | Contextual-identity stream margin | Diagnosis |
|---|---:|---:|---:|---:|---|
| Oracle seed 101 | -0.1915 | -0.1129 | -0.0448 | +0.0924 | Global prior identity was harmful on two domains; contextual identity reverses the conclusion. |
| Oracle seed 108 | -0.3446 | -0.1974 | -0.0039 | +0.1388 | Probe harm was real for the copied global identity, while the full stream was nearly neutral; this was not a clean helpful-prior false reset. |
| Oracle seed 113 | -0.0842 | -0.0991 | -0.0256 | +0.1117 | Law-domain mismatch dominated both probes and stream; more reset rounds could not repair identity. |
| Adversarial seed 109 | +0.2187 | -0.2260 | -0.3333 | n/a | The first two probe rounds were unrepresentative; all probes and the main stream correctly showed strong harm. |

For adversarial seed 109, the accepted prior reduced final main-stream mean reward by `0.1399` relative to all-cold. This is an early-accept representativeness failure: increasing only the destructive-reset horizon would not affect a `confident-acceptable` stop at round 2.

## 5. Fresh development results

Means are across seeds 121-140. Static margins compare the prior-driven greedy router with the same-policy all-cold router.

| Prior identity | Mean domain Spearman | Guard triggers | Mean guard margin | First-2 probe margin | All-probe margin | Phase-0 stream margin | Prefix sign agreement | All-probe sign agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Global oracle | +0.4810 | 2/20 | +0.0338 | +0.0262 | +0.0196 | -0.0041 | 10/20 | 14/20 |
| Contextual oracle | +1.0000 | 0/20 | +0.1324 | +0.1280 | +0.1274 | +0.1224 | 19/20 | 20/20 |
| Global adversarial | -0.4810 | 20/20 | -0.3298 | -0.3970 | -0.3662 | -0.3553 | 20/20 | 20/20 |
| Contextual adversarial | -1.0000 | 20/20 | -0.5478 | -0.5826 | -0.5745 | -0.5741 | 20/20 | 20/20 |

The global-oracle phase-0 stream margin was positive on only 10/20 seeds. The contextual-oracle margin was positive on 20/20 seeds and improved by `+0.12646` on average. Its selected-rule harmful fraction on the phase-0 stream was `0.0033`, versus `0.0506` for copied global oracle.

All-probe coverage was more informative across seeds than the first-two-round prefix. For global oracle, probe-to-stream Pearson/Spearman correlation improved from `0.0748/-0.0045` to `0.4258/0.3985`. For global adversarial, it improved from `0.1667/0.2617` to `0.5116/0.5233`. The fresh global-adversarial split happened to have no seed-109-like sign miss, but the spent held-out counterexample remains valid evidence that early acceptance has tail risk.

## 6. Predeclared diagnostic gate

| Gate | Requirement | Observed | Result |
|---|---:|---:|---|
| Artifact integrity | 80/80 valid immutable runs | 80/80; zero hash/fingerprint failures | Pass |
| Contextual identity improvement | At least +0.08 mean stream margin | +0.12646 | Pass |
| Contextual oracle positive stream seeds | At least 18/20 | 20/20 | Pass |
| Global-adversarial all-probe sign agreement | At least 19/20 | 20/20 | Pass |
| All probes not less representative than prefix | All-probe sign count at least prefix count | 20 versus 20; correlations also higher | Pass |
| Promotion limit | Diagnostic direction only | No guard promotion or execution-policy change | Pass |

**Phase 0L passes its development diagnostic gate.** This does not repair Phase 0K's failed held-out reliability gate and does not authorize paid API evaluation or formal scaling.

## 7. Artifact and verification

- Config SHA-256: `856cf0f6170a7f340f92e032c602ee08a44b2d611575aec6e5e6eed94ad30f66`
- Aggregate fingerprint: `30092cbc4b4dd4b8f148296f37b9091f068e9ccee4ae84b33a8de67daa0191a0`
- Complete grid: 80/80 runs
- Missing or duplicate runs: 0
- File/config/stream/run/aggregate fingerprint failures: 0
- Supplemental post-hoc record: `artifacts/acl2027_continual_phase0l_probe_representativeness_dev_v1/phase0k_spent_held_out_posthoc.json`
- Audit: `artifacts/acl2027_continual_phase0l_probe_representativeness_dev_v1/audit_report.json`
- Regression suite: 59 passed in 34.08 seconds

## 8. Interpretation and decision

1. **Prior identity is the primary semantic defect.** A global mean prior must not be labeled a contextual oracle or copied unchanged into every domain state.
2. **The three Phase 0K helpful resets are not evidence that a genuinely contextual helpful prior is rejected.** They are evidence that the existing global-only representation can be locally harmful and was mischaracterized.
3. **Probe coverage is a secondary but real safety defect.** Seed 109 proves that a two-round confident-acceptable decision can be strongly wrong even when all phase-0 probes and the stream agree on harm.
4. **Another threshold sweep is not justified.** The next candidate should change the prior contract and decision action, not calibrate Phase 0J thresholds on spent evidence.

Phase 0M should develop an identity-aware, non-destructive guard on a new development split. At minimum it should:

- distinguish global-only priors from explicit per-domain priors;
- initialize contextual domain states cold when only a global prior is available, rather than duplicating the global vector into every domain;
- use `abstain` or `escalate` instead of destructive reset/accept when early evidence is not representative;
- require broader probe confirmation before a global-only prior receives an early `confident-acceptable` decision;
- retain exact token accounting and later pass another disjoint held-out reliability phase.

Paid API evaluation and formal 128/512 scaling remain disabled. No user preparation is required for Phase 0M.
