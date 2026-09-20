# TG8 V7 Deadline Extension

The user authorized extending only the existing run to 2026-09-16 07:00:00
Asia/Shanghai. The original stop deadline was 2026-09-16 04:26:16.
The unchanged shutdown grace is 30 seconds.

Authorization amendment:
`configs/acl2027/tracegraph_tg8_durable_v2_deadline_amendment_v1_20260915.json`
SHA-256: `ba3c7229513aa236b3c97061868217dd927e0b8990a5c6fbfa9cbf49a6cc32f5`.

## Application Record

The amendment's `change_method` describes the initially intended method.
The direct `systemctl set-property --runtime` call failed with
`Cannot set property RuntimeMaxUSec, or unknown property`; readback remained
six hours. It did not change or restart the experiment.

The successful fallback installed the separately recorded configuration
`configs/acl2027/tracegraph_tg8_durable_v2_deadline_extension_20260915.conf`
(SHA-256 `f2b823edd8165b2e6e8e72fb95ee5b30bb872ce61d54de1effac269aa3272932`)
at `/run/systemd/system/tg8-v2-ecaa88078a140638bacf.service.d/90-deadline-extension.conf`
and invoked `systemctl daemon-reload`, not service restart.
The original transient service fragment, run config, receipt and frozen
executors were not edited.

After reload, `systemctl show` and `systemd-analyze dump` reported:

- RuntimeMaxSec: 8h 33min 44s (30824 seconds).
- MainPID: 390; NRestarts: 0; state: active/running.
- ExecMainStartTimestamp and ActiveEnterTimestamp: 2026-09-15 22:26:16 CST.
- Need Daemon Reload: no; the unit-specific drop-in was loaded.
- Restart: no; PrivateNetwork: yes; TimeoutStopSec: 30s.
- RuntimeRandomizedExtraSec: 0; KillMode: control-group.

The limit is relative to the original active timestamp, not reload time.
It requests shutdown at approximately 07:00, with the existing 30-second
termination grace. No extra rows, retries, resume or restart are authorized.
All 360-row, 75-step, first-hard-invariant and three-input constraints remain.

The authorized config, receipt and durable runner hashes were rechecked:
`b17933813a83b403fae9c7dddac4568e48bc3f9f3ba885dec9fb845e9376584f`,
`ecaa88078a140638bacf1f3e5acadf1f71b20d0e86008ee3d9cff96794ec37e1`,
`6d6d1ad26f5f5ea18d7da8b8dece366035588fbd3ac5ee4dc7dab419091263e8`.

At the post-change status check, 102 rows were readable, including 19
successes; the latest event started ordinal 102 at 23:42:16 CST.
No exit record existed. These are interim counts, not a final audit or
scientific conclusion.

## Terminal Check: 2026-09-16

When the conversation resumed, the local clock was 2026-09-16 11:57:20 CST.
The service was no longer running. Journal evidence reports
`Service reached runtime time limit. Stopping.` at 11:50:12 CST and exit
130 with systemd result `timeout` at 11:50:14.
The durable exit record says `interrupted`, with no result.json.

The runtime property change above was verified, but it did NOT establish
enforcement of the requested absolute 07:00 wall-clock deadline. The observed
stop was 4h 50min 12s later. The cause of that discrepancy is unconfirmed;
do not assume suspension, clock changes or timer rearming without evidence.
Treat this as an infrastructure deadline anomaly, not successful completion.

Read-only terminal checks found 103 unique saved rows forming the exact
schedule prefix, 4416 transitions and 19 successes. All saved rows had at
most 75 steps, steps matched transition counts, exact three-field runtime
inputs, complete action histories, admissible selected actions and null
recorded hard-invariant violations. These checks passed; they are not a
fresh recomputation of every selector/ledger invariant.
Ordinal 103 started but has no saved row; its progress is unknown.
The last row was saved at 2026-09-15 23:43:27 CST.

The 360-row experiment is incomplete and cannot support a full-factorial
scientific conclusion. No retry, resume or new launch was performed.
The monitoring automation is removed after this terminal evidence check.

## Power Evidence Follow-Up

A subsequent read-only Windows System event query found:

- 2026-09-15 23:43:46 CST, Kernel-Power 506: entering connected standby,
  reason Idle Timeout.
- 2026-09-15 23:44:25 CST, Kernel-Power 507 then 506: lid-related transition.
- 2026-09-16 11:50:15 CST, Kernel-Power 507: leaving connected standby,
  reason Lid.

The last row was saved 19 seconds before the first standby event. The
11:50:12 service timeout was logged close to the 11:50:15 wake event.
This supports host standby/resume as a contributor to the progress gap and
delayed wall-clock stop; it does not prove the entire causal mechanism or
continuous sleep duration. Intermediate power transitions also exist.

At termination, stderr places the parent inside `env.step`, waiting on the
local multiprocessing result queue in `alfworld_envs.py:104`, not a network
read. The run had required PrivateNetwork isolation from launch. An Internet
outage alone is therefore not supported as the direct experiment failure
cause by these records. The worker's exact internal state remains unknown.
No live row was replayed to investigate.
