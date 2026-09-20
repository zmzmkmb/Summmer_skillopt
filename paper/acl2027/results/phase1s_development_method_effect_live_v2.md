# Phase 1S v2 Development Method-Effect Live Result

Date: 2026-08-11

## Outcome

The authorized `qwen3.7-plus` Token Plan run completed all 192 frozen
development calls with zero retries and no client-side `max_tokens` field.
Exact usage was available for every attempt. Thirty-one responses failed the
frozen output contract and remain counted as negative condition outcomes.

| Measure | Result |
| --- | ---: |
| Planned / attempted calls | 192 / 192 |
| Candidate / fallback calls | 96 / 96 |
| Contract-valid calls | 161 |
| Execute / abstain / invalid | 123 / 38 / 31 |
| Exact task correct | 6 / 192 (3.125%) |
| Input / output / total tokens | 526,776 / 155,334 / 682,110 |
| Retries | 0 |
| Client `max_tokens` | omitted |
| Local list-price accounting | CNY 2.296224 |

## Development Results

| Comparison | Exact correct | Contract valid | Execute / abstain / invalid |
| --- | ---: | ---: | ---: |
| Candidate | 2/96 | 79/96 | 61 / 18 / 17 |
| Fresh fallback | 4/96 | 82/96 | 62 / 20 / 14 |
| Contextual prior | 0/64 | 54/64 | 43 / 11 / 10 |
| Copied-global prior | 4/64 | 52/64 | 38 / 14 / 12 |
| Global-only prior | 2/64 | 55/64 | 42 / 13 / 9 |
| Representative probes | 0/96 | 80/96 | 55 / 25 / 16 |
| Shifted probes | 6/96 | 81/96 | 68 / 13 / 15 |
| Candidate-retaining label | 3/96 | 82/96 | 65 / 17 / 14 |
| Destructive-gate label | 3/96 | 79/96 | 58 / 21 / 17 |

Across the 96 paired candidate-versus-fallback comparisons, the candidate won
zero, the fallback won two, and 94 tied. Both fallback wins occurred on the
shifted OfficeQA panel under `global-only`; each gate label contained one of
the duplicated comparisons. The mean candidate-minus-fallback exact margin was
`-0.02083`.

All six exact successes came from OfficeQA task `UID0086`. SpreadsheetBench
obtained `0/96` exact tasks despite 94 contract-valid responses. Of 32
OfficeQA executions with a supported calculation audit, only three were
arithmetically self-consistent.

## Identifiability Audit

This run identifies only development-panel branch and condition differences.
It does not identify the two deployment claims that motivated the design:

- No held-out downstream task was executed. The observed task sets have zero
  intersection with the frozen held-out OfficeQA and SpreadsheetBench sets.
- The 192 calls contain only 52 unique request bodies.
- All 96 gate-label pairs use identical request hashes.
- The gate labels are metadata only: no distinct numerical thresholds or
  accept/reject/abstain decision rules were implemented.

Consequently, aggregate differences between the two gate labels are stochastic
response variation, not evidence that either deployment policy is better.

## Paper Implication

The result narrows the ACL claim.

1. **Typed priors:** not confirmed on these real development tasks. The
   directional result contradicts the hypothesis (`contextual` 0/64 versus
   `copied-global` 4/64), but the extremely low and task-concentrated accuracy
   prevents a reliable prior-effect conclusion.
2. **Sparse-probe representativeness:** weakened and still untested as a
   deployment claim. Shifted probes outperformed representative probes on the
   development panel, while no downstream stream was run.
3. **Candidate-retaining triage:** not tested. Identical requests and absent
   thresholds make the two gate labels scientifically non-identifiable, and no
   candidate-retention-over-time outcome exists.

The defensible paper position remains that inherited skills require typed
identity, representativeness checks, and non-destructive uncertainty handling,
with strong synthetic evidence for identity-aware handling and real-model
evidence motivating validation. Phase 1S does not yet show that the complete
protocol improves real downstream deployment.

Before any further paid scaling, Phase 1T must freeze a zero-network redesign
with disjoint development and downstream streams, numerical gate thresholds,
actual policy-specific deployment decisions, and longitudinal candidate
retention. The design must also raise the executor-valid scoring floor so that
effects are not determined by a single OfficeQA task.

## Integrity

- Analysis aggregate fingerprint:
  `729ad8548ca2c4e3d718f860d843cce8cc7ac7e99b0781068abc8c42c7b7aa12`
- Results SHA-256:
  `2e6113b703652a6b3d4cf3c5787f037b791c55ace7298a39aa6f09d29502618e`
- Scored records SHA-256:
  `c948c29ccab6696607df3ee9fcfc7c0b0db26bc5a4ad20316865596853b0050e`
- Analysis aggregates SHA-256:
  `332accc81e94a502f13e4212fb726eab3080b7181a9ab87e99cb43d6f941b17f`
- Design audit SHA-256:
  `ed6da769359cb7aacdd9d060e1cdb863f70e191eaa5a24bf5a5e6a8b35b9f431`

Paid permission is closed. The completed live artifact is immutable and must
not be rerun.
