# TraceGraph TG6 Local Execution Runner v1

Date: 2026-08-31

## Scope

- Parent authorization scope: `configs/acl2027/tracegraph_tg6_local_execution_preflight_v1.json`
- Parent-scope SHA-256: `f9ec6efe63d044adf1614f3ca7d67c7b434963c94cdea44ac093498c4ab77c7c`
- Runner configuration SHA-256: `2d60a6557affc9d67dc2fd7d7f6fb9cf3b6e3ba239461b2d427b99df4f8bf67e`
- Frozen schedule: 40 held-out ALFWorld tasks, zero retries, stop on first hard invariant violation
- Runtime inputs: `observation`, `historical_actions`, `admissible_actions` only
- Provider/model/API/network calls: forbidden and observed as zero

## Terminal outcome

Execution stopped at the first hard invariant violation. Two tasks were started;
one task completed its 50-step budget and one task failed during environment
initialization. No retry or resume is permitted under the authorization.

| Metric | Value |
| --- | ---: |
| Tasks scheduled | 40 |
| Episodes started | 2 |
| Episodes completed | 1 |
| Successful episodes | 0 |
| Retries | 0 |
| Network calls | 0 |
| Provider calls | 0 |
| Model calls | 0 |
| Paid API calls | 0 |

The first task (`valid_seen/look_at_obj_in_light-AlarmClock-None-DeskLamp-323/`
`trial_T20190909_044715_250790`) ran 50 steps and ended with
`environment_done` without success. The second task
(`valid_seen/look_at_obj_in_light-BaseballBat-None-DeskLamp-303/`
`trial_T20190907_060414_846460`) stopped at step 0.

## Blocking error

The ALFWorld/TextWorld worker raised `KeyError: 'val1'` while parsing the
second task's `game.tw-pddl` during environment reset. This is recorded as a
local environment-integrity blocker, not as a TraceGraph capability result.
The failed initialization must not be retried under this authorization.

## Artifact policy

The raw runner result is preserved byte-for-byte as `result.json` in the
immutable artifact directory. The artifact is descriptive and terminal; it does
not authorize Phase 6, WebShop, provider/model/API work, or reuse of any
Phase 0-6 artifact.
