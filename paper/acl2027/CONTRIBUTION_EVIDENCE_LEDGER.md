# ACL 2027 contribution evidence ledger

This ledger distinguishes protocol readiness from evidence for the paper's scientific claims. A passing transport, parser, or payload preflight is not counted as proof of the main contribution.

## Current thesis

When a continual-learning system inherits historical skill priors, safe deployment requires identifying the prior's scope, testing whether sparse validation evidence is representative, and retaining rather than destroying candidates when evidence is negative or insufficient.

## Claim status after Phase 2

| Claim | Current status | Supporting evidence | Missing evidence |
|---|---|---|---|
| Typed/scoped priors matter (`copied-global`, `global-only`, `contextual`) | Supported synthetically; reliable real-task improvement not established | Phase 0N synthetic support; Phase 2 v31 real-task margin was positive but the frozen gate was inconclusive | Independent real-task evidence that clears effect, family-consistency, and mechanism thresholds |
| Sparse validation predicts downstream safety | Not established; principal scientific risk | Phase 0L-0N diagnostics and selective behavior | Seed 176 was accepted but harmed the downstream stream; SearchQA proxy-to-real ranking mismatch remains unresolved |
| `accept` / `reject` / `abstain` with candidate retention is safer than destructive gating | Semantics and synthetic behavior supported; real-task effectiveness not established | Phase 0N non-mutation and retained candidates; Phase 1E/1G protocol contracts | Real cross-task harmful/helpful deployment rates and abstention behavior |
| Overall ACL main claim | Partially supported, not established | Strong synthetic identity evidence, audited protocol, and complete but inconclusive Phase 2 real-task evidence | Replicated real-task causal evidence and probe-to-stream representativeness evidence |

## Evidence that would strengthen the main claim

1. Repaired real-task smoke responses are task-valid, so prior/gate effects can be measured without retrieval or formatting confounds.
2. On at least one new task family, triage lowers harmful deployment while preserving a non-trivial helpful-deployment rate.
3. Sparse-probe decisions predict downstream outcomes under frozen thresholds and held-out task order.
4. The result survives comparison among copied-global, global-only, contextual, binary-gate, triage-gate, and frozen SkillOpt/MOAR conditions.

## Change triggers

The paper direction must be reconsidered if any of the following occurs:

- repaired task protocols remain unreliable enough that prior and gate effects cannot be identified;
- prior identity has no measurable effect outside the synthetic harness;
- sparse validation repeatedly accepts harmful candidates or abstains/rejects nearly all helpful candidates;
- the three-way protocol provides no advantage over a simpler identity-correct reset baseline.

Until those tests are complete, the defensible framing is a scoped contribution about typed priors, representativeness-aware validation, and non-destructive abstention, not a general zero-failure safety guarantee.
## Phase 1H update

The repaired two-family request preflight passed all 14 checks with 0 network and 0 paid calls. The two request hashes are frozen, reference-answer/golden-formula leakage checks passed, and the Phase 1F temporal and schema confounds are explicitly blocked.

This is protocol evidence, not method-effect evidence. Claim statuses are unchanged: typed/scoped priors have held-out synthetic support only; sparse-probe representativeness is not established; non-destructive triage lacks real cross-task effectiveness evidence; and the overall ACL claim remains partially supported, not established. No direction change is triggered. The next informative result must come from a separately authorized repaired two-call live smoke, followed by held-out paired comparisons only if that smoke is task-valid.
## Phase 1I update

The authorized repaired smoke consumed exactly two calls and failed both task-valid gates with exact usage available (`4,963` total tokens, zero retries). OfficeQA retrieved all 12 correct monthly values but summed them to `2561` instead of `2602`; SpreadsheetBench exhausted its output budget, produced truncated JSON, and its recoverable 12 formulas all used the wrong global-range logic.

This does not test or falsify typed priors, sparse-probe representativeness, or non-destructive triage because no prior condition or deployment decision was exercised. It does weaken the current real-task evidence route: `qwen3.6-flash` plus the present contracts is not a task-valid substrate for method comparison. Phase 1H's protocol-readiness conclusion must be qualified because Phase 1I exposed an underspecified OfficeQA operand item schema and insufficient SpreadsheetBench completion control.

No paper-mainline change is triggered yet. The experiment plan must add a no-paid capability-calibration phase and establish a task-valid floor, potentially with a stronger model, before any batch or prior/gate comparison. If that floor cannot be reached without benchmark-specific overfitting, the real-task suite or the scope of the ACL claim must change.

## Phase 1J update

The zero-network replay passed its diagnostic gate with `0` network calls and `0` paid calls. OfficeQA retrieval/provenance was isolated as successful, while operand schema, arithmetic, and answer consistency failed independently. SpreadsheetBench yielded 12 complete edits for diagnosis, but the raw JSON remained truncated and all 12 formulas remained semantically wrong. Diagnostic recovery did not change either Phase 1I task-valid label.

This strengthens protocol validity, error attribution, and preservation of negative evidence, but it is not evidence that typed priors, sparse probes, or non-destructive triage improve real-task outcomes. The overall ACL claim remains partially supported and the paper mainline does not change. The real-task route stays blocked until a repaired model-contract pair meets a frozen task-valid floor. A zero-network Phase 1K paired-model preflight should compare `qwen3.6-flash` with a stronger candidate before any separately authorized confirmation; the 24/40 batch remains closed.
## Phase 1K update

The zero-network paired-model preflight froze four fair requests for `qwen3.6-flash` and `qwen3.8-max` on the same OfficeQA and SpreadsheetBench development tasks. All fairness, stricter-contract, and leakage audits passed with zero network and zero paid calls. This is protocol readiness only; all central claim statuses remain unchanged. The live four-call successor and the 24/40 batch remain closed pending separate authorization.
## Phase 1L update

The cost-aware Flash confirmation executed exactly two authorized `qwen3.6-flash` calls with zero retries and exact usage of `4,440` tokens. Both frozen task-valid gates failed. OfficeQA reached the 1,200-token output limit, produced truncated JSON, reported `1580` rather than `2602`, and mixed annual with monthly evidence. SpreadsheetBench returned complete 12-cell JSON and valid formulas, but all `12/12` formulas omitted the row-specific maximum check and disagreed with the golden semantics.

This is model-contract capability evidence, not evidence about typed priors, sparse-probe representativeness, or non-destructive triage. The overall ACL claim remains partially supported, not established. The paper mainline does not change yet, but the real-task route remains blocked and `qwen3.6-flash` should not be used for the formal comparison. The next cost-aware step is a separately frozen and authorized two-call `qwen3.7-plus` confirmation on identical task content. If Plus also fails, the OfficeQA/SpreadsheetBench route or the real-task claim scope must change rather than escalating automatically to `qwen3.8-max`.
## Phase 1M update

The zero-network `qwen3.7-plus` preflight passed with two frozen requests, zero provider calls, and complete immutable hashes. In response to the Phase 1L attribution problem, both successor requests completely omit the client-side `max_tokens` parameter while preserving the task messages. The historical Phase 1L `1200/1400` limits and negative results remain immutable.

This removes a client-induced truncation confound from the next capability check but does not add evidence for typed priors, probe representativeness, or three-way triage. The overall ACL claim remains partially supported. Exactly two Plus calls require separate authorization; Max and the 24/40 batch remain closed.
## Phase 1N update

The uncapped `qwen3.7-plus` confirmation executed exactly two authorized calls with zero retries and `4,839` exact tokens. Both responses were complete, so client-side truncation is no longer a viable explanation. OfficeQA returned the correct 12 grounded operands, which sum to `2602`, but reported `2498`; SpreadsheetBench returned complete valid syntax but all `12/12` formulas used the wrong comparison direction.

This is capability and validator-motivation evidence, not a test of typed priors, sparse-probe representativeness, or non-destructive triage. It strengthens the motivation for validation and abstention but leaves the ACL main claim partially supported. The real-task route must now be adjudicated or narrowed through zero-network design work; `qwen3.8-max` escalation and 24/40 scaling remain closed.

## Phase 1O update

The zero-network construct-first route adjudication passed with `0` provider calls. Without reference access, the OfficeQA executor recomputed the 12 frozen grounded operands as `2602`; independent scoring then matched the reference exactly. Without golden-workbook access, the SpreadsheetBench constrained constructor generated 12 formulas; independent scoring obtained `12/12` exact matches.

OfficeQA is retained only with deterministic recomputation and abstention on provenance, temporal, coverage, or evidence-operand mismatch. SpreadsheetBench is retained only as a constrained executor-backed task, not as evidence for unconstrained formula-generation ability. This clears the task-substrate blockage and strengthens validation/abstention motivation, but it still does not test typed priors, sparse-probe representativeness, or non-destructive triage efficacy. The main ACL claim remains partially supported. The next phase must return to a pre-registered, contribution-aligned real-task protocol rather than spend more calls on model-capability escalation.

## Phase 1P update

The contribution-aligned zero-network preflight froze two executor-backed task
families, three prior identities, representative versus deliberately shifted
four-task probe panels, and candidate-retaining triage versus destructive
gating. Each family now has 8 development and 16 disjoint downstream tasks.
The full `3 x 2 x 2 x 2` design contains 24 condition cells, with identical
model/prompt/order/call-allocation controls and both counterfactual branches
charged. All 22 audit checks passed with `0` network and `0` paid calls.

This resolves protocol ambiguity, not the evidence gap. Typed-prior effects
remain real-task unconfirmed, sparse-probe representativeness remains the
principal scientific risk, and triage has no real-task effectiveness result
yet. The ACL main claim therefore remains partially supported and the paper
direction does not change. Before any paid execution, Phase 1Q must freeze
candidate provenance, executor eligibility, exact call counts, and a
worst-case cost matrix for these 24 cells. A later paired result must trigger
scope narrowing if prior identity has no effect, representative probes do not
outperform shifted probes, or retention-aware triage has no advantage over
the simpler controls.

## Phase 1Q update

The zero-network execution and budget preflight passed all 19 checks. All 48
frozen OfficeQA and SpreadsheetBench identities are locally executor-eligible,
all six prior-by-gate candidates are bound to fresh cold counterfactual
fallbacks, unsupported tasks must abstain, and candidate/fallback calls are
charged equally. The exact request counts are 192 for development only, 384
for staged confirmation, and 960 for the full frozen design.

The corresponding CNY 39.744, 79.488, and 198.720 figures are conservative
planning assumptions, not provider quotations, output caps, or authorization.
No network, provider, or paid calls were made.

This adds protocol and budget evidence only. It does not change the status of
typed-prior effects, sparse-probe representativeness, or candidate-retaining
triage, so the ACL main claim remains partially supported and the paper
direction does not change. Phase 1R must freeze and audit the development-only
runner before any separately authorized paid execution.

## Phase 1R update

The immutable development-runner preflight passed every audit check. It
materialized exactly 192 logical and physical requests across the 24 frozen
condition cells, with 96 candidate and 96 fresh cold-fallback calls,
`max_tokens` omitted, zero retries, deterministic append-only resume, exact
usage accounting, explicit abstention, and hard stops for unknown usage,
contract failure, or plan drift. The preflight made 0 network, provider, and
paid calls.

This is runner-readiness evidence only. Typed-prior effects remain real-task
unconfirmed, sparse-probe representativeness remains the principal scientific
risk, and candidate-retaining triage still lacks a real-task effectiveness
result. The ACL main claim remains partially supported and the paper direction
does not change.

The materialized prompts total approximately 1.35 million characters, so
Phase 1Q's CNY 39.744 development estimate remains a planning assumption.
Current provider rates and actual tokenizer usage must be reviewed before any
paid authorization. The next phase should move directly toward the first
192-call development method-effect experiment rather than add another broad
protocol-only micro-phase.

## Phase 1S v1/v2 update

Phase 1S v1 reached the user-confirmed Token Plan endpoint and returned exact
usage on its first `qwen3.7-plus` call, but the OfficeQA `calculation` field had
the wrong type. The v1 runner hard-stopped after 1/192 attempts and 2,931 exact
tokens. This proves route connectivity but provides no method-effect evidence.
The terminal artifact remains immutable and non-resumable.

The separately versioned Phase 1S v2 zero-network preflight passed 12/12
checks. It preserves raw provider text, applies only predeclared syntactic
normalization, counts known-usage malformed or schema-invalid responses as
per-condition invalid outcomes, and continues to the next logical call.
Unknown usage, provider exceptions, plan drift, authorization drift, and the
accounting ceiling remain terminal.

This repair prevents one formatting failure from erasing the complete
factorial comparison while preserving negative evidence. It does not establish
typed-prior, representativeness, or triage effects. The ACL main claim remains
partially supported and the paper direction does not change. A separately
immutable live authorization config and new explicit authorization are still
required before another provider attempt.

## Phase 1S v2 live-result update

The authorized live run completed all 192 development calls with zero retries,
`max_tokens` omitted, and exact accounting of 682,110 tokens. It produced 161
contract-valid responses, 31 invalid outputs, 123 executions, 38 abstentions,
and only 6 exact task successes. Candidate branches scored 2/96 versus 4/96
for fresh fallbacks. Contextual, copied-global, and global-only conditions
scored 0/64, 4/64, and 2/64; representative and shifted panels scored 0/96 and
6/96. All six successes came from one OfficeQA task, while SpreadsheetBench
scored 0/96.

This weakens rather than strengthens the current real-task evidence. Typed
priors are not confirmed: the observed direction favors the deliberately
wrong copied-global condition, but accuracy is too sparse and concentrated to
support a stable prior-effect estimate. Sparse-probe representativeness remains
the principal risk and now requires redesign because the representative panel
underperformed the shifted panel and no held-out stream was executed.

The triage claim was not tested. All 96 gate-label pairs reused identical
request bodies, no numerical gate thresholds or policy-specific decisions were
implemented, and no longitudinal candidate-retention outcome exists. The two
gate labels are metadata only in this artifact.

The ACL mainline therefore narrows to a motivation and protocol contribution
supported by synthetic identity-aware results, not a demonstrated real-task
deployment improvement. No direction should be claimed from Phase 1S gate
comparisons. Phase 1T must be a zero-network redesign with disjoint held-out
streams, frozen numerical thresholds, actual accept/reject/abstain deployment
semantics, and candidate retention across time before any further paid scaling.

## Phase 1T cross-conversation design checkpoint

Phase 1S also exposes a prerequisite that was previously implicit: a system
cannot meaningfully inherit skills when the base model produces too few
verified successes to form reusable historical experience. Historical
experience is now operationalized as:

`successful verified trajectories -> skill candidates -> typed prior -> sparse probes -> held-out downstream stream -> later candidate recovery`

OfficeQA and SpreadsheetBench are demoted from the primary causal experiment.
Their Phase 1S floor was too severe and concentrated: only `6/192` exact
successes, all from OfficeQA `UID0086`, and `0/96` SpreadsheetBench successes.
The user also reports a separate LiveMathematicianBench trial with zero correct
answers; this is user-provided capability evidence rather than a repository
artifact, but it is sufficient to stop spending on that route pending a new
frozen calibration.

SearchQA remains the proven non-floor anchor from Phase 1B. The preferred new
substrate candidate is 2WikiMultiHopQA, with BFCL
simple/multiple/non-live as backup. CLUTRR may provide controlled transfer
support, and ALFWorld is deferred to a later procedural stress test.

Before any paid dataset experiment, Phase 1T must freeze a small no-skill
capability gate of approximately 12 tasks per candidate. Eligibility requires
at least 90% contract-valid responses, baseline accuracy in the approximate
25%-75% range, successes distributed across at least three task types, an
automatic verifier, identifiable reusable skill families, and no concentration
of all successes on one task ID. These criteria are design targets to be
pre-registered and zero-network audited; no paid calibration is currently
authorized.

This changes the experimental route but does not abandon the paper's three
central contributions. It adds a necessary antecedent claim: inherited
experience must first be verifiable and reusable. The next conversation should
continue Phase 1T by freezing the dataset-eligibility and history/probe/stream
design, not by launching provider calls.

## Phase 1T immutable design result

The capability-gated held-out deployment redesign passed all `21/21`
zero-network audit checks with aggregate fingerprint
`dd5a45d13889c53c8f313946d924987113d2306404f99e93256efa2a5b5c8e81`.
The frozen substrate gate requires at least 90% contract validity, inclusive
25%-75% baseline accuracy, at least three successes across three task types,
automatic verification, reusable skill families, and no task ID contributing
more than half of all successes.

SearchQA now has disjoint 12-task calibration, 120-task history, 24-task
development-probe, and 120-task held-out downstream streams. All 360 test IDs
spent in Phase 1B are excluded from downstream selection. Historical SearchQA
performance does not bypass the fresh eligibility gate. 2WikiMultiHopQA is
fully specified as the preferred successor but remains unmaterialized and was
not downloaded.

The redesign makes the Phase 1S gate comparison operational: accept requires
a paired mean margin of at least `0.125`, at least three helpful pairs, and no
harmful pair; reject requires a mean margin at most `-0.125` or at least two
harmful pairs; all remaining valid outcomes abstain. Retaining reject/abstain
preserves the candidate and permits recovery after two qualifying later
windows, while destructive reject/abstain discards it irreversibly. The audit
confirmed both state paths and exact candidate-plus-fallback token accounting.

This is protocol and identifiability evidence only. It does not establish
typed-prior benefit, probe representativeness, or retention-aware deployment
benefit on real tasks. The ACL main claim remains partially supported. Phase
1U should bind the local SearchQA calibration payload and freeze the 2Wiki
acquisition/materialization validator with provider execution still closed.

## Phase 1U update

The immutable payload-readiness audit passed all `10/10` checks with aggregate
fingerprint
`6604ef63517129291aead96afaebb5e21fc6ac30931f0b4ad3350bcb90eeb41a`.
All 12 admitted SearchQA calibration identities have complete local payloads.
The mirrored 2WikiMultiHopQA development pool contains 12,576 unique,
schema-valid gold records with zero duplicate IDs, missing fields, invalid
support references, evidence-ID mismatches, blank answer IDs, or invalid task
types. The frozen 12/120/24/120 partitions are exact and pairwise disjoint, and
joint answer-plus-support verification is fixed before model execution.

The author repository and its April 7, 2021 ID-bearing release remain the
normative source; Kaggle was used only as a byte transport mirror after the
author-hosted Dropbox endpoint timed out. No provider or paid calls occurred.

This resolves payload, provenance, partition, and automatic-verification
readiness only. It does not show that 2WikiMultiHopQA clears the non-floor
capability gate, and it adds no typed-prior, representativeness, or
retention-aware deployment effect. The ACL main claim remains partially
supported. Phase 1V should freeze a zero-call calibration runner and verifier
preflight before any separate provider authorization is considered.

## Phase 1V update

The immutable calibration request and verifier preflight passed all `14/14`
checks with aggregate fingerprint
`845af0618483eecfd9e3063162be0fc2133743ba69fdbeaebd9a34e44c5e041f`.
It freezes exactly 24 ordered requests, comprising 12 admitted SearchQA tasks
followed by 12 2WikiMultiHopQA tasks, with deterministic identities, private
gold separation, no held-out inputs, strict task-specific parsers and
verifiers, append-only exact-prefix resume, exact usage accounting, zero
retries, and terminal hard stops for unknown usage or plan drift. Network,
provider, and paid calls were all zero.

The strengthened selected-record audit found that 5/12 2Wiki calibration
records have textual evidence chains but empty `evidences_id` lists, while
1/12 has `answer_id=null` for answer `1969`. These limitations are preserved
as explicit availability flags. They do not prevent answer-plus-supporting-
fact verification because all selected records retain non-empty answers,
contexts, supporting facts, and textual evidence chains. Phase 1U remains
immutable, and no claim of complete answer/evidence ID coverage is made.

This adds measurement-readiness evidence only. It does not establish the
2Wiki capability floor or any typed-prior, representativeness, or retention-
aware deployment effect. The ACL main claim remains partially supported and
unchanged. Phase 1W must freeze a separately authorized, bounded 24-call live
calibration contract; provider execution remains closed meanwhile.

## Phase 1W update

The immutable bounded live-calibration authorization preflight passed all
`17/17` checks with aggregate fingerprint
`f4d8947ebbd74aad623337125bea9b448035c43edae9b4bddcc8fab94daac8e2`.
It preserves the Phase 1V scientific request-plan hash `694ecbc...` and
freezes a separate transport-plan hash `099f899a...` after adding only
`model=qwen3.7-plus` and `enable_thinking=false` to the 24 requests.

The contract fixes one-second pacing, zero retries, no `max_tokens`, exact
append-only-prefix resume, raw-response preservation, exact usage accounting,
continuation after known-usage invalid output, and terminal stops for unknown
usage, provider exception, plan or authorization drift, and accounting-ceiling
exhaustion. Conservative exposure is 51,505 input plus 98,304 output tokens,
estimated at CNY 0.889442 under the frozen local rates, with a CNY 10 local
hard ceiling. Network, provider, and paid calls were all zero.

This is authorization-readiness evidence only. It establishes neither a
capability result nor a paper method effect, so the ACL main claim remains
partially supported and unchanged. Phase 1X requires fresh explicit
authorization for exactly 24 attempts; no authorization is inherited from
Phase 1S.

## Phase 1X update

The one-time live calibration completed all `24/24` authorized
`qwen3.7-plus` Token Plan attempts with zero retries, no `max_tokens`, known
usage for every attempt, and preserved raw responses. Exact usage was 27,981
input plus 884 output tokens, and exact local accounting was CNY 0.063034.
SearchQA produced 12/12 contract-valid outputs and 10/12 correct answers.
2WikiMultiHopQA produced 12/12 contract-valid outputs, 7/12 correct answers,
9/12 correct support sets, and 6/12 joint successes.

Applied without retuning, the frozen Phase 1T 2Wiki eligibility gate passes.
Joint baseline accuracy is 50%, inside the inclusive 25%-75% interval; all six
successes have distinct task IDs; and they span three frozen task types and
three reusable skill families. The successful types are `bridge_comparison`,
`comparison`, and `compositional`; the corresponding families are
`bridge_attribute_comparison`, `attribute_comparison`, and `entity_bridge`.
The calibration's `inference` type had no joint success and remains a coverage
limitation, but the preregistered minimum was three successful types.

This establishes substrate eligibility and verified-success availability only.
It does not establish typed-prior benefit, probe representativeness, or
retention-aware deployment benefit. The ACL main claim remains partially
supported. Paid permission closed after the completed 24th attempt, the
authorization is exhausted, and Phase 1Y is restricted to zero-network history
and skill-candidate materialization design.

## Phase 1Y update

The zero-network history audit bound exact disjoint 12/120/24/120 SearchQA and
2WikiMultiHopQA calibration/history/probe/held-out partitions and audited 240
history records. All 24 locally stored Phase 1X calibration responses replayed
consistently but were excluded as calibration. SearchQA history lacks local task
and response payloads; 2Wiki history contains gold tasks but no model
trajectories. Gold records were not treated as trajectories.

The materialization therefore admitted 0 verified trajectories and 0 typed
candidates. Deterministic identities, provenance, rejection reasons, partition
isolation, verifier replay, family/type inventory, and empty-set concentration
were audited with no evaluation leakage. Candidate-contract coverage failed as
an explicit scientific negative result. Phase 1Y adds no typed-prior,
representativeness, or retention-effect evidence, so the main ACL claim remains
partially supported and unestablished on real held-out tasks.

Phase 1Z is scientifically blocked because there is no typed candidate. At
least 10 cross-family history successes would be required (2 SearchQA and 8
2Wiki); only the 8 2Wiki requests can currently be frozen, while SearchQA
history payloads are missing. The exact currently authorizable call count is 0.
The previous 1,152-call product is an unaudited upper bound, not a minimum. No
network, provider, model, or paid call occurred, and no execution authorization
is open.

## Phase 1Y history request plan update

The missing SearchQA history task/context payloads were restored locally from
`data/searchqa_split/train/items.json`; the original dataset files were not
modified. A CLI-generated deterministic plan now binds exactly 10 candidate
history-generation attempts: 2 SearchQA and 8 2WikiMultiHopQA. The plan hash
is `02d387a6d768da2d66cfdda6835abb5764a0204463207a23795a8e845a6f5004`, and
all 10 request hashes are unique.

The frozen plan estimates 10,159 input tokens and permits up to 40,960 output
tokens, with a conservative CNY `0.347998` ceiling under the recorded rates.
It has zero retries, omits `max_tokens`, requires exact append-only-prefix
resume, and hard-stops on unknown usage, provider exceptions, hash or
authorization drift, cost-ceiling exhaustion, non-prefix resume, or duplicate
logical IDs. The plan records `provider_calls=0` and remains closed until fresh
explicit authorization for exactly these 10 attempts.

This preparation does not create verified trajectories or typed candidates:
both remain `0` until responses exist and pass local verifier replay. Phase 1Z
therefore remains blocked and its minimum call count must be recomputed after
history successes are admitted; the old 1,152-call upper bound is not used.

## Phase 1Y live history and candidate update

The one-time authorized history batch completed exactly 10/10
`qwen3.7-plus` requests with zero retries and no `max_tokens`. Local verifier
replay admitted 8 successful trajectories: 2/2 SearchQA and 6/8
2WikiMultiHopQA. Exact usage was 11,610 input plus 501 output tokens (12,111
total), locally accounted as CNY 0.027228. The authorization is exhausted and
all provider execution is closed.

The frozen two-support candidate contract admitted 3 typed candidates:
`fact_retrieval`, `attribute_comparison`, and
`bridge_attribute_comparison`. The `entity_bridge` and `relation_inference`
scopes each retained only one verified support, so complete coverage failed at
3/5 required skill families. Maximum candidate task-family concentration is
2/3; maximum supporting-task-ID concentration is 1/6. Deterministic IDs,
verifier replay, partition isolation, and evaluation leakage checks passed;
no leakage was found.

## Phase 1Z and Phase 1 closure

Phase 1Z performed a zero-provider execution-gate adjudication bound to the
immutable Phase 1Y result and candidate hashes. Because the frozen candidate
coverage gate failed, the held-out causal pilot was not scientifically
executable. Phase 1Z made 0 provider, network, and paid calls and closed as
`inconclusive_without_phase1z_provider_execution`; therefore no typed-prior,
probe-representativeness, or retention-aware held-out effect is claimed.

The theoretical minimum repair would require two additional *successful*
history calls, one for each missing scope. Success cannot be guaranteed, so an
exact guaranteed request count is undefined; the currently authorized count is
0. Phase 1 is closed and no additional Phase 1 stage may be created. The
closure aggregate fingerprint is
`5c2a3c0a1140609c3e51e6a093301dcab5949d14d561e162d9cc1a8f9c2f7340`.

## Phase 2 expansion design v1

## Phase 2 expansion freeze v1

Phase 2 B is independently frozen at the protocol and budget level, but its
concrete task/request freeze is blocked in zero-network preflight. The local
source manifest, namespaced Phase 1 exclusion audit, selector contract,
partition audit, stage gates, request hard stops, and preregistered analysis
are recorded in `artifacts/acl2027_phase2_expansion_freeze_v1/` and
`paper/acl2027/results/phase2_expansion_freeze_v1.md`. SearchQA has only 12
complete local calibration payloads while 70 fact-retrieval payloads are
required for the five disjoint Phase 2 partitions. No tasks or requests were
fabricated; the executable request plan is empty until a new audited payload
artifact exists. Target arithmetic remains 710 logical requests at CNY
6.197280 with a CNY 7.50 ceiling. This is design/preflight evidence only and
does not alter the Phase 1 inconclusive conclusion or open authorization.

Phase 2 is a new independent `design_only` extension. It preserves the Phase 1
real-task method-effect conclusion as inconclusive and does not modify or reuse
Phase 1 immutable evaluation records. The design compares a conservative arm
(4 verified supports, 4 disjoint probes, and 8 disjoint held-out tasks per each
of 5 families) with a stronger arm (8, 8, and 16 respectively). Each family
has two pre-registered development-acquisition attempts followed by a formal
history cap of 16 attempts in the conservative arm or 32 in the stronger arm;
the minimum successful history calls are exactly the required support count,
but the number of attempts needed to obtain them is unknown and bounded only by
the frozen cap.

The design requires distinct request bodies and physical calls for `cold`,
`copied_global`, `global_only`, and `contextual_typed_prior`; retaining and
destructive gating may reuse the same preserved response ledger because they
are local state policies. It explicitly prevents identical gate-label request
pairs, binds task/payload/condition/provenance/request hashes, excludes all
spent and prior calibration/probe/held-out IDs, and keeps gold answers separate
from model trajectories. At the frozen Phase 1T thresholds, the maximum logical
requests are 390 (A) or 710 (B), with planning estimates of CNY 3.334560 or
CNY 6.197280 and conservative ceilings of CNY 4.00 or CNY 7.50. These are
future authorization plans only: this design made zero network, model, and
paid calls, and does not open provider authorization.

## Phase 2 SearchQA payload readiness and freeze v2

The missing SearchQA payload preflight was resolved from the existing local full-payload
files under `data/searchqa_split/{train,val,test}/items.json`; no network download was
needed. Exact string-ID reconciliation against the corresponding ID-only manifests
passed with no unmatched or ambiguous records. After namespaced exclusion of Phase 1B,
Phase 1 calibration, Phase 1X, Phase 1 probe, and Phase 1 held-out IDs, 1,364 complete
SearchQA records remained, including the required 70 fact-retrieval tasks.

The new v2 audit freezes 350 mutually exclusive tasks across five skill families and
materializes 710 deterministic future request hashes. It records zero network,
provider, model, and paid calls; Phase 1 remains closed and inconclusive; and the
Phase 2 plan remains design-only and closed pending explicit authorization. This is
payload/protocol readiness evidence only and contains no method-effect result.

## Phase 2 staged live-runner preflight v1

The recovered staged runner preflight binds the immutable Phase 2 B v2 freeze,
710-request plan, and partition audit by exact file hashes without overwriting
them. The runner now enforces exact-prefix and authorization-hash resume,
stage/call/cost ceilings, exact usage, terminal raw/error preservation,
independent coverage, and probe-audit gating. Formal scaling remains false and
is not a staged-pilot prerequisite; independent paid/provider/Qwen switches and
explicit stage authorization are required.

The closed local preflight passed 16 cache-free tests and produced aggregate
fingerprint `1a4545b63f1b994505e3a724358518143ff50a68f444bb87cce49f64ba066a30`.
It made zero network, provider, model, Qwen, and paid calls. This is execution
safety/readiness evidence only and does not establish a Phase 2 method effect.

Independent acceptance subsequently rejected v1 as authorizable despite its
static regression passing. The original request plan interleaves family blocks,
so v1 silently stopped a 60-call calibration stage after 12 calls; a new-stage
authorization could not resume an old ledger; historical rows consumed the new
authorization quota; caller-supplied fake string supports could pass coverage;
and the aggregate fingerprint did not directly bind runner or test source. The
v1 files and fingerprint remain immutable as a regression record, but v1 must
not be authorized.

## Phase 2 staged live-runner preflight v2

The zero-network v2 preserves the original 710-request Phase 2 B v2 freeze and
adds a deterministic stage-contiguous execution schedule. Its strict bijection
audit reports 710 requests, zero omissions, duplicates, or request-hash
changes; schedule SHA-256 is
`01c4e03660648cf8d5b150f78bf783f273b99899fa6fa4ac8be495090e44dd60`.
Exact-prefix resume now targets that schedule. Immutable authorization-registry
validation preserves historical authorization hashes while current-stage
quotas count only rows produced by the current authorization.

Coverage now requires a hashed candidate artifact bound to verifier-confirmed
formal-history trajectories, tasks, requests, response hashes, frozen family
assignments, provenance, and leakage audit. Probe and held-out remain closed
until their complete coverage and probe-audit gates pass. No real passing
candidate artifact was fabricated; the current preflight status is correctly
`coverage-incomplete`.

Focused cache-free tests passed 27/27 and the combined Phase 2/handoff suite
passed 41/41. A full mock lifecycle produced the exact 60/10/160/160/320 stage
sequence and 710-row schedule prefix under five authorization hashes. The
immutable aggregate fingerprint
`0bf2e595a664a37978f214c6aad64a50c9a03c4751a38a567c527c940dba8b70`
directly binds configs, runner, tests, freeze, plan, partition audit, schedule,
preflight audit, and both gate schemas. Network, provider, model, Qwen, and paid
calls were all zero; every execution switch remains false. v2 is execution
readiness evidence only and adds no method-effect evidence.

Independent acceptance retained the v2 schedule and authorization machinery as
a useful regression record: focused tests passed 27/27, an expanded combined
suite passed 57/57, and an isolated complete mock lifecycle passed with the exact
60/10/160/160/320 sequence, 710 unique request hashes, and five authorization
hashes. All manifest input hashes and aggregate fingerprint recomputed exactly.

However, v2 is not authorizable. `verify_coverage` accepts a caller-authored
artifact plus a caller-supplied hash and trusts its `verifier_confirmed_success`
flags; `verify_probe_audit` similarly trusts a caller-authored `passed` flag.
The passing lifecycle test constructs both verdict artifacts directly rather
than replaying a frozen verifier/analyzer over gold-separated inputs. The CLI
also exposes only the closed preflight and has no accepted crash-durable live
provider/ledger path. These are readiness defects, not negative method-effect
evidence. A separately versioned zero-call v3 repair is required before any
60-call calibration authorization.

The separately versioned v3 repair passed zero-network preflight and is ready
for independent acceptance. Candidate materialization deterministically
replays all 160 formal-history raw responses against frozen parser, normalizer,
private gold, task/family bindings, source/config hashes, and leakage boundary.
Probe audit replays the complete 160-row probe ledger and frozen condition grid.
Caller-authored verdicts, `passed=true`, and attacker-recomputed file hashes
cannot unlock probe or held-out. Insufficient support is `coverage-incomplete`,
not method failure; no real passing coverage or probe artifact was created.

The closed-by-default live path provides preflight, audit, execute-stage, and
resume commands. Exact authorization binding, stage quota, cost ceilings,
route/model policy, atomic durable ledger writes, entry hash chain,
terminal-attempt refusal, and staged exact-prefix recovery were tested.
Focused tests passed 19/19 and the requested combined regression passed 60/60.
Every call stage resumed after simulated termination with zero duplicates; the
mock lifecycle ended at 710 rows under five authorization hashes. Aggregate
fingerprint `9794cfaaa01b7baf1b79fa334c1c2d30961b01f13da3522d46ce2770fdccac39`
binds v3 code, tests, schemas, gold manifests, frozen inputs, schedule, and
audit. Network, provider, model, Qwen, and paid calls were all zero. This is
execution-readiness evidence only; no method-effect claim or authorization was
created.

Independent read-only acceptance did not authorize v3. Fourteen of fifteen
direct manifest file bindings matched current disk content, but the recorded
`runner_source_sha256` has 65 characters and differs from the runner's canonical
64-hex SHA-256. The runtime and tests also do not consume the manifest or
recompute its aggregate fingerprint, so the claimed source binding is not an
enforced authorization gate. v3 remains immutable and non-authorizable. This is
an execution-readiness defect, not negative method-effect evidence; a separately
versioned zero-network v4 must repair and independently pass this binding gate
before any calibration authorization is created.

## Phase 2 staged live-runner preflight v4

The separately versioned zero-network v4 repairs the v3 binding defect. Its
manifest recomputes 16 bound file hashes from current disk bytes, requires
canonical lowercase 64-hex SHA-256 values, and recomputes the canonical
aggregate fingerprint. The frozen config root rejects manifest field drift,
aggregate tampering, runner or test byte drift, and attacker-rehashed manifests.
All preflight, audit, execute-stage, and resume paths enforce integrity before
provider invocation.

The closed authorization binds config SHA-256
`4775d9e55fb97316460e38e9c0a8fd07181b799a8aa9670a7a022194df3b7954`
and manifest aggregate fingerprint
`17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`,
plus the frozen schedule, freeze, request-plan, and partition hashes. Focused
tests passed 26/26 and the v4/v3/handoff suite passed 51/51, preserving the exact
710-row five-stage mock lifecycle and crash recovery. Network, provider, model,
Qwen, and paid calls were all zero. This is execution-readiness evidence only;
Independent read-only acceptance passed on 2026-08-13. The acceptance reran
the cache-free focused suite (26/26), recomputed all 16 disk bindings and the
aggregate fingerprint through the integrity gate, confirmed the frozen root,
and observed zero network, provider, model, Qwen, and paid calls with
`authorization_opened=false`. The prior combined 51/51 regression remains the
recorded full-lifecycle check. v4 is therefore accepted as execution-readiness
evidence, but no calibration authorization exists and no method-effect evidence
was added.

## Phase 2 v10 development-acquisition update

The separately authorized diagnostic completed exactly 10/10 `qwen3.7-plus`
Token Plan calls, two for each frozen skill family. All 10 responses satisfied
the exact JSON contract and 8/10 were verifier-correct. Exact usage was 12,371
input plus 98 output tokens (12,469 total), with CNY 0.025526 local accounting,
zero retries, zero duplicates, no `max_tokens`, and valid request-start pacing.
The authorization closed automatically and no formal-history, probe, held-out,
or formal-scaling call occurred.

`fact_retrieval`, `attribute_comparison`, `bridge_attribute_comparison`, and
`relation_inference` each scored 2/2. `entity_bridge` scored 0/2, resolving an
intermediate attribute or entity rather than the requested final bridge answer.
The frozen design treats development acquisition as a viability diagnostic, so
this does not automatically cancel formal history, but it raises the risk that
`entity_bridge` will fail to reach 8 verified supports within its 32-attempt
formal cap. These 10 responses are development-only and cannot count as formal
history. This is capability/acquisition evidence, not typed-prior, probe,
triage, held-out, or method-effect evidence.

## Phase 2 formal-history, probe, and held-out evidence update

The independently corrected zero-network v13 materializer replayed all 160
formal-history rows while preserving unique logical requests, request hashes,
and provider response IDs. Private-gold leakage checks passed and verified
supports reached 28/32/28/17/16 across the five frozen families. This establishes
typed-candidate coverage and readiness only; it is not probe or held-out effect
evidence.

The completed v20 probe analysis combined 48 reusable v18 rows with 112 v20
recovery rows into a balanced 160-row, 40-task, four-condition grid. Contextual
typed prior scored 28/40 versus 27/40 for global-only, a +0.025 difference with
2 wins, 1 loss, and 37 ties. The frozen probe eligibility gate passed. This is
permission-gating evidence for the subsequent held-out evaluation, not a
held-out method-effect result.

The completed v23 held-out analysis combined 232 preserved v21 rows with 88
v23 recovery rows into the frozen 320-row, 80-task, four-condition grid. Cold,
copied-global, global-only, and contextual typed prior scored 62/80, 59/80,
59/80, and 60/80. The primary typed-minus-global margin was +0.0125 with 2
wins, 1 loss, and 77 ties. It did not meet the pre-registered positive or
negative threshold, so the eligibility gate is `inconclusive`. The evidence
therefore supports neither a positive nor a negative real held-out causal claim
for the typed prior.

All v23 recovery identities, request-start and response hash chains, pacing,
exact-prefix recovery, token/cost accounting, and forbidden-stage counters
passed audit. The combined audit fingerprint is
`9ebaa09c1afdb81e1fa59f7fb429dbc31f8df7b5b26dd10070dfc31552297c2b`.
This supports reproducibility and execution-governance claims, not method
superiority. All provider and formal-scaling permissions are closed; further
experimentation requires separate authorization.

## Phase 2 v25 replication interpretation

The independent post-v23 replication executed the immutable 80-task, four-condition
v24 schedule exactly once. All 320 responses were contract-valid: cold 59/80,
copied-global 61/80, global-only 57/80, and contextual-typed-prior 59/80.
The replication-only paired margin was +0.0250 with 4 wins, 2 losses, and 74
ties. Under the unchanged preregistered rule, the gate is **negative** because
typed losses reached 2. This is bounded negative evidence against claiming a
reliable typed-prior improvement on this replication, not evidence that every
typed prior is intrinsically harmful.

The execution audit passed 320/320 attempts, 697,395 exact tokens, CNY 1.410264,
zero retries/duplicates/terminal rows, valid hash chains/exact-prefix/pacing, and
zero forbidden-stage calls. Audit fingerprint:
`35a683a78dd6057b8e3e5122373de024706eba033e3742c04eaf081fdba0c779`.
The authorization is closed; further experiment stages, models, and formal
scaling require a new independent authorization.

## Phase 2 v31 completion interpretation

The completed v31 recovery supplied the final 220 rows for the frozen 400-task,
1,600-row grid. The combined evidence uses 1,072 complete v27 rows, 308
complete-grid v29 rows, and 220 v31 rows; terminal attempts and the orphan v29
cold row remain excluded provenance.

Strict contextual typed prior accuracy was 308/400 versus 301/400 for
global-only, a +0.0175 margin with 14 wins, 7 losses, and 379 ties.
Alias-tolerant accuracy was 349/400 versus 344/400, a +0.0125 margin with 11
wins, 6 losses, and 383 ties. The result missed the positive threshold on
effect size, win-minus-loss count, family consistency, and mechanism-stratum
size. It did not meet the negative rule. The frozen gate is **inconclusive**.

This does not confirm a reliable typed-prior benefit and does not show that
typed priors are generally harmful. Phase 0 synthetic support remains scoped;
v23 remains inconclusive and v25 remains negative. Phase 2 is complete, all
provider permissions are closed, and formal scaling is not authorized.
Combined fingerprint:
`a203fc9bf435b9bc8d1079e118b1aa34e54a1b647944596ad0aee351a4b958bb`.

## Phase 3A real-task mechanism audit

The zero-network Phase 3A audit preserved the Phase 2 inconclusive gate and
classified all 400 completed task grids using raw-response identity,
normalized-answer identity, strict and alias-tolerant outcomes, and the frozen
typed-versus-global comparison. It found 294 tasks with identical raw responses
under all four conditions, 340 with identical normalized answers, and 368 with
identical alias-tolerant outcomes. Typed and global-only responses differed on
53 tasks, but their normalized answers differed on only 33.

The exclusive taxonomy contains 294 no-observable-uptake tasks, 74 response
changes without alias-outcome changes, 11 typed benefits, 6 typed harms, and 15
other heterogeneous tasks. This strengthens the diagnosis that the real-task
gap is dominated by sparse observable treatment uptake and outcome-insensitive
variation, while preserving genuine heterogeneous benefit and harm among the
small affected subset. It does not establish that typed priors are reliable.

Another random same-distribution scale-up is therefore rejected. A mechanism
bridge must first measure whether the model recognizes an applicable skill,
selects its stable ID, executes the intended intermediate operation, and changes
the final answer relative to global and shuffled-typed controls. The proposed
60-task, five-condition Phase 3B target remains unmaterialized and unauthorized.
Phase 3A aggregate fingerprint:
`0b2c420671b02b4210c3903d5549c5ec137699ec501c028a949da4ebb6212e3c`.

## Phase 3B activation preflight

The zero-network Phase 3B preflight converts the Phase 3A mechanism diagnosis
into a falsifiable real-task design. It freezes 60 entirely new tasks, balanced
12 per family, and 300 unique requests over five conditions. The new
shuffled-typed negative control always presents a bundle sourced from a family
different from the target task family. Task selection is gold-independent,
private gold is stored separately, and Phase 2 task, logical-call, and
request-hash overlaps are all zero.

The model-visible response contract contains exactly declared applicability,
selected skill ID, a short intermediate operation label, and final answer.
This makes prior uptake directly observable rather than inferring it only from
answer changes. The frozen analysis compares contextual typed uptake with the
shuffled control, scores final answers under both strict normalized and
alias-tolerant rules, and reports results overall and by family. The stop rule
forbids scale-up when contextual uptake is below 0.15 or the contextual-minus-
shuffled uptake difference is below 0.05.

This is design evidence only. It preserves the Phase 2 inconclusive gate,
creates no authorization, and makes zero network, provider, model, paid, or
formal-scaling calls. Phase 3B aggregate fingerprint:
`fe1bb5316f57e4aa4dba14e19a173a44c60575263bd54018b8b33e6d256de7b8`.

## Phase 3B recovered activation evidence

The completed v3/v5 evidence chain produces a full 60-task, 300-row grid while
preserving failed-attempt provenance and never retrying a spent request. The
analysis admits 125 rows from complete v3 task grids and all 175 completed v5
recovery rows; the partial v3 task and its terminal row are excluded and
replaced as frozen by v4.

The primary mechanism result is positive. Contextual typed bundles were
explicitly adopted on 60/60 tasks versus 31/60 for shuffled typed bundles, a
+0.4833 paired difference with 29 contextual-only and zero shuffled-only uses.
The difference is concentrated in fact retrieval, relation inference, and
entity bridge. Both comparison families adopted contextual and shuffled bundles
on every task, exposing a remaining specificity weakness rather than hiding it.

Final-answer evidence is bounded. Alias-tolerant contextual accuracy was 53/60,
compared with 50/60 shuffled and 54/60 cold. Strict contextual accuracy was
49/60, compared with 46/60 shuffled and 49/60 cold. Therefore the evidence
supports the claim that typed historical skills can be recognized and selected
in a strongly family-sensitive way under an explicit activation contract. It
does not yet support a general claim that inherited skills improve accuracy
over no skill context.

The frozen positive gate passed, the stop rule did not fire, and scale-up is
eligible only as a separately designed and authorized next phase. All 175 v5
calls completed with zero retries, valid pacing and identities, 439,441 exact
tokens, and CNY 0.940886 exact stage cost. Analysis fingerprint:
`d228d3b907091a8001d3f3379bd1ad1ded2af1cf30dfe0c148226a6be9cc435f`.

## Phase 3C mediation evidence

The zero-network Phase 3C audit separates selective contextual adoption from
indiscriminate adoption and links uptake to intermediate operations and final
answers. Of 60 tasks, 29 were contextual-only and 31 adopted both contextual
and shuffled bundles.

For contextual-only tasks, intermediate operations changed on 26/29, showing
that typed history can alter the model's declared procedure. However, normalized
answers changed on only 1/29, and contextual accuracy had zero net wins over
both shuffled and cold under alias-tolerant scoring. Thus Phase 3B's positive
uptake evidence does not yet mediate into reliable task utility.

The 31/60 both-adopt stratum fires the frozen specificity warning and includes
every task from the two comparison families. This is bounded evidence for a
remaining abstention and bundle-specificity failure, not evidence that historical
skills are useless. The frozen mediation gate is **inconclusive**; cross-domain
scaling is deferred until a new zero-network design directly repairs and tests
specificity. Fingerprint:
`0e1769ea906c18907f7161aea5fd93b30add92738b6cce26be32091dfb1b30fd`.

## Phase 3D specificity-repair design evidence

The zero-network Phase 3D preflight addresses the exact limitation exposed by
Phase 3C rather than expanding the same treatment. It freezes 40 new tasks from
the two comparison families and 240 requests spanning contextual, irrelevant,
dual-candidate order, global, and cold controls.

The design makes rejection directly observable. Every presented candidate must
receive an applicability judgment, the selected ID may be `none`, and reversed
dual-candidate order isolates position bias from skill-family specificity. The
positive gate also requires operation and answer mediation plus outcome
non-regression, so prompt-compliance or selector-only success cannot be reported
as task-utility evidence.

This is design and readiness evidence only. All prior identity overlaps are
zero, the future schedule is not authorized, and cross-domain scaling remains
closed. Aggregate fingerprint:
`59143bd2c63bf73c4f747121d547216a2665c7bd722fb7c672b0e12e9db2e5b0`.

## Phase 3D execution-readiness evidence

The zero-network v2 live preflight independently rechecks the 240 frozen
request identities and binds the complete future execution contract. It records
the exact provider destination and payload classes, model and decoding settings,
pacing, stage and cumulative cost ceilings, usage and hash-chain accounting,
terminal-stop behavior, and automatic authorization closure.

This strengthens auditability, not the substantive mechanism claim. No model
response was collected, so specificity, abstention, mediation, and outcome gates
remain unevaluated. Provider execution requires the verbatim authorization
statement stored in the preflight artifact; generic continuation is not valid
authorization. Preflight fingerprint:
`1b57aabe12711ef646674dc39dcc01990c8e0088c667c30fe0818d47c26f4970`.

## Phase 3D executed evidence

The Phase 3D run completed 240/240 authorized calls with exact usage and a
closed authorization. Its strict response contract has a decisive limitation:
the model systematically represented candidate assessments as an ID-keyed
mapping rather than the frozen ordered array. Consequently, strict
contract-validity is 0/240 and the prespecified gate is **negative**.

The non-gating shape-tolerant diagnostic is useful mechanism description but
does not repair the claim. It finds perfect contextual and dual selection after
reconstructing the specified order, but only 0.675 irrelevant rejection, zero
answer net wins over irrelevant context, and two net losses versus cold. The
evidence therefore supports neither reliable abstention nor answer utility, and
does not license cross-domain scaling. Strict fingerprint:
`501f57df97267d3dae84fa953e0652102e5d003572d9e40c58d8a50010e22b29`.

## Phase 3E control-validity evidence

The zero-network Phase 3E audit preserves Phase 3D's strict negative gate but
narrows the diagnostic interpretation. The attribute-comparison negative
control was operation-incompatible and was rejected on all 20 tasks. The
bridge-attribute negative control was invalid because the entity-bridge bundle
provided the necessary film-to-director operation; it was applicable and
selected on 13/20 tasks. This is control contamination, not evidence of
indiscriminate adoption. A future design must use an operation-incompatible
bridge-family control and pre-register the provider's candidate-ID-keyed
assessment mapping as its response contract. No calls occurred. Fingerprint:
`ca9b53061590b7d11f45a355a4e19b177806e8366707a70ceb4e8005c5eb26e7`.

## Phase 3F executed contract-and-control evidence

The 240-call Phase 3F v2 execution is fully accounted: 240/240 completed,
zero retries, valid pacing and hash chains, 711,240 exact tokens, CNY 1.543848
stage cost, and a closed authorization. Its strict analysis is **inconclusive**:
221/240 contract-valid rows, contextual selection 1.0, irrelevant rejection
0.625, dual correct selection 0.95, and answer-change rate 0.40.

The separately versioned boolean-mapping diagnostic is non-gating. It raises
contract validity to 238/240 and shows irrelevant rejection 1.0 plus dual
correct selection 0.975, but its 0.05 answer-change rate fails the frozen 0.10
mediation requirement. Accordingly, it supports bounded selector specificity,
not reliable answer mediation or cross-domain scaling. Strict fingerprint:
`d797e795ba5d6318cbeb01ce8ff7187949a134679a621a673855b216e3a3d0cc`;
diagnostic fingerprint:
`96e6678979361ed7b840bc0b1e80ac4ddbf1b19ebbb49ede377a3379b224d0b4`.

## Research-line decision (2026-08-22)

The original thesis line `typed/scoped priors + representative sparse validation -> improved continual routing` is now `LEGACY / FROZEN / READ-ONLY`. Its supported evidence is scoped mechanism evidence, operation-incompatible prior risk, and the selector-to-grounding gap. Reliable real-task routing improvement, sparse-probe representativeness, and triage utility remain unestablished. Legacy results cannot be used for tuning or new candidate construction.

The active thesis line is `scope-aware admission + answer-level evidence grounding -> auditable and safer historical experience reuse`. It treats candidate identity/scope, admission, selected skill, intermediate operation, evidence resolution, final answer, and counterfactual-answer avoidance as separate endpoints. Phase 5 is bounded evidence for this line, not a claim of general accuracy improvement.
