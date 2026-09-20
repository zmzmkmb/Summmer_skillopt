# Phase 1W: bounded live calibration authorization preflight

## Purpose

Phase 1W binds the immutable Phase 1V SearchQA and 2WikiMultiHopQA
calibration plan to one separately authorized live transport contract. It
freezes request identity, provider route, model, pacing, retry behavior,
response preservation, exact usage accounting, local cost controls, resume,
and terminal stops before any provider permission is opened.

This phase is a zero-network authorization preflight. It does not measure
model capability or establish a paper method effect.

## Frozen live contract

- exactly 24 logical calls and 24 physical attempts;
- 12 admitted SearchQA requests followed by 12 2WikiMultiHopQA requests;
- model `qwen3.7-plus` through the user-confirmed Beijing Token Plan route;
- `temperature=0`, `enable_thinking=false`, and no `max_tokens` request key;
- one attempt per logical call, zero SDK retries, zero explicit retries, and
  one-second pacing;
- raw provider text and exact usage preserved for every known-usage result;
- known-usage malformed or schema-invalid outputs remain visible and
  continuable;
- unknown usage, provider exception, plan drift, authorization drift,
  call-count drift, and accounting-ceiling exhaustion are terminal;
- resume requires the completed records to be an exact append-only prefix of
  the frozen transport plan.

The original scientific request hash remains separate from the transport
request hash. The transport adds only `model` and `enable_thinking` to each
Phase 1V request.

## Cost contract

The frozen local accounting rates are CNY 2 per million input tokens and CNY
8 per million output tokens. The Phase 1V prompts contain 103,010 message
characters. At a conservative two characters per input token and 4,096 output
tokens per call, the planning exposure is:

```text
input tokens:              51,505
output tokens:             98,304
conservative cost:       CNY 0.889442
local accounting ceiling: CNY 10.000000
```

The CNY 10 ceiling is a local hard stop and is never translated into a
provider request parameter. `max_tokens` is not used as cost control.

## Audit result

All 17 checks passed. Network calls, provider calls, and paid calls were all
zero.

```text
decision: preflight_passed_new_explicit_authorization_required
scientific request-plan hash: 694ecbc1ad016f22452a9d94652485f8088afc7f18d54620bc8bfc9693844ac0
transport request-plan hash:  099f899a2c5c06a1773b43d55909f5ac7e446ea37af9b9aceeed4441f2fa08b8
evaluator-private hash:       4b7beaf887abce1b111ece39e46606108f1502b53cbc24cd7a5dd6b3452ca65c
aggregate fingerprint:       f4d8947ebbd74aad623337125bea9b448035c43edae9b4bddcc8fab94daac8e2
```

Simulations verified known-usage invalid continuation, raw-response
preservation, exact-prefix resume, terminal unknown usage and provider
exceptions, independent authorization binding, plan drift, and the exact CNY
10 accounting boundary. Simulated attempts are not provider calls.

## Scientific interpretation

Phase 1W establishes that the bounded capability calibration can be executed
under an auditable, non-expanding transport and accounting contract. It does
not show whether either dataset clears a capability floor, and it adds no
typed-prior, probe-representativeness, or candidate-retention evidence. The
ACL main claim remains partially supported and unchanged.

## Next step

Phase 1X requires a new immutable authorization config and explicit user
authorization for exactly 24 `qwen3.7-plus` Token Plan attempts under the
frozen CNY 10 ceiling. Authorization cannot be inherited from Phase 1S.
Provider execution, qwen3.8-max, staged/full scaling, formal scaling, and the
legacy OfficeQA/SpreadsheetBench batch remain closed meanwhile.
