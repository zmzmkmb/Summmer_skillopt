# Phase 2 probe prompt/route correction preflight v15

This zero-network preflight investigates the terminal HTTP 400 from v14 without retrying its spent logical request.

The frozen 160-row probe schedule uses system prompts of the form `return the frozen response schema`, but does not state the JSON object shape and does not contain a `response_format` field. The successful v8 route instead explicitly requires exactly one JSON object with shape `{"answer":"<short answer>"}` and binds `response_format=json_object` with thinking disabled. The v14 transport added `json_object` only at dispatch.

The comparison verifies a prompt/transport contract mismatch and establishes that correction is required before another probe execution. It does not prove the provider's exact HTTP 400 cause because the error body was not persisted.

- Frozen probe rows: 160
- Permanently spent v14 rows: 1
- Network/provider/paid calls: 0/0/0
- v8 JSON contract verified: yes
- adapter JSON route verified: yes
- aggregate fingerprint: `833aa6e99bda15722458147031f170e95d62a11cee0c6e63f6096eda9d0301b8`
- provider authorization: closed

The next permissible work is a separately versioned 160-row replacement schedule with an explicit JSON prompt contract and a new task replacing the spent v14 request. Any live execution requires fresh probe-only authorization. Held-out, later stages, and formal scaling remain forbidden.
