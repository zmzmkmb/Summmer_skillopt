# TG8 Manual Start

This is one new independent run, not a retry or continuation of the 103
saved rows. Preparation has NOT started any experiment. No Codex heartbeat
or online assistant is required after the user starts the local script.

## Start

From a PowerShell terminal in the project, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_acl2027_tg8_manual_v1.ps1
```

The script displays the full frozen plan and asks for explicit confirmation.
Only after the user enters the displayed `AUTHORIZE <plan SHA256>` line does
it create the new receipt/config and submit the run. The plan digest is:

`bb68465f38a85105042dc086426415f1b6b2465c67997569d5bc412399c072ba`

Connect AC power, leave the lid open and leave the terminal open. Minimizing
the terminal is fine. The script requests system wakefulness, NOT display
wakefulness; the screen may turn off. It does not change the power plan.
The temporary request is released on normal/error exit. Forced sleep,
closing the lid, shutdown, loss of power or closing the terminal are not
covered by this protection. Never put a running laptop in a bag.

The limits are 360 rows, at most 75 steps each, zero retries, first hard
invariant stop, and the unchanged three runtime input fields. All experiment
network/provider/model/API/paid calls, Phase 0-6, WebShop, other models and
other datasets remain forbidden.

This NEW plan proposes the frozen six-hour service limit, not yesterday's
expired 07:00 deadline. A Windows-side check also requests stop after six
hours from launch, polling every five seconds while the host is awake.
The service keeps its 30-second shutdown grace. No software running on a
suspended/off host can enforce an absolute deadline at that instant.
No per-step worker timeout is added; a stalled row can consume the cap.

## Files

- Frozen plan: `configs/acl2027/tracegraph_tg8_manual_plan_20260916.json`
- Created on confirmation: `configs/acl2027/tracegraph_tg8_manual_authorized_20260916.json`
- Created on confirmation: `configs/acl2027/tracegraph_tg8_manual_receipt_20260916.json`
- New output: `artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1`
- Saved rows: `rows/*.json`; events: `events.jsonl`; terminal state: `exit.json`
- Full result when published: `result.json`, requiring a separate scientific audit

Re-running this entry point after confirmation is refused, even if startup
fails. Preserve all diagnostics; do not delete launch claims or old results.
An incomplete output is not a zero-success finding or a complete TG8 result.

## Offline Checks

`-CheckOnly` validates/displays the plan without authorizing or launching.
`-SelfTest` briefly acquires/releases only the Windows system-awake request;
it does not load an environment, create an authorization or run an episode.

On 2026-09-16, Windows tests passed 28 with 2 Linux-only skips. WSL tests
passed all 30. Both Windows CheckOnly (from a different working directory)
and WSL plan review passed. The real Windows self-test showed a SYSTEM
request and no DISPLAY request; a subsequent check showed both absent.
The frozen durable runner, legacy row executor and old launcher are unchanged.
