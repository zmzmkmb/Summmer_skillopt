# Phase 1V: calibration request and verifier preflight

## Purpose

Phase 1V converts the admitted 12-task SearchQA calibration payload and the
12-task 2WikiMultiHopQA calibration payload into one deterministic,
leakage-controlled request plan. It freezes model-visible requests,
evaluator-private gold data, strict parsers and verifiers, resume behavior,
exact usage accounting, and terminal failure semantics before any provider
authorization.

This phase establishes measurement readiness only. It does not call a model,
measure either substrate's capability, or establish a paper method effect.

## Audit result

The immutable preflight passed all 14 checks:

- exactly 24 requests are ordered as 12 SearchQA requests followed by 12
  2WikiMultiHopQA requests;
- all request identities and source hashes bind to the completed Phase 1U
  artifacts;
- model-visible requests are structurally separated from evaluator-private
  answers, aliases, supporting facts, and evidence metadata;
- no held-out partition is an input;
- SearchQA requires exactly `{answer}`;
- 2WikiMultiHopQA requires exactly `{answer, supporting_evidence}` and joint
  answer-plus-supporting-fact success;
- known-usage malformed or schema-invalid responses remain visible and allow
  execution to continue;
- unknown usage appends a terminal non-resumable record;
- resume requires an exact append-only completed-plan prefix;
- plan drift is terminal;
- usage accounting is exact and retries are zero;
- network, provider, and paid calls are all zero.

Decision:

```text
preflight_passed_provider_execution_closed
```

Request-plan SHA-256:

```text
694ecbc1ad016f22452a9d94652485f8088afc7f18d54620bc8bfc9693844ac0
```

Evaluator-private SHA-256:

```text
4b7beaf887abce1b111ece39e46606108f1502b53cbc24cd7a5dd6b3452ca65c
```

Aggregate fingerprint:

```text
845af0618483eecfd9e3063162be0fc2133743ba69fdbeaebd9a34e44c5e041f
```

## Selected-record metadata findings

The strengthened selected-record audit exposed two upstream metadata gaps in
the 12 frozen 2WikiMultiHopQA calibration records:

- 5 records have a non-empty textual `evidences` chain but an empty
  `evidences_id` list;
- 1 record, whose answer is `1969`, has `answer_id=null`.

These gaps are preserved explicitly through `evidences_id_available=false`
and `answer_id_available=false`. They do not block the frozen verifier because
every selected record still has a non-empty answer, context, supporting facts,
and textual evidence chain. When evidence IDs are present, their shape and
content are validated strictly. Phase 1U remains immutable; Phase 1V does not
retroactively claim complete answer-ID or evidence-ID coverage.

## Scientific interpretation

Phase 1V removes ambiguity in request identity, leakage control, parsing,
automatic verification, failure visibility, resume, and accounting for the
bounded calibration. It does not show that 2WikiMultiHopQA clears the frozen
non-floor capability gate, and SearchQA remains admitted independently under
the user's experiment policy.

The ACL main claim is unchanged. Typed-prior benefit, sparse-probe
representativeness, and candidate-retention benefit remain unconfirmed on the
new substrate.

## Next step

Phase 1W should freeze a separately versioned live calibration configuration
bound to these exact 24 request hashes. It must specify the provider route,
model, cost ceiling, zero-retry runner, exact usage handling, and one-time
authorization boundary. Provider execution remains closed until the user gives
separate explicit authorization for those 24 calls.
