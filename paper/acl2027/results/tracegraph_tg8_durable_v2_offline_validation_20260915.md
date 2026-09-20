# TG8 Durable V2: Offline Validation

Date: 2026-09-15 (Asia/Shanghai).
Status: candidate implementation, formal execution closed.

## Evidence Boundary

No ALFWorld environment was constructed or stepped during this repair.
The 360-row tests use the frozen schedule with a synthetic row executor,
not real observations or task outcomes. No new dataset or model was used.
These results establish execution-recording behavior, not the TG8 hypothesis.
Both interrupted v5/v6-receipt attempts remain incomplete with unknown metrics.

## Changes

- The old runner is unchanged at SHA256
  `ef7e0a19780fd514a9227849b2467d0734f3f3c0a8cc840bd648a501ed4dfeed`.
  V2 calls its `run_row` directly; selector, runtime input projection,
  schedule, step cap and metric definitions are unchanged.
- Each row is preceded by a flushed/fsynced start event. Each completed or
  exception-returned row is written and fsynced, then atomically published
  via a non-overwriting hard link before the next row begins.
- Output directories and authorization claims cannot be reused. A Linux
  advisory lock prevents concurrent v2 workers.
- A hidden Windows WSL client waits for a systemd service; the service is
  independent of the interactive tool session and has `Restart=no`,
  `KillMode=control-group` and `PrivateNetwork=yes`.
- The proposed service has a 21600-second wall-time limit and 30-second
  stop grace period. This is a NEW infrastructure safeguard requiring
  explicit authorization, not a scientific stopping criterion or retry.
- Config, receipt, manifest, stdout/stderr, durable events, row JSON files
  and exit status are separate artifacts. The inspector reports saved
  evidence only and never resumes execution.
- The activated configuration is bound by canonical SHA256 excluding only
  the receipt path/hash to avoid a circular digest. The new receipt must
  also bind the new runner, unchanged legacy runner, output path and timeout.
  Old receipts cannot authorize v2.

## Verification

Initial Windows run: 29 passed, 2 Linux-only tests skipped (durability,
selector-v3, readiness and v4 preflight).
Initial WSL run: 16 durability tests passed, including lock and network
namespace rejection checks. Final regression counts are recorded below.

Final Windows regression: **40 passed, 2 Linux-only skipped** in 30.56 seconds.
Final WSL durability regression: **18 passed** in 10.30 seconds.
The intermediate Windows `windows_final_v1.xml` recorded one failure
(39 passed, 2 skipped): a backslash-versus-slash recovery path mismatch.
The inspector now uses POSIX artifact paths on both platforms; the failed
report is retained and the successful rerun uses a different filename.
Handoff validation passed (61 completed phases, 7190 immutable legacy runs);
that validation is a provenance check, not new TG8 completion evidence.

Reports under `artifacts/acl2027_tracegraph_tg8_durable_v2_offline_20260915`:

| File | SHA256 |
| --- | --- |
| `windows_final_v2.xml` | `7d5b3274dbfa9ef3ecb9883d2a0ccacc6c8e169a18b41fc5107b80fbe54b76d2` |
| `wsl_final_v2.xml` | `2cebaf84110254bc4b2c3206c917c742b84c770f6861f241c3eb9873b42e97be` |

Final candidate bindings:

| Item | SHA256 |
| --- | --- |
| Durable runner | `6d6d1ad26f5f5ea18d7da8b8dece366035588fbd3ac5ee4dc7dab419091263e8` |
| Windows launcher | `454bc03eced27322ec4b7041ed5860d7aaee1db80f7d0f3aa390ab6e5558a4f7` |
| Closed candidate file | `a925fdcee7e670eaa02940863c580bd5a8e80bb8de7dfb0c63b48590891a7fc7` |
| Proposed activated canonical config | `a5617a8c1ed4d4671ebddfaedeedce0415cc60f7c1e7876c68b87909fc14d2b8` |

The closed candidate validator reports exactly four authorization-related
errors (closed execution flags/status and absent receipt); all file, scope,
schedule, selector, readiness and skillbank bindings pass. See
`paper/acl2027/TG8_DURABLE_V2_AUTHORIZATION_REQUEST_20260915.md` for the new
authorization request. Merely writing that request does not grant permission.

Offline service smoke:

- Unit: `tg8-offline-smoke-7be37faa193e403f87d6c96c8bff0c66`.
- Started: 2026-09-15 21:38:05 CST; finished: 21:38:15 CST.
- Hidden Windows process was submitted and its parent command returned.
- Journal recorded `isolated: true` and then `formal_episodes: 0`.
- systemd client recorded `code=exited/status=0`, runtime 10.253 seconds.
- The probe only checks its local namespace identity and sleeps.

Tests cover all 360 synthetic row IDs in order, save-before-next-row,
first-error stop with partial evidence, acknowledged-versus-attempted step
counts, disk failure, startup failure, KeyboardInterrupt, forced process
termination, torn event logs, partial files, no-clobber publication,
authorization/hash tampering, receipt reuse and old-receipt rejection.

An existing handoff test still asserted the pre-execution September 10
state. It was updated to require the actual blocked/closed state, preserved
unknown counts for the interrupted attempt, and zero formal repair episodes.

## Remaining Limits

This does not prevent Windows/WSL shutdown, power loss or forced termination.
An active row can still be lost; a missing exit record is not success.
Directory/file fsync was exercised, but storage-controller power-loss
guarantees have not been tested. A pending file is diagnostic, not a result.
The synthetic smoke does not prove an ALFWorld run will complete under the
service. The frozen executor still has blocking environment calls, and its
exception label can include infrastructure errors. The new wall limit bounds
that risk without retrying. No real environment smoke is authorized here.

The field `actions_taken` retains the legacy transition-count semantics.
`acknowledged_steps` separately counts returns from environment steps; neither
should be substituted for an unknown mid-call outcome after interruption.
Network counters are not fabricated as independent measurements: the
service namespace enforces isolation, while the row execution imports no
new provider or model. PrivateNetwork alone is not a full security sandbox.

Next gate: a new exact authorization for the bound v2 candidate, followed
by one independent run and a full 360-row artifact audit. No claim about
representation/controller effects is justified before that audit.
