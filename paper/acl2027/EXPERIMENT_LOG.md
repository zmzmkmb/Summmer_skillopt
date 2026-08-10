# ACL 2027 Experiment Log

**Last updated:** 2026-08-10 20:27 (Asia/Shanghai)
**Source of truth:** `experiment_state.json`, `CROSS_CONVERSATION_PROTOCOL.md`, immutable phase reports, and the experiment registry.
**Scope:** This log records the persistent ACL 2027 experiment program. It does not replace the immutable artifacts and does not authorize any new paid or scaling run.

## Current checkpoint

- **Completed phases:** 18 (`0H`-`1K` in the current persisted state).
- **Immutable runs:** 837, according to the handoff validator.
- **Current phase:** **1L - Paired-model live capability confirmation**, planned and not yet authorized.
- **Scientific status:** protocol and offline safety evidence are substantial, but the real-task route has not yet established the ACL main claim. Phase 1I produced negative task-valid calibration evidence; Phase 1J diagnosed it; Phase 1K prepared a fair four-call model comparison.
- **Execution guard:** paid API calls and formal scaling are disabled. The OfficeQA 24 / SpreadsheetBench 40 batch is closed.

## Chronological phase record

| Phase | Expected runs | Immutable report | Conclusion |
|---|---:|---|---|
| 0H | 90 | `paper/acl2027/results/phase0h_helpful_prior_informative_probe_dev_v1.md` | Same-policy cold reference removes all-cold comparator asymmetry, but frozen probes still falsely reset helpful priors. |
| 0I | 60 | `paper/acl2027/results/phase0i_rollout_guard_dev_v1.md` | Rollout min-12 reaches 0/5 helpful false resets and 5/5 adversarial detections, but costs 6.7k-9.6k guard tokens. |
| 0J | 90 | `paper/acl2027/results/phase0j_adaptive_rollout_dev_v1.md` | Adaptive harm-margin-0.10/slope-0.10 preserves the 0/5 helpful, 5/5 adversarial, 0/5 all-cold decision pattern while reducing mean guard cost to 3.4k-6.2k tokens. |
| 0K | 180 | `paper/acl2027/results/phase0k_adaptive_rollout_reliability_v1.md` | The frozen held-out gate failed: 3/20 helpful false resets, 19/20 adversarial detections, and 9,027.9 mean helpful guard tokens; paid API and formal scaling remain disabled. |
| 0L | 80 | `paper/acl2027/results/phase0l_probe_representativeness_diagnostic_v1.md` | Global oracle was a global-mean identity copied into contextual states; explicit contextual identity improved mean phase-0 stream margin by 0.1265 and all-probe coverage exposed the seed-109 early-accept representativeness failure. |
| 0M | 160 | `paper/acl2027/results/phase0m_identity_aware_guard_dev_v1.md` | Global-only identity correction removed copied-global oracle false resets (4/20 to 0/20) and improved mean reward by 0.0466. The selective candidate accepted 20/20 oracle and 0/20 adversarial priors with zero candidate-state mutation, but full confirmation added 9.5k mean oracle tokens. |
| 0N | 160 | `paper/acl2027/results/phase0n_identity_aware_guard_reliability_v1.md` | The frozen candidate passed every held-out gate: +0.0367 oracle reward versus copied-global reset, 10.66% token overhead versus global-only reset, 1/20 adversarial accepts, and 0/40 candidate-state mutations. Safety passed exactly at its allowed boundary, so probe-to-stream representativeness remains unresolved. |
| 1A | 1 | `paper/acl2027/results/phase1a_searchqa_pilot_preflight_v1.md` | The complete zero-paid-call SearchQA preflight passed deterministic manifest, strict parser, exact resume, retry/fallback provenance, hard-cap, permission, artifact-hash, and exact token/cost gates; mock accuracy is plumbing-only and paid execution remains separately gated. |
| 1B | 1 | `paper/acl2027/results/phase1b_searchqa_token_plan_live_pilot_v5.md` | The complete paced live pilot finished 2,448 SearchQA calls with 2,579 attempts, zero 429s, one conservatively accounted provider content rejection, and no reasoning content. skillopt_moar_frozen was strongest; the frozen selective candidate tied reset EM but was slightly lower on F1/sub-EM, so its offline advantage did not clearly transfer. |
| 1C | 1 | `paper/acl2027/results/phase1c_searchqa_proxy_reconciliation_v1.md` | The no-paid paired diagnostic found no selective-guard real-task advantage over identity-correct reset, localized part of the offline mismatch to comparator identity, and retained frozen MOAR as the strongest real-task method. |
| 1D | 1 | `paper/acl2027/results/phase1d_triage_pilot_v1.md` | A fabricated no-network development grid showed the three-way triage protocol reduced unsafe deployments from 48 to 0 while retaining all 144 candidates and preserving 16 helpful deployments. This is a development signal only; real cross-task validation is still required. |
| 1E | 1 | `paper/acl2027/results/phase1e_real_cross_task_triage_protocol_v1.md` | The real cross-task accept/reject/abstain protocol was frozen and audited with no network calls. SearchQA is confirmatory-only; OfficeQA and SpreadsheetBench are new development task families. Complete payload materialization and provider review remain prerequisites for execution. |
| 1F | 2 | `paper/acl2027/results/phase1f_real_cross_task_triage_pilot_v1.md` | The two-call real smoke verified Token Plan transport and exact usage (2,072 total tokens, zero retries/rate limits) but failed the task-valid smoke gate: OfficeQA confused fiscal-year 1,580 with calendar-year 2,602, and SpreadsheetBench returned a malformed schema key plus a formula inconsistent with the golden workbook. Paid permission and the 24/40 batch remain closed. |
| 1G | 1 | `paper/acl2027/results/phase1g_cross_task_protocol_repair_v1.md` | The offline protocol repair passed: OfficeQA retrieval evidence is separated from temporal aggregation, the Phase 1F fiscal/calendar shortcut is blocked, parser normalization preserves provenance, and SpreadsheetBench requires exact executable per-cell edits. The development set is 8 stratified OfficeQA examples; paid smoke and 24/40 scaling remain closed. |
| 1H | 1 | `paper/acl2027/results/phase1h_repaired_cross_task_smoke_preflight_v1.md` | The zero-network preflight froze exactly two repaired, leakage-audited requests and passed all 14 checks plus 20 cross-phase tests. It strengthens measurement validity but adds no real model-effect evidence; the overall ACL claim remains partially supported, not established, and paid execution plus the 24/40 batch remain closed. |
| 1I | 2 | `paper/acl2027/results/phase1i_repaired_cross_task_live_smoke_v1.md` | Exactly two repaired Token Plan smoke calls completed with zero retries and 4,963 exact tokens, but both task-valid gates failed. OfficeQA retrieved the 12 correct values yet reported 2,561 instead of 2,602 and exposed an underspecified operand schema; SpreadsheetBench was truncated at 1,800 output tokens and all 12 recoverable formulas used incorrect global-range logic. This is negative base-task calibration evidence, not a test of the prior or triage claims. Paid permission and the 24/40 batch remain closed. |
| 1J | 2 | `paper/acl2027/results/phase1j_no_paid_capability_calibration_v1.md` | Zero-network replay separated seven failure channels without changing either negative task-valid label. OfficeQA evidence recomputed to 2602 while schema, arithmetic, and answer failed; SpreadsheetBench retained truncation and 12/12 formula mismatches. Protocol validity improved, but qwen3.6-flash remains unqualified and the ACL main claim remains partially supported. |
| 1K | 4 | `paper/acl2027/results/phase1k_paired_model_capability_preflight_v1.md` | Four fair qwen3.6-flash/qwen3.8-max capability requests passed all zero-network schema, fairness, and leakage audits. This establishes protocol readiness only; exact four-call paid confirmation remains unauthorized and the main ACL claim is unchanged. |

## Phase 0 - Offline continual-routing and safety development

Phases 0H-0N progressively repaired the offline continual-routing protocol:

1. Same-policy cold references removed comparator asymmetry, but frozen probes still caused false helpful-prior resets (0H).
2. A rollout-aware guard reached 0/5 helpful false resets and 5/5 adversarial detections, at a high token cost (0I).
3. Adaptive harm-margin and slope thresholds preserved the decision pattern while lowering guard cost (0J).
4. Reliability testing failed the frozen held-out gate, so paid API and formal scaling remained disabled (0K).
5. Probe-representativeness diagnostics showed that copied global identity caused misleading conclusions and that contextual identity materially improved the stream margin (0L).
6. Identity-aware correction removed copied-global false resets in development and preserved candidate-state immutability, but confirmation was expensive (0M).
7. The frozen reliability candidate passed the held-out oracle and immutability gates, while safety passed exactly at its allowed boundary; representativeness remained unresolved (0N).

**Interpretation:** Phase 0 supports a carefully scoped safety/protocol story, not a universal selector-accuracy claim.

## Phase 1 - Real-task route and capability gating

- **1A-1C (SearchQA):** deterministic preflight passed; the paced live pilot completed 2,448 calls with no 429s; frozen MOAR was strongest, while the selective candidate did not show a clear real-task advantage. The proxy reconciliation localized part of the offline/online mismatch to comparator identity.
- **1D-1E (triage):** a fabricated development grid showed that accept/reject/abstain triage can eliminate unsafe deployments, but 1D is development-only. Phase 1E froze the real cross-task protocol and explicitly kept SearchQA confirmatory-only while OfficeQA and SpreadsheetBench became new development families.
- **1F:** exactly two live smoke calls verified transport and usage accounting but failed the task-valid gate. OfficeQA confused fiscal-year 1,580 with calendar-year 2,602; SpreadsheetBench returned malformed structure and an incorrect formula.
- **1G-1H:** the protocol was repaired without paid calls. Temporal aggregation, provenance-preserving parsing, exact executable per-cell spreadsheet edits, leakage checks, and request freezing were added and audited.
- **1I:** exactly two authorized repaired calls consumed 4,963 exact tokens with no retries. OfficeQA retrieved the 12 correct values but reported 2,561 instead of 2,602; SpreadsheetBench was truncated and all 12 recoverable formulas disagreed with the golden workbook. The paid permission was closed immediately and no batch was launched.
- **1J:** zero-network replay separated seven failure channels and preserved both negative task-valid labels. This improved attribution but did not qualify `qwen3.6-flash` or strengthen the method-effect claim.
- **1K:** four unique zero-network requests were frozen fairly for `qwen3.6-flash` and `qwen3.8-max`, with identical task content across models, explicit schemas, no answer/golden leakage, and stricter output contracts. This is protocol readiness only.

## Current phase: 1L

The next action is **not** to launch a batch. It is to obtain explicit authorization for exactly four paid Token Plan calls, then execute the four frozen Phase 1K requests once each, in order, with exact usage auditing and no retries. The predeclared decision rule is:

- retain `qwen3.6-flash` if it passes both task-valid gates;
- use `qwen3.8-max` if only it passes;
- change the real-task route or narrow the claim scope if neither passes.

The expected write scope is limited to the Phase 1L config, runner, tests, artifact directory, report, evidence ledger, and experiment state. Do not modify completed immutable Phase 1I-1K artifacts.

## Reproducibility and guardrails

- Always validate the handoff state before continuing: `python scripts/acl2027_experiment_handoff.py validate`.
- Use the repository state as authoritative across conversations; do not rely on chat summaries.
- Run Python tests without bytecode or pytest cache artifacts:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider ...
```

- Keep paid permission closed unless a separate, explicit authorization names the exact call count.
- Do not rerun completed immutable artifacts, add retries, launch the 24/40 batch, or enable formal scaling.

## Log maintenance

When a material phase action completes, append a dated checkpoint to `experiment_state.json`, update this log and the phase report if applicable, then run the handoff validator. The state file and immutable artifacts remain the authoritative record.
