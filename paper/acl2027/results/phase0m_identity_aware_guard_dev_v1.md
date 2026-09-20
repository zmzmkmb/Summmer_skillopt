# Phase 0M: identity-aware non-destructive guard development v1

## Status and scope

**Status:** completed development-only synthetic instrumentation.  
**Config:** `configs/acl2027/offline_continual_phase0m_identity_aware_guard_dev_v1.json`  
**Artifact:** `artifacts/acl2027_continual_phase0m_identity_aware_guard_dev_v1/`  
**Seeds:** 141-160, disjoint from Phase 0J development 81-85, spent Phase 0K held-out 101-120, and Phase 0L development 121-140.  
**Runs:** 160 = 20 seeds x 2 prior conditions x 4 frozen methods.  
**Claim boundary:** synthetic routing evidence only; this is not downstream LLM accuracy, a held-out reliability result, paid evaluation, or formal 128/512-rule scaling.

## Frozen comparison

The phase compared:

1. `copied_global_reset_phase0k`: the legacy semantic error, which copied a global prior into every contextual state and retained the destructive Phase 0K reset guard;
2. `global_only_reset_phase0k`: the identity-correct initialization, where the global prior initializes only the global state and contextual states start cold;
3. `contextual_reset_phase0k`: explicit per-domain priors, used as a contextual-information comparator;
4. `global_only_selective_full_confirmation`: global-only initialization plus a selective non-destructive deployment guard. Early acceptable evidence escalates to all eight probe rounds per domain; harmful evidence rejects to a fresh cold fallback; ambiguous evidence abstains to the same fallback; the candidate state is never reset.

The utility conditions were `oracle` and `adversarial`. The predeclared gates covered immutable artifact integrity, typed prior initialization, non-destructive action semantics, adversarial false-safe acceptance, oracle usefulness, and exact token accounting.

## Main development results

### Oracle priors

| Method | Mean reward | Mean total tokens | Mean guard tokens | Actions |
|---|---:|---:|---:|---|
| copied-global + reset | 0.740407 | 81,514.1 | 5,342.5 | 16 retain, 4 false resets |
| global-only + reset | 0.787023 | 80,464.0 | 4,042.1 | 20 retain, 0 false resets |
| contextual + reset | 0.822373 | 80,614.2 | 3,984.4 | 20 retain, 0 false resets |
| global-only + selective | 0.787023 | 89,977.3 | 13,555.4 | 20 accepts after full confirmation |

Correcting prior identity improved oracle mean reward by **+0.046616** over copied-global initialization. The paired 95% t interval was `[+0.036145, +0.057086]`, and all 20 seed-level differences were positive. Explicit contextual priors added another **+0.035350** over global-only initialization.

The selective candidate preserved the same reward as global-only reset on every oracle seed, but full confirmation added **9,513.35 mean tokens** per run. This was an 11.82% increase in total tokens and a 235.36% increase in guard-validation tokens relative to global-only reset.

### Adversarial priors

All four methods reached the same mean downstream synthetic stream reward, `0.724799`, after safe fallback behavior. The three destructive comparators reset on 20/20 seeds. The selective candidate made:

- 0/20 adversarial accepts;
- 16/20 `reject-fallback-cold` decisions;
- 4/20 `abstain-fallback-cold` decisions;
- 0/40 candidate-state mutations across oracle and adversarial runs.

The four abstentions are semantically important: the evidence was not sufficient for the stricter harmful classification, so the guard avoided relabeling uncertainty as a confirmed harmful reset while still declining deployment.

## Gate decision

- **Artifact integrity:** pass. All 160 immutable runs, file/config/stream/run/aggregate fingerprints, and exact run- and round-level token identities validated.
- **Prior identity contract:** pass. Every global-only contextual state started at 0.5, copied-global states matched the global vector, and contextual states used explicit per-domain vectors.
- **Non-destructive semantics:** pass. All selective decisions preserved the candidate state; decision/action mappings had zero audit failures.
- **Candidate safety:** pass. Adversarial acceptance was 0/20, below the predeclared maximum of 1/20.
- **Candidate usefulness:** pass. Oracle reward exceeded copied-global reset by 0.046616 and exactly matched global-only reset.
- **Promotion limit:** respected. No paid API or formal scaling permission changed.

Aggregate fingerprint: `0f19ae8eb18a2f07297a909cae672a857f45e92f20dfc54382bde15711b5159b`.  
Audit: `artifacts/acl2027_continual_phase0m_identity_aware_guard_dev_v1/audit_report.json`.

## Interpretation

The largest measured gain came from the **prior-identity correction**, not from adding a more complicated threshold. Global-only initialization removed all four copied-global helpful false resets and improved reward while slightly reducing mean total cost.

The selective guard achieved the intended semantic safety behavior: acceptance required broader confirmation, ambiguity produced abstention, and no candidate state was destructively reset. Its weakness is cost. Full confirmation bought no additional oracle reward over identity-correct reset and added about 9.5k tokens. Therefore Phase 0M supports the method contract but does not establish token superiority.

## Decision and next phase

Freeze `global_only_selective_full_confirmation` as the single conservative Phase 0M candidate for a disjoint held-out reliability test. Phase 0N must test the unchanged candidate on new seeds, including its predeclared safety, usefulness, non-destructive, and total-token gates. The cheaper `global_only_reset_phase0k` remains the key ablation, and `contextual_reset_phase0k` remains an information-rich comparator rather than a deployable global-only method.

Paid API evaluation and formal 128/512 scaling remain disabled.
