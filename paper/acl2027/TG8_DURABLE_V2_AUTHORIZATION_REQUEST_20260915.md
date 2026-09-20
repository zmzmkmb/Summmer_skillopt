# TG8 Durable V2 Authorization Request

Prepared 2026-09-15. This document is a request, NOT an authorization receipt.
Formal execution is still closed. Prior authorizations cannot be reused.

## Proposed Authorization

I authorize one new independent TG8 v4 run using the durable v2 executor
and hidden Windows/WSL/systemd launcher, with these exact SHA256 bindings:

| Binding | SHA256 |
| --- | --- |
| Closed candidate config file | `a925fdcee7e670eaa02940863c580bd5a8e80bb8de7dfb0c63b48590891a7fc7` |
| Activated canonical config | `a5617a8c1ed4d4671ebddfaedeedce0415cc60f7c1e7876c68b87909fc14d2b8` |
| Durable v2 runner | `6d6d1ad26f5f5ea18d7da8b8dece366035588fbd3ac5ee4dc7dab419091263e8` |
| Windows launcher | `454bc03eced27322ec4b7041ed5860d7aaee1db80f7d0f3aa390ab6e5558a4f7` |
| Frozen v1 row executor | `ef7e0a19780fd514a9227849b2467d0734f3f3c0a8cc840bd648a501ed4dfeed` |
| v4 aggregate fingerprint | `098bee6f10b47fb8dbe656785c3732a949448047f72bb0454bb48545299ceffe` |
| Selector | `6aae3a8539594bdb65bdeab92f9d82c2de9ac0e287f036af1e83157751636622` |
| Selector config | `36407699541289ea42a69362f1a6a3c2582648b1e1b7680781ed6725ee066582` |
| Readiness | `85627fd938abce62e254a68957893f81b1389cc0a7e6519976d338a15ed3904b` |
| Existing TG1 skillbank | `15059dd2cc5b99fc69d0bae79109ec20c8d000ec9d550ce237d06ee9ffd6a331` |

Run the fixed 360 rows, at most 75 steps each, zero retries, stop on the
first hard invariant violation and invalidate the full factorial run.
Permit runtime inputs only `observation`, `historical_actions`,
`admissible_actions`. Do not run network/provider/model/API/paid calls,
Phase 0-6, WebShop, other models or other datasets.

I explicitly accept a NEW infrastructure time limit: request service stop
after 21600 seconds (6 hours), with at most 30 seconds of shutdown grace.
If it times out or is interrupted, preserve the evidence, mark the run
incomplete, and do not retry or resume it. A timeout is not a scientific
negative result.

Use this new independent directory, never overwriting previous outputs:

`artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260915_v1`

Keep the old candidate and all old receipts unchanged. Derive a NEW
authorized config from `configs/acl2027/tracegraph_tg8_durable_v2_candidate.json`
by changing only `execution_authorized=true`, `episode_execution_allowed=true`,
`authorization_status=authorized`, and the new receipt path/SHA256.
The activated canonical digest excludes only the receipt path/SHA256.
Create a new receipt bound to the activated config, runner hashes, new
output path and wall-time limit. No output override, automatic restart,
retry, continuation from saved rows, or additional run is authorized.

## Before Launch

Recheck every hash and handoff state; confirm there is no existing TG8
runner; verify the independent directory does not exist; then launch once.
Monitor the systemd unit and durable row/event files. A process or launch
record alone is not evidence of progress, completion or invariant validity.
