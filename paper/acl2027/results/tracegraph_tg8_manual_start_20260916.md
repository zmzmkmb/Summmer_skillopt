# TG8 Manual-Plan Run Started

The user explicitly authorized plan
`bb68465f38a85105042dc086426415f1b6b2465c67997569d5bc412399c072ba`
and asked Codex to start it. The operator relayed that exact authorization
through the frozen confirmation prompt. Chat-source provenance is recorded
separately in `configs/acl2027/tracegraph_tg8_manual_chat_authorization_20260916.json`;
the unchanged helper labels the received input `explicit_local_terminal_confirmation`.

Two host-only failures occurred before any authorization or episode:
the first failed to deliver stdin to Read-Host; the second lacked
Get-FileHash in its detached PowerShell module environment. Both sets of
logs and claims are preserved. A prompt-synchronized relay with explicit
native module loading passed detached CheckOnly and a transport smoke
before the actual activation. Frozen plan, selector, runner and launcher
files were not changed. Exactly one formal run was submitted.

The new output is
`artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1`.
Service `tg8-v2-f0cdf278bffd858564cf` started at 2026-09-16 23:21:26 CST.
Its PID is 380, with Restart=no, NRestarts=0, PrivateNetwork=yes,
RuntimeMaxSec=6h and TimeoutStopSec=30s.
The service's nominal deadline is 2026-09-17 05:21:26 CST; the Windows
supervisor prints 05:21:27 CST, reflecting the separate clock/readout.
No extension beyond this six-hour scope is authorized.

Windows relay PID 27988 keeps supervisor PID 18772 alive; WSL keeper PID
29516 waits for the service. A real SYSTEM awake request was observed;
DISPLAY had no awake request. AC must stay connected and the lid must stay
open. No permanent power-policy setting or Codex heartbeat was created.
Do not close/kill the background supervisor. Explicit sleep, shutdown or
power loss are outside the idle-sleep protection.

At 23:23:55 CST, six unique rows forming the exact schedule prefix had been
saved, totaling 216 steps and two successes. Step caps, exact three runtime
fields, complete histories and selected-action admissibility passed checks;
all six rows recorded null hard-invariant violations. No exit/result existed.
This is interim startup evidence, NOT a full-factorial scientific conclusion.

Machine-readable verification:
`artifacts/acl2027_tg8_manual_control_20260916/startup_verified.json`.
The authorization is consumed. Monitor/read only; never submit, resume,
overwrite or retry. On terminal state, audit all available records and
distinguish completion from an incomplete or invalid factorial run.

## Authorized Control Amendment

The user subsequently asked to cancel automatic time stopping and inspect
lid-close behavior. At 23:57:25 CST on September 16, the existing unit was
verified active/running with RuntimeMaxSec=infinity, the same PID380/start,
NRestarts=0 and PrivateNetwork=yes. A unit-specific runtime drop-in and
daemon-reload changed only the service time cap.

Before retiring the old timed supervisor PID18772 at 23:44:43, replacement
guardian PID27152 acquired a SYSTEM-only awake request at 23:40:35. It reuses
only the parsed power-helper function from the unchanged, hash-verified
entrypoint; it never invokes that entrypoint's launch body. Its power smoke
and read-only target-identity check passed. The WSL keeper PID29516 and Linux
experiment remained running, and saved rows grew from 30 to 61. The new
guardian has no elapsed-time stop and releases its awake request after the
existing service terminates. Fixed experimental caps and all prohibitions
are unchanged. The original config and receipt retain their original hashes;
the separate authorization amendment records the effective time-cap removal.

Evidence: `artifacts/acl2027_tg8_manual_control_20260916/deadline_cancellation_applied.json`.
The latest read-only snapshot contains 61 saved rows and 12 successes, with
no exit; only the earlier six-row prefix has the detailed audit above.

Powercfg showed AC/DC lid action index 0, Do nothing. No setting was changed.
This supports that the configured lid action will not itself request sleep;
it is not a physical lid-close test or a guarantee against firmware,
thermal or power-loss interruption.

## Terminal Update: September 17

The run completed at 2026-09-17 08:08:45.965176 Asia/Shanghai (exit 0):
360/360 rows, 45 successes, 16,311 acknowledged actions. The guardian
recorded terminal state at 08:08:46 and released SYSTEM awake protection.
The start/running instructions above are historical and must not be used
to relaunch. Original config, receipt, rows and logs remain untouched.

The separate terminal report is
`paper/acl2027/results/tracegraph_tg8_manual_terminal_audit_20260917.md`.
Full offline selector validation passed for all 360 rows and 16,311 steps.
All failed rows ended at
step 50, so the intended 75-step sensitivity cannot be claimed. Raw success
counts are 0/90, 0/90, 3/90 and 42/90 in frozen condition order; scientific
inference uses 30 task clusters, not 360 independent observations. The
separate primary task-cluster analysis and Chinese TG6-TG8 report are complete.
