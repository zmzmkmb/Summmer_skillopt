# Phase 2 probe-only live v14

## Authorization

The user authorized only the frozen 160-call probe schedule with `qwen3.7-plus`, temperature 0, zero retries, no request `max_tokens`, and CNY 7.50 stage and cumulative ceilings. Held-out execution, later stages, and formal scaling were not authorized.

The zero-network v14 preflight passed before provider activation. It bound the accepted v4 aggregate fingerprint `17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`, v13 aggregate fingerprint `b85558e67b05589384b628d1bbc082b840ea3b8175260ec71a2cd14a0d82f244`, the exact 160-row probe schedule, and the coverage-passed v13 candidate artifact. The focused v14 suite passed 8/8 and the combined v14/v13/v4 suite passed 38/38 with zero network calls.

## Terminal result

The first authorized provider attempt returned HTTP 400 Bad Request. Under the zero-retry contract, the logical request was recorded once as terminal, the remaining 159 requests were not attempted, and the authorization closed immediately.

- Planned calls: 160
- Provider attempts: 1
- Completed calls: 0
- Unique logical requests: 1
- Duplicate requests: 0
- Retries: 0
- Request-start rows / ledger rows: 1 / 1
- Model: `qwen3.7-plus`
- Temperature: 0
- `max_tokens`: absent
- Usage metadata: unavailable for the terminal attempt
- Exact input/output/total tokens: unknown
- Exact local cost: unknown
- Known token and cost lower bounds: 0 tokens, CNY 0.0
- Held-out calls: 0
- Formal-scaling calls: 0
- Authorization: closed

The additive v14.1 audit preserves unknown-usage semantics; the original v14 empty-known-usage sum must not be interpreted as exact zero usage or exact zero cost.

## Gate and diagnosis

The complete 160-row probe audit was not reached, so the probe gate is not evaluated and this run adds no method-effect evidence.

Offline comparison shows that the frozen probe system prompt says only `return the frozen response schema` and the frozen schedule does not contain `response_format`, while the successful v8 route explicitly states the JSON object shape and binds `response_format=json_object`. The v14 transport added `json_object` at dispatch. This mismatch is a plausible explanation for HTTP 400, but the provider error body was not persisted, so it is not a verified root cause.

Any continuation requires a separately versioned zero-network prompt/route correction, must permanently exclude the spent v14 logical request, and then requires fresh probe-only authorization. No v14 request may be retried or resumed.
